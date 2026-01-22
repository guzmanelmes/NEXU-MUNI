import os
from docxtpl import DocxTemplate
from flask import current_app
from app.models.horas_extras import HeSolicitud, HeDiario
from datetime import datetime
import locale

# Intentar configurar fecha en español
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass # Si falla en Windows, no bloquea el sistema

class DocumentosHeService:
    
    MESES = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    @staticmethod
    def generar_decreto_autorizacion(solicitud_id):
        """
        Genera el Decreto (Ex-Ante) que autoriza las horas extras planificadas.
        """
        solicitud = HeSolicitud.query.get_or_404(solicitud_id)
        
        # 1. Preparar el Contexto (Variables para el Word)
        contexto = {
            'anio': solicitud.anio,
            'mes_nombre': DocumentosHeService.MESES.get(solicitud.mes, 'Mes Desconocido').upper(),
            'fecha_actual': datetime.now().strftime("%d de %B de %Y"),
            'es_emergencia': "SÍ" if solicitud.es_emergencia else "NO",
            'justificacion_emergencia': solicitud.justificacion_emergencia or "No aplica",
            'funcionarios': []
        }

        # 2. Procesar Funcionarios y sus Tareas
        for resumen in solicitud.resumenes:
            # Agrupar tareas únicas para que el decreto no sea eterno
            tareas_unicas = set()
            for dia in resumen.bitacora:
                if dia.nombre_actividad:
                    tareas_unicas.add(dia.nombre_actividad)
            
            texto_tareas = ", ".join(tareas_unicas) if tareas_unicas else "Labores impostergables inherentes al cargo."

            # Datos del funcionario
            fila = {
                'nombre_completo': f"{resumen.funcionario.nombres} {resumen.funcionario.apellido_paterno} {resumen.funcionario.apellido_materno}",
                'rut': resumen.rut_funcionario,
                'grado': f"{resumen.grado} {resumen.estamento}",
                'calidad': resumen.tipo_contrato,
                'unidad': resumen.unidad,
                'tareas': texto_tareas,
                # Totales estimados
                'horas_25_est': resumen.total_horas_25,
                'horas_50_est': resumen.total_horas_50
            }
            contexto['funcionarios'].append(fila)

        # 3. Cargar Plantilla
        ruta_plantilla = os.path.join(current_app.root_path, 'templates', 'word', 'plantilla_he_autorizacion.docx')
        
        if not os.path.exists(ruta_plantilla):
            raise FileNotFoundError(f"No se encontró la plantilla en: {ruta_plantilla}")

        doc = DocxTemplate(ruta_plantilla)
        
        # 4. Renderizar y Guardar
        doc.render(contexto)
        
        nombre_salida = f"Decreto_Autoriza_HE_{solicitud.mes}_{solicitud.anio}.docx"
        ruta_salida = os.path.join(current_app.root_path, 'static', 'temp', nombre_salida)
        
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        doc.save(ruta_salida)
        
        return ruta_salida, nombre_salida

    @staticmethod
    def generar_orden_trabajo_individual(dia_id):
        """
        Genera un documento Word individual para una Orden de Trabajo específica (un día).
        """
        # 1. Buscar el registro del día
        dia = HeDiario.query.get_or_404(dia_id)
        resumen = dia.resumen
        funcionario = resumen.funcionario
        
        # 2. Formatear horas y fechas
        # Formato de fecha largo: "Viernes 02 de Enero de 2026"
        fecha_texto = dia.fecha.strftime("%A %d de %B de %Y").capitalize()
        
        # 3. Preparar Contexto
        contexto = {
            'folio': dia.id, # Usamos el ID como número de folio simple
            'fecha_emision': datetime.now().strftime("%d/%m/%Y"),
            
            # Datos Funcionario
            'nombre_funcionario': f"{funcionario.nombres} {funcionario.apellido_paterno} {funcionario.apellido_materno}",
            'rut_funcionario': resumen.rut_funcionario,
            'cargo_funcionario': f"{resumen.tipo_contrato} - {resumen.grado}",
            'unidad': resumen.unidad,
            
            # Datos de la Orden
            'fecha_ejecucion': fecha_texto,
            'hora_inicio': dia.hora_inicio.strftime("%H:%M"),
            'hora_termino': dia.hora_termino.strftime("%H:%M"),
            'total_horas': dia.horas_calculadas,
            'tipo_recargo': f"{dia.tipo_recargo}%", # Muestra 25%, 50% o MIXTO%
            
            # Detalle
            'titulo_actividad': dia.nombre_actividad or "Sin título definido",
            'detalle_tareas': dia.actividad_realizada,
            
            # Logística
            'usa_vehiculo': "SÍ" if dia.usa_vehiculo else "NO",
            'patente': dia.placa_patente if dia.placa_patente else "N/A"
        }

        # 4. Cargar Plantilla
        ruta_plantilla = os.path.join(current_app.root_path, 'templates', 'word', 'plantilla_orden_trabajo.docx')
        
        if not os.path.exists(ruta_plantilla):
            raise FileNotFoundError(f"Falta la plantilla: {ruta_plantilla}")

        doc = DocxTemplate(ruta_plantilla)
        doc.render(contexto)

        # 5. Guardar temporal
        nombre_limpio = f"OT_{dia.id}_{resumen.rut_funcionario}.docx"
        ruta_salida = os.path.join(current_app.root_path, 'static', 'temp', nombre_limpio)
        
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        doc.save(ruta_salida)
        
        return ruta_salida, nombre_limpio

    @staticmethod
    def generar_orden_trabajo_grupal(lista_dias_ids):
        """
        Genera UN SOLO documento Word que agrupa varios días seleccionados.
        """
        if not lista_dias_ids:
            raise ValueError("No se seleccionaron días para generar la orden.")

        # 1. Buscar todos los registros seleccionados
        dias = HeDiario.query.filter(HeDiario.id.in_(lista_dias_ids)).order_by(HeDiario.fecha, HeDiario.hora_inicio).all()
        
        if not dias:
            raise ValueError("No se encontraron registros válidos.")

        # Validamos que todos sean del mismo funcionario (seguridad)
        primer_resumen = dias[0].resumen
        for d in dias:
            if d.resumen_id != primer_resumen.id:
                raise ValueError("No puedes agrupar días de funcionarios distintos en una misma orden.")

        funcionario = primer_resumen.funcionario
        
        # 2. Calcular Totales del Grupo
        total_horas_grupo = sum(d.horas_calculadas for d in dias)
        
        # Obtenemos el título de la actividad principal (usamos la del primer día como referencia o genérico)
        actividad_principal = dias[0].nombre_actividad
        
        # 3. Preparar Contexto para Word
        contexto = {
            'folio': f"{primer_resumen.id}-{len(dias)}", # Folio compuesto
            'fecha_emision': datetime.now().strftime("%d/%m/%Y"),
            
            # Datos Funcionario (Cabecera)
            'nombre_funcionario': f"{funcionario.nombres} {funcionario.apellido_paterno} {funcionario.apellido_materno}",
            'rut_funcionario': primer_resumen.rut_funcionario,
            'cargo_funcionario': f"{primer_resumen.tipo_contrato} - {primer_resumen.grado}",
            'unidad': primer_resumen.unidad,
            
            # Totales
            'total_horas_orden': total_horas_grupo,
            'actividad_global': actividad_principal,
            
            # LISTA DE DÍAS (Para la tabla dinámica en Word)
            'lista_dias': []
        }

        for d in dias:
            # Formato de fecha para la tabla
            fecha_str = d.fecha.strftime("%d/%m/%Y")
            dia_sem = d.fecha.strftime("%A").capitalize()
            
            fila = {
                'fecha': fecha_str,
                'dia_semana': dia_sem,
                'inicio': d.hora_inicio.strftime("%H:%M"),
                'termino': d.hora_termino.strftime("%H:%M"),
                'hrs': d.horas_calculadas,
                'recargo': f"{d.tipo_recargo}%" if d.tipo_recargo != 'MIXTO' else "Mixto",
                'actividad': d.actividad_realizada,
                'vehiculo': f"SÍ ({d.placa_patente})" if d.usa_vehiculo else "NO"
            }
            contexto['lista_dias'].append(fila)

        # 4. Cargar Plantilla Grupal
        ruta_plantilla = os.path.join(current_app.root_path, 'templates', 'word', 'plantilla_orden_trabajo_grupal.docx')
        
        if not os.path.exists(ruta_plantilla):
            raise FileNotFoundError(f"Falta plantilla: {ruta_plantilla}")

        doc = DocxTemplate(ruta_plantilla)
        doc.render(contexto)

        # 5. Guardar
        nombre_archivo = f"OT_Grupal_{primer_resumen.rut_funcionario}_{len(dias)}dias.docx"
        ruta_salida = os.path.join(current_app.root_path, 'static', 'temp', nombre_archivo)
        
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        doc.save(ruta_salida)
        
        return ruta_salida, nombre_archivo