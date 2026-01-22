from app.extensions import db
from app.models.viaticos import EscalaViaticos, ViaticoDecreto
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
# Imports para Documentos (Word/PDF)
from docxtpl import DocxTemplate
from flask import current_app
import os
from werkzeug.utils import secure_filename

# Imports para Carga Masiva
import csv
import io
from app.models.personas import Persona
from app.models.nombramientos import Nombramiento

class ViaticosService:

    # ==============================================================================
    # GESTIÓN DE ESCALAS
    # ==============================================================================

    @staticmethod
    def get_todas_escalas():
        """Retorna las escalas ordenadas por fecha (más reciente primero) y luego por grado."""
        return EscalaViaticos.query.order_by(
            EscalaViaticos.fecha_inicio.desc(),
            EscalaViaticos.grado_min.asc()
        ).all()

    @staticmethod
    def crear_escala(data):
        """
        Crea una nueva escala y CIERRA AUTOMÁTICAMENTE la anterior si se solapan.
        """
        try:
            g_min = int(data.get('grado_min'))
            g_max = int(data.get('grado_max'))
            f_ini = datetime.strptime(data.get('fecha_inicio'), '%Y-%m-%d').date()
            
            fecha_fin_input = data.get('fecha_fin')
            f_fin = None
            if fecha_fin_input:
                f_fin = datetime.strptime(fecha_fin_input, '%Y-%m-%d').date()
                
        except (ValueError, TypeError):
            raise ValueError("Datos numéricos o de fecha inválidos.")

        if g_min > g_max:
            raise ValueError("El Grado Mínimo no puede ser mayor que el Grado Máximo.")

        # Lógica de cierre inteligente
        escala_anterior = EscalaViaticos.query.filter(
            EscalaViaticos.grado_min == g_min,
            EscalaViaticos.grado_max == g_max,
            or_(
                EscalaViaticos.fecha_fin == None,
                EscalaViaticos.fecha_fin >= f_ini
            )
        ).first()

        if escala_anterior:
            nuevo_fin_anterior = f_ini - timedelta(days=1)
            if nuevo_fin_anterior < escala_anterior.fecha_inicio:
                raise ValueError(f"La nueva escala comienza antes de que inicie la anterior vigente ({escala_anterior.fecha_inicio}).")

            escala_anterior.fecha_fin = nuevo_fin_anterior
            db.session.add(escala_anterior)

        nueva = EscalaViaticos(
            grado_min=g_min,
            grado_max=g_max,
            monto_100=int(data.get('monto_100')),
            monto_40=int(data.get('monto_40')),
            monto_20=int(data.get('monto_20')),
            fecha_inicio=f_ini,
            fecha_fin=f_fin
        )

        db.session.add(nueva)
        db.session.commit()
        return nueva

    @staticmethod
    def eliminar_escala(id):
        """Elimina una escala y restaura la vigencia de la anterior."""
        escala_a_borrar = EscalaViaticos.query.get(id)
        if not escala_a_borrar:
            return False

        try:
            inicio_borrada = escala_a_borrar.fecha_inicio
            fin_borrada = escala_a_borrar.fecha_fin 
            grados_min = escala_a_borrar.grado_min
            grados_max = escala_a_borrar.grado_max

            dia_anterior = inicio_borrada - timedelta(days=1)
            
            escala_anterior = EscalaViaticos.query.filter(
                EscalaViaticos.grado_min == grados_min,
                EscalaViaticos.grado_max == grados_max,
                EscalaViaticos.fecha_fin == dia_anterior
            ).first()

            if escala_anterior:
                escala_anterior.fecha_fin = fin_borrada
                db.session.add(escala_anterior)

            db.session.delete(escala_a_borrar)
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            raise e

    # ==============================================================================
    # GESTIÓN DE DECRETOS DE VIÁTICOS (CRUD + Cálculos)
    # ==============================================================================

    @staticmethod
    def obtener_escala_para_grado(grado, fecha_viaje):
        """Busca la escala monetaria vigente."""
        return EscalaViaticos.query.filter(
            EscalaViaticos.grado_min <= grado,
            EscalaViaticos.grado_max >= grado,
            EscalaViaticos.fecha_inicio <= fecha_viaje,
            or_(
                EscalaViaticos.fecha_fin == None,
                EscalaViaticos.fecha_fin >= fecha_viaje
            )
        ).first()

    @staticmethod
    def get_decretos(filtros=None):
        return ViaticoDecreto.query.order_by(ViaticoDecreto.id.desc()).all()

    @staticmethod
    def get_decreto_por_id(id):
        return ViaticoDecreto.query.get_or_404(id)

    @staticmethod
    def _limpiar_hora(hora_str):
        """
        CORRECCIÓN: Elimina segundos (HH:MM:SS -> HH:MM) para evitar errores en strptime.
        """
        if not hora_str: return None
        if len(hora_str) > 5:
            return hora_str[:5]
        return hora_str

    @staticmethod
    def crear_decreto_viatico(data):
        try:
            rut = data.get('rut_funcionario')
            grado = int(data.get('grado'))
            estamento = data.get('estamento')
            
            # Fechas y Horas (Usando _limpiar_hora)
            f_salida = datetime.strptime(data.get('fecha_salida'), '%Y-%m-%d').date()
            h_salida_str = ViaticosService._limpiar_hora(data.get('hora_salida'))
            h_salida = datetime.strptime(h_salida_str, '%H:%M').time()
            
            f_regreso = None
            h_regreso = None
            if data.get('fecha_regreso'):
                f_regreso = datetime.strptime(data.get('fecha_regreso'), '%Y-%m-%d').date()
            if data.get('hora_regreso'):
                h_regreso_str = ViaticosService._limpiar_hora(data.get('hora_regreso'))
                h_regreso = datetime.strptime(h_regreso_str, '%H:%M').time()

            # Cálculo Automático
            escala = ViaticosService.obtener_escala_para_grado(grado, f_salida)
            if not escala:
                raise ValueError(f"No existe escala de viáticos para Grado {grado} en fecha {f_salida}.")

            nuevo = ViaticoDecreto(
                numero_decreto=data.get('numero_decreto'),
                fecha_decreto=datetime.strptime(data['fecha_decreto'], '%Y-%m-%d').date() if data.get('fecha_decreto') else None,
                rut_funcionario=rut,
                estamento_al_viajar=estamento,
                grado_al_viajar=grado,
                motivo_viaje=data.get('motivo'),
                lugar_destino=data.get('destino'),
                fecha_salida=f_salida,
                hora_salida=h_salida,
                fecha_regreso=f_regreso,
                hora_regreso=h_regreso,
                usa_vehiculo='usa_vehiculo' in data,
                tipo_vehiculo=data.get('tipo_vehiculo'),
                placa_patente=data.get('placa_patente'),
                dias_al_100=float(data.get('dias_100', 0)),
                dias_al_40=float(data.get('dias_40', 0)),
                dias_al_20=float(data.get('dias_20', 0)),
                admin_municipal_id=int(data.get('admin_id')),
                secretario_municipal_id=int(data.get('secretario_id'))
            )

            nuevo.calcular_monto_total(escala)
            db.session.add(nuevo)
            db.session.commit()
            return nuevo

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def actualizar_decreto_viatico(id, data):
        """
        Actualiza decreto existente y recalcula montos.
        """
        try:
            decreto = ViaticoDecreto.query.get_or_404(id)
            
            decreto.numero_decreto = data.get('numero_decreto')
            if data.get('fecha_decreto'):
                decreto.fecha_decreto = datetime.strptime(data['fecha_decreto'], '%Y-%m-%d').date()
            
            decreto.motivo_viaje = data.get('motivo')
            decreto.lugar_destino = data.get('destino')
            
            # Fechas y Horas (Con limpieza)
            f_salida = datetime.strptime(data.get('fecha_salida'), '%Y-%m-%d').date()
            decreto.fecha_salida = f_salida
            
            h_salida_str = ViaticosService._limpiar_hora(data.get('hora_salida'))
            decreto.hora_salida = datetime.strptime(h_salida_str, '%H:%M').time()
            
            if data.get('fecha_regreso'):
                decreto.fecha_regreso = datetime.strptime(data.get('fecha_regreso'), '%Y-%m-%d').date()
            if data.get('hora_regreso'):
                h_regreso_str = ViaticosService._limpiar_hora(data.get('hora_regreso'))
                decreto.hora_regreso = datetime.strptime(h_regreso_str, '%H:%M').time()

            # Transporte
            decreto.usa_vehiculo = 'usa_vehiculo' in data
            decreto.tipo_vehiculo = data.get('tipo_vehiculo')
            decreto.placa_patente = data.get('placa_patente') if decreto.usa_vehiculo else None

            # Desglose
            decreto.dias_al_100 = float(data.get('dias_100', 0))
            decreto.dias_al_40 = float(data.get('dias_40', 0))
            decreto.dias_al_20 = float(data.get('dias_20', 0))

            # Firmantes
            decreto.admin_municipal_id = int(data.get('admin_id'))
            decreto.secretario_municipal_id = int(data.get('secretario_id'))

            # Recálculo
            escala = ViaticosService.obtener_escala_para_grado(decreto.grado_al_viajar, f_salida)
            if not escala:
                raise ValueError(f"No se encontró escala vigente para la fecha {f_salida}.")
            
            decreto.calcular_monto_total(escala)
            
            db.session.commit()
            return decreto

        except Exception as e:
            db.session.rollback()
            raise e

    # ==============================================================================
    # GENERACIÓN DE DOCUMENTOS Y ARCHIVOS (Word / PDF)
    # ==============================================================================

    @staticmethod
    def generar_word_decreto(id_decreto):
        """Genera el documento Word basado en plantilla."""
        decreto = ViaticoDecreto.query.get_or_404(id_decreto)
        root_path = current_app.root_path
        plantilla_path = os.path.join(root_path, 'templates', 'docs', 'plantilla_decreto_viatico.docx')
        
        if not os.path.exists(plantilla_path):
            raise FileNotFoundError("Plantilla no encontrada.")

        context = {
            'numero_decreto': decreto.numero_decreto or "___",
            'fecha_decreto': ViaticosService._formatear_fecha(decreto.fecha_decreto),
            'nombre_funcionario': f"{decreto.funcionario.nombres} {decreto.funcionario.apellido_paterno} {decreto.funcionario.apellido_materno}".upper(),
            'rut_funcionario': decreto.rut_funcionario,
            'grado': decreto.grado_al_viajar,
            'estamento': decreto.estamento_al_viajar.upper(),
            'destino': decreto.lugar_destino.upper(),
            'motivo': decreto.motivo_viaje,
            'fecha_salida': ViaticosService._formatear_fecha(decreto.fecha_salida),
            'hora_salida': decreto.hora_salida.strftime('%H:%M') if decreto.hora_salida else "",
            'fecha_regreso': ViaticosService._formatear_fecha(decreto.fecha_regreso),
            'hora_regreso': decreto.hora_regreso.strftime('%H:%M') if decreto.hora_regreso else "",
            'vehiculo_texto': f"Vehículo {decreto.tipo_vehiculo.lower()} Patente {decreto.placa_patente}" if decreto.usa_vehiculo and decreto.placa_patente else ("Vehículo Municipal" if decreto.tipo_vehiculo == 'MUNICIPAL' else "Locomoción Colectiva"),
            'dias_100': decreto.dias_al_100,
            'dias_40': decreto.dias_al_40,
            'dias_20': decreto.dias_al_20,
            'monto_total': f"${decreto.monto_total_calculado:,.0f}".replace(",", "."),
            'firma_admin_nombre': decreto.admin_municipal.firma_linea_1,
            'firma_admin_cargo': decreto.admin_municipal.firma_linea_4 or decreto.admin_municipal.cargo,
            'firma_secretario_nombre': decreto.secretario.firma_linea_1,
            'firma_secretario_cargo': decreto.secretario.firma_linea_4 or decreto.secretario.cargo,
        }

        doc = DocxTemplate(plantilla_path)
        doc.render(context)
        
        filename = f"Decreto_Viatico_{decreto.id}.docx"
        output_dir = os.path.join(root_path, 'static', 'downloads')
        os.makedirs(output_dir, exist_ok=True)
        doc.save(os.path.join(output_dir, filename))
        
        if decreto.estado == 'BORRADOR':
            decreto.estado = 'PENDIENTE_FIRMA'
            db.session.commit()
            
        return filename

    @staticmethod
    def subir_archivo_firmado(id_decreto, archivo):
        decreto = ViaticoDecreto.query.get_or_404(id_decreto)
        if not archivo: raise ValueError("Sin archivo.")
            
        filename = secure_filename(f"viatico_{decreto.id}_firmado.pdf")
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'viaticos')
        os.makedirs(upload_dir, exist_ok=True)
        
        archivo.save(os.path.join(upload_dir, filename))
        decreto.archivo_firmado = filename
        decreto.estado = 'APROBADO'
        db.session.commit()
        return True

    @staticmethod
    def _formatear_fecha(fecha):
        if not fecha: return "___"
        meses = {1:'Enero',2:'Febrero',3:'Marzo',4:'Abril',5:'Mayo',6:'Junio',7:'Julio',8:'Agosto',9:'Septiembre',10:'Octubre',11:'Noviembre',12:'Diciembre'}
        return f"{fecha.day} de {meses[fecha.month]} de {fecha.year}"

    # ==============================================================================
    # CARGA MASIVA (Importación CSV)
    # ==============================================================================

    @staticmethod
    def generar_plantilla_csv():
        """Genera un string CSV para que el usuario descargue la plantilla."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            'RUT_FUNCIONARIO', 'MOTIVO', 'DESTINO', 
            'FECHA_SALIDA (DD-MM-YYYY)', 'HORA_SALIDA (HH:MM)', 
            'FECHA_REGRESO (DD-MM-YYYY)', 'HORA_REGRESO (HH:MM)',
            'USA_VEHICULO (SI/NO)', 'TIPO_VEHICULO', 'PATENTE'
        ])
        writer.writerow([
            '12345678-9', 'Ejemplo Motivo', 'Ciudad Destino', 
            '01-12-2025', '08:30', 
            '02-12-2025', '18:00',
            'NO', 'LOCOMOCION_PUBLICA', ''
        ])
        return output.getvalue()

    @staticmethod
    def procesar_carga_masiva(archivo, admin_id, secretario_id):
        """
        Procesa el CSV de carga masiva, busca datos y calcula montos automáticamente.
        Retorna (exitos, errores).
        """
        stream = io.StringIO(archivo.stream.read().decode("UTF-8"), newline=None)
        csv_input = csv.DictReader(stream, delimiter=';')
        
        exitos = 0
        errores = []
        fila_num = 1 

        for row in csv_input:
            fila_num += 1
            try:
                # 1. Limpieza y Búsqueda de Persona
                rut_raw = row.get('RUT_FUNCIONARIO', '').strip()
                if not rut_raw: continue
                
                rut_limpio = rut_raw.upper().replace('.', '').replace('-', '')
                persona = Persona.query.filter_by(rut=rut_raw).first() or Persona.query.get(rut_raw) or Persona.query.filter_by(rut=rut_limpio).first()
                
                if not persona:
                    errores.append(f"Fila {fila_num}: RUT {rut_raw} no encontrado.")
                    continue

                # 2. Búsqueda de Nombramiento Vigente
                nombramiento = Nombramiento.query.filter_by(persona_id=persona.rut, estado='VIGENTE').order_by(Nombramiento.fecha_inicio.desc()).first()
                if not nombramiento:
                    errores.append(f"Fila {fila_num}: {persona.nombres} sin nombramiento vigente.")
                    continue
                
                # Mapeo Estamento
                estamento_bd = nombramiento.estamento.estamento.upper()
                mapa_estamentos = {
                    'ALCALDES': 'ALCALDE', 'DIRECTIVOS': 'DIRECTIVO', 'PROFESIONALES': 'PROFESIONAL',
                    'JEFATURAS': 'JEFATURA', 'TECNICOS': 'TECNICO', 'TÉCNICOS': 'TECNICO', 
                    'ADMINISTRATIVOS': 'ADMINISTRATIVO', 'AUXILIARES': 'AUXILIAR'
                }
                estamento_val = mapa_estamentos.get(estamento_bd, estamento_bd.rstrip('S'))

                # 3. Fechas
                try:
                    f_salida = datetime.strptime(row['FECHA_SALIDA (DD-MM-YYYY)'], '%d-%m-%Y').date()
                    h_salida = datetime.strptime(row['HORA_SALIDA (HH:MM)'], '%H:%M').time()
                    f_regreso = datetime.strptime(row['FECHA_REGRESO (DD-MM-YYYY)'], '%d-%m-%Y').date()
                    h_regreso = datetime.strptime(row['HORA_REGRESO (HH:MM)'], '%H:%M').time()
                except ValueError:
                    errores.append(f"Fila {fila_num}: Formato fecha/hora inválido.")
                    continue

                # 4. Cálculo Días Automático
                dias_100 = 0.0
                dias_40 = 0.0
                delta_dias = (f_regreso - f_salida).days
                if delta_dias == 0:
                    dias_40 = 1.0 
                else:
                    dias_100 = float(delta_dias)
                    dias_40 = 1.0

                # 5. Escala
                escala = ViaticosService.obtener_escala_para_grado(nombramiento.grado, f_salida)
                if not escala:
                    errores.append(f"Fila {fila_num}: Sin escala para Grado {nombramiento.grado}.")
                    continue

                # 6. Transporte
                usa_vehiculo = row.get('USA_VEHICULO (SI/NO)', 'NO').upper() == 'SI'
                tipo_vehiculo = row.get('TIPO_VEHICULO', 'LOCOMOCION_PUBLICA').upper()
                patente = row.get('PATENTE', '').upper() if usa_vehiculo else None

                # 7. Crear Decreto
                nuevo = ViaticoDecreto(
                    estado='BORRADOR',
                    rut_funcionario=persona.rut,
                    estamento_al_viajar=estamento_val,
                    grado_al_viajar=nombramiento.grado,
                    motivo_viaje=row.get('MOTIVO', 'Sin motivo'),
                    lugar_destino=row.get('DESTINO', 'Sin destino'),
                    fecha_salida=f_salida, hora_salida=h_salida,
                    fecha_regreso=f_regreso, hora_regreso=h_regreso,
                    usa_vehiculo=usa_vehiculo,
                    tipo_vehiculo=tipo_vehiculo,
                    placa_patente=patente,
                    dias_al_100=dias_100,
                    dias_al_40=dias_40,
                    dias_al_20=0.0,
                    admin_municipal_id=int(admin_id),
                    secretario_municipal_id=int(secretario_id)
                )
                
                nuevo.calcular_monto_total(escala)
                db.session.add(nuevo)
                exitos += 1

            except Exception as e:
                errores.append(f"Fila {fila_num}: Error inesperado - {str(e)}")

        if exitos > 0:
            db.session.commit()
        else:
            db.session.rollback()
            
        return exitos, errores