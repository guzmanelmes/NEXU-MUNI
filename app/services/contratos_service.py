from app.extensions import db
from app.models.contratos import ContratoHonorario, ContratoCuota, ContratoCuotaDetalle
from app.models.programas import Programa
from app.services.programas_service import ProgramasService
from docxtpl import DocxTemplate
from flask import current_app, request
from datetime import datetime
import json  # IMPORTANTE: Necesario para leer el JSON del frontend
import os

class ContratosService:

    @staticmethod
    def crear_contrato(data):
        """
        Crea el contrato con gestión financiera GRANULAR.
        1. Recibe un JSON complejo desde el frontend con la estructura:
           [
             {
               "mes": 1, "anio": 2026, "monto": 100000,
               "distribucion": [ {"codigo": "215...", "monto": 40000}, ... ]
             },
             ...
           ]
        2. Procesa este JSON para crear el Contrato, las Cuotas y los Detalles específicos.
        """
        try:
            monto_total = int(data['monto_total'])
            
            # --- 1. PARSEO Y VALIDACIÓN DEL JSON FINANCIERO ---
            json_str = data.get('json_detalle_completo')
            if not json_str:
                raise ValueError("No se recibieron los datos de distribución financiera.")
            
            try:
                cuotas_data = json.loads(json_str)
            except json.JSONDecodeError:
                raise ValueError("Error de formato en los datos financieros.")

            # --- 2. CÁLCULO DE RESUMEN GLOBAL (Para Nivel 1 y Rebaja de Saldo) ---
            # Aunque guardamos el detalle mes a mes, el contrato necesita saber
            # cuánto se gastó en total por cuenta para el resumen general.
            distribucion_global_map = {}
            
            for c_data in cuotas_data:
                for d_data in c_data['distribucion']:
                    codigo = d_data['codigo']
                    monto = int(d_data['monto'])
                    
                    if codigo in distribucion_global_map:
                        distribucion_global_map[codigo] += monto
                    else:
                        distribucion_global_map[codigo] = monto
            
            # Convertimos el mapa a lista para guardarlo en el campo JSON del contrato
            distribucion_global_list = [{'codigo': k, 'monto': v} for k, v in distribucion_global_map.items()]

            # Validación de integridad: La suma del mapa debe ser igual al monto total
            suma_global = sum(item['monto'] for item in distribucion_global_list)
            if suma_global != monto_total:
                raise ValueError(f"Inconsistencia financiera: El detalle suma ${suma_global} pero el total declarado es ${monto_total}.")

            # --- 3. CREACIÓN DEL CONTRATO PADRE (NIVEL 1) ---
            
            f_firma = datetime.strptime(data['fecha_firma'], '%Y-%m-%d').date()
            f_inicio = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d').date()
            f_fin = datetime.strptime(data['fecha_fin'], '%Y-%m-%d').date()
            
            f_decreto = None
            if data.get('fecha_decreto'):
                f_decreto = datetime.strptime(data['fecha_decreto'], '%Y-%m-%d').date()

            nuevo_contrato = ContratoHonorario(
                persona_id=data['persona_id'],
                programa_id=int(data['programa_id']),
                tipo_contrato_id=int(data['tipo_contrato_id']),
                
                # Datos Financieros Globales
                monto_total=monto_total,
                numero_cuotas=len(cuotas_data), # Cantidad real de cuotas
                valor_mensual=0, # Variable
                
                # Control
                estado='BORRADOR',
                horas_semanales=int(data.get('horas_semanales', 44)),
                
                # Administrativos
                fecha_firma=f_firma,
                fecha_inicio=f_inicio,
                fecha_fin=f_fin,
                fecha_decreto=f_decreto,
                numero_decreto_autoriza=data.get('numero_decreto_autoriza'),
                autoridad_id=int(data['autoridad_id']),
                secretario_id=int(data['secretario_id']),
                
                # JSONs
                funciones_json=data.get('funciones'), 
                horario_json=data.get('horario'),     
                distribucion_cuentas_json=distribucion_global_list # Resumen global
            )
            
            db.session.add(nuevo_contrato)
            db.session.flush() # Obtener ID del contrato

            # --- 4. CREACIÓN DE CUOTAS (NIVEL 2) Y DETALLES (NIVEL 3) ---
            
            for index, c_data in enumerate(cuotas_data):
                # A. Crear la Cuota
                nueva_cuota = ContratoCuota(
                    contrato_id=nuevo_contrato.id,
                    numero_cuota=index + 1,
                    mes=int(c_data['mes']),
                    anio=int(c_data['anio']),
                    monto=int(c_data['monto']),
                    estado='PENDIENTE'
                )
                db.session.add(nueva_cuota)
                db.session.flush() # Obtener ID de la cuota

                # B. Crear los Detalles específicos de ESTA cuota
                for d_data in c_data['distribucion']:
                    monto_imputado = int(d_data['monto'])
                    
                    if monto_imputado > 0:
                        detalle = ContratoCuotaDetalle(
                            cuota_id=nueva_cuota.id,
                            codigo_cuenta=d_data['codigo'],
                            monto_parcial=monto_imputado
                        )
                        db.session.add(detalle)

            # --- 5. REBAJA PRESUPUESTARIA GLOBAL ---
            # Descontamos del programa el total acumulado por cuenta
            ProgramasService.rebajar_saldo(distribucion_global_list)
            
            db.session.commit()
            return nuevo_contrato
            
        except Exception as e:
            db.session.rollback()
            # Es útil ver el error en la consola si algo falla
            print(f"[ContratosService] Error al crear contrato: {str(e)}")
            raise e

    @staticmethod
    def actualizar_contrato(id, data):
        """
        Actualiza los datos administrativos de un contrato existente.
        NOTA: Por seguridad financiera, NO se permite editar la estructura de pagos aquí.
        """
        try:
            contrato = ContratoHonorario.query.get(id)
            if not contrato:
                raise ValueError("Contrato no encontrado")

            # Administrativos
            contrato.numero_decreto_autoriza = data.get('numero_decreto_autoriza')
            
            if data.get('fecha_firma'):
                contrato.fecha_firma = datetime.strptime(data['fecha_firma'], '%Y-%m-%d').date()
            
            if data.get('fecha_decreto'):
                contrato.fecha_decreto = datetime.strptime(data['fecha_decreto'], '%Y-%m-%d').date()

            contrato.autoridad_id = int(data['autoridad_id'])
            contrato.secretario_id = int(data['secretario_id'])
            contrato.tipo_contrato_id = int(data['tipo_contrato_id'])
            contrato.horas_semanales = int(data.get('horas_semanales', 44))
            
            # JSONs simples
            contrato.funciones_json = data.get('funciones') 
            contrato.horario_json = data.get('horario')     

            db.session.commit()
            return contrato

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def generar_word_contrato(contrato_id):
        """
        Genera el DOCX usando la plantilla específica.
        """
        contrato = ContratoHonorario.query.get(contrato_id)
        if not contrato:
            raise ValueError("Contrato no encontrado")

        tipo_contrato = contrato.tipo
        nombre_plantilla = tipo_contrato.plantilla_word 
        
        root_path = current_app.root_path
        plantilla_path = os.path.join(root_path, 'templates', 'docs', nombre_plantilla)
        
        if not os.path.exists(plantilla_path):
             raise FileNotFoundError(f"No se encontró el archivo de plantilla: {nombre_plantilla}")

        doc = DocxTemplate(plantilla_path)
        context = ContratosService._preparar_contexto_doc(contrato)
        doc.render(context)
        
        output_filename = f"Contrato_{contrato.persona.rut.replace('.', '')}_{contrato.id}.docx"
        downloads_dir = os.path.join(root_path, 'static', 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        output_path = os.path.join(downloads_dir, output_filename)
        doc.save(output_path)
        
        return output_filename

    @staticmethod
    def _preparar_contexto_doc(contrato):
        """
        Arma las variables {{variable}} para el Word.
        """
        persona = contrato.persona
        programa = contrato.programa
        autoridad = contrato.autoridad   
        secretario = contrato.secretario 
        
        # --- A. FIRMAS ---
        lineas_alcalde = [l.upper() for l in [autoridad.firma_linea_1, autoridad.firma_linea_2, autoridad.firma_linea_3, autoridad.firma_linea_4] if l]
        bloque_alcalde = "\n".join(lineas_alcalde)

        lineas_secretario = [l.upper() for l in [secretario.firma_linea_1, secretario.firma_linea_2, secretario.firma_linea_3, secretario.firma_linea_4] if l]
        bloque_secretario = "\n".join(lineas_secretario)

        cargo_legal = autoridad.firma_linea_4 or autoridad.firma_linea_3 or autoridad.cargo

        # --- B. JORNADA ---
        horas = contrato.horas_semanales
        if horas == 44:
            texto_jornada = "Jornada Completa (44 Horas Semanales)"
        else:
            texto_jornada = f"Jornada Parcial de {horas} Horas Semanales según distribución horaria anexa"

        # --- C. FECHAS ---
        fecha_decreto_uso = contrato.fecha_decreto if contrato.fecha_decreto else contrato.fecha_firma

        # --- D. IMPUTACIÓN (Texto simple para el Word - Muestra el resumen global) ---
        cuentas_imputadas = []
        if contrato.distribucion_cuentas_json:
            for item in contrato.distribucion_cuentas_json:
                if 'codigo' in item:
                    cuentas_imputadas.append(item['codigo'])
        texto_imputacion = ", ".join(cuentas_imputadas) if cuentas_imputadas else "S/I"

        # --- E. VALOR MENSUAL ---
        if contrato.numero_cuotas > 1:
            texto_monto_mensual = "Según calendario de cuotas anexo"
        else:
            texto_monto_mensual = f"${contrato.monto_total:,.0f}".replace(",", ".")

        return {
            'numero_decreto_contrato': contrato.numero_decreto_autoriza,
            'fecha_decreto_contrato': ContratosService._formatear_fecha_es(fecha_decreto_uso),
            'nombre_municipalidad': 'ILUSTRE MUNICIPALIDAD DE SANTA JUANA',
            'imputacion_presupuestaria': texto_imputacion,
            
            'nombre_autoridad': autoridad.firma_linea_1.upper(),
            'cargo_autoridad_legal': cargo_legal.upper(),

            'nombre_funcionario': f"{persona.nombres} {persona.apellido_paterno} {persona.apellido_materno}".upper(),
            'rut_funcionario': persona.rut,
            'domicilio_funcionario': (persona.direccion or "").upper(),
            'comuna_funcionario': (persona.comuna_residencia or 'SANTA JUANA').upper(),
            'profesion_funcionario': (persona.titulo_profesional or "EXPERTO EN OFICIO").upper(),
            
            'monto_total_num': f"${contrato.monto_total:,.0f}".replace(",", "."),
            'monto_mensual_num': texto_monto_mensual,
            'fecha_inicio_larga': ContratosService._formatear_fecha_es(contrato.fecha_inicio),
            'fecha_fin_larga': ContratosService._formatear_fecha_es(contrato.fecha_fin),
            
            'texto_jornada': texto_jornada,
            'lista_funciones': contrato.funciones_json or [],
            'horario': contrato.horario_json or {},

            'nombre_programa': programa.nombre.upper(),
            'decreto_programa': programa.numero_decreto,
            'fecha_decreto_programa': ContratosService._formatear_fecha_es(programa.fecha_decreto),
            
            'bloque_firma_alcalde': bloque_alcalde,
            'bloque_firma_secretario': bloque_secretario,
            'fecha_actual': ContratosService._formatear_fecha_es(datetime.now())
        }

    @staticmethod
    def _formatear_fecha_es(fecha_obj):
        if not fecha_obj: return ""
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return f"{fecha_obj.day} de {meses.get(fecha_obj.month)} de {fecha_obj.year}"