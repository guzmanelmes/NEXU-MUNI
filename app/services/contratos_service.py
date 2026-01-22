from app.extensions import db
from app.models.programas import Programa, CuentaPresupuestaria
from app.models.contratos import ContratoHonorario, ContratoCuota, ContratoCuotaDetalle, AutoridadFirmante
from app.services.programas_service import ProgramasService
from docxtpl import DocxTemplate
from flask import current_app
from datetime import datetime
import json
import os

class ContratosService:

    @staticmethod
    def crear_contrato(data):
        """
        Crea el contrato con gestión financiera GRANULAR.
        Soluciona el error 'cuenta_id' buscando la cuenta automáticamente si no viene en el JSON.
        """
        try:
            monto_total = int(data['monto_total'])
            programa_id = int(data['programa_id'])
            
            # --- 1. PARSEO Y VALIDACIÓN DEL JSON FINANCIERO ---
            json_str = data.get('json_detalle_completo')
            if not json_str:
                raise ValueError("No se recibieron los datos de distribución financiera.")
            
            try:
                cuotas_data = json.loads(json_str)
            except json.JSONDecodeError:
                raise ValueError("Error de formato en los datos financieros.")

            # --- 1.1 PRE-CARGA DE CUENTAS DEL PROGRAMA (Para evitar KeyError: 'cuenta_id') ---
            # Si el JSON no trae el ID de la cuenta (ej: carga masiva), lo buscamos aquí.
            programa = Programa.query.get(programa_id)
            if not programa:
                raise ValueError("Programa no encontrado.")
            
            # Mapa rápido: Código -> ID Cuenta (Ej: '215.21...' -> 5)
            mapa_cuentas_programa = {c.codigo: c.id for c in programa.cuentas}

            # --- 2. CÁLCULO DE RESUMEN GLOBAL ---
            distribucion_global_map = {}
            
            for c_data in cuotas_data:
                for d_data in c_data['distribucion']:
                    codigo = d_data['codigo']
                    monto = int(d_data['monto'])
                    
                    # CORRECCIÓN CRÍTICA: Obtener cuenta_id de forma robusta
                    # 1. Intentamos leerlo del JSON
                    c_id = d_data.get('cuenta_id')
                    
                    # 2. Si no viene (Carga Masiva), lo buscamos en el mapa del programa
                    if not c_id:
                        c_id = mapa_cuentas_programa.get(codigo)
                    
                    # 3. Si aún no existe, error de negocio
                    if not c_id:
                        raise ValueError(f"La cuenta {codigo} no pertenece al programa seleccionado (ID {programa_id}).")

                    if codigo in distribucion_global_map:
                        distribucion_global_map[codigo]['monto'] += monto
                    else:
                        # Guardamos estructura completa para ProgramasService
                        distribucion_global_map[codigo] = {'monto': monto, 'cuenta_id': c_id}
            
            # Reconstruimos la lista preservando 'cuenta_id' para la rebaja de saldo
            distribucion_global_list = [
                {'codigo': k, 'monto': v['monto'], 'cuenta_id': v['cuenta_id']} 
                for k, v in distribucion_global_map.items()
            ]

            # Validación de integridad
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
                programa_id=programa_id,
                tipo_contrato_id=int(data['tipo_contrato_id']),
                monto_total=monto_total,
                numero_cuotas=len(cuotas_data),
                valor_mensual=0,
                estado='BORRADOR',
                horas_semanales=int(data.get('horas_semanales', 44)),
                fecha_firma=f_firma,
                fecha_inicio=f_inicio,
                fecha_fin=f_fin,
                fecha_decreto=f_decreto,
                numero_decreto_autoriza=data.get('numero_decreto_autoriza'),
                autoridad_id=int(data['autoridad_id']),
                secretario_id=int(data['secretario_id']),
                funciones_json=data.get('funciones'), 
                horario_json=data.get('horario'),     
                distribucion_cuentas_json=distribucion_global_list 
            )
            
            db.session.add(nuevo_contrato)
            db.session.flush()

            # --- 4. CREACIÓN DE CUOTAS (NIVEL 2) Y DETALLES (NIVEL 3) ---
            for index, c_data in enumerate(cuotas_data):
                nueva_cuota = ContratoCuota(
                    contrato_id=nuevo_contrato.id,
                    numero_cuota=index + 1,
                    mes=int(c_data['mes']),
                    anio=int(c_data['anio']),
                    monto=int(c_data['monto']),
                    estado='PENDIENTE'
                )
                db.session.add(nueva_cuota)
                db.session.flush()

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
            # Ahora distribucion_global_list tiene 'cuenta_id', evitando el error
            ProgramasService.rebajar_saldo(distribucion_global_list)
            
            db.session.commit()
            return nuevo_contrato
            
        except Exception as e:
            db.session.rollback()
            print(f"[ContratosService] Error al crear contrato: {str(e)}")
            raise e

    @staticmethod
    def actualizar_contrato(id, data):
        """
        Actualiza un contrato existente.
        REALIZA UN RESET FINANCIERO COMPLETO:
        1. Restituye el saldo al presupuesto original.
        2. Elimina cuotas y detalles antiguos.
        3. Crea la nueva estructura financiera.
        4. Descuenta el nuevo saldo.
        """
        try:
            contrato = ContratoHonorario.query.get(id)
            if not contrato:
                raise ValueError("Contrato no encontrado")

            # --- 1. ACTUALIZACIÓN DATOS ADMINISTRATIVOS ---
            contrato.numero_decreto_autoriza = data.get('numero_decreto_autoriza')
            if data.get('fecha_firma'):
                contrato.fecha_firma = datetime.strptime(data['fecha_firma'], '%Y-%m-%d').date()
            if data.get('fecha_decreto'):
                contrato.fecha_decreto = datetime.strptime(data['fecha_decreto'], '%Y-%m-%d').date()
            if data.get('fecha_inicio'):
                contrato.fecha_inicio = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d').date()
            if data.get('fecha_fin'):
                contrato.fecha_fin = datetime.strptime(data['fecha_fin'], '%Y-%m-%d').date()

            contrato.autoridad_id = int(data['autoridad_id'])
            contrato.secretario_id = int(data['secretario_id'])
            contrato.tipo_contrato_id = int(data['tipo_contrato_id'])
            contrato.horas_semanales = int(data.get('horas_semanales', 44))
            contrato.funciones_json = data.get('funciones') 
            contrato.horario_json = data.get('horario')

            # --- 2. GESTIÓN FINANCIERA (SI CAMBIÓ EL JSON) ---
            if data.get('json_detalle_completo'):
                json_str = data.get('json_detalle_completo')
                try:
                    nuevas_cuotas_data = json.loads(json_str)
                except:
                    raise ValueError("Error en formato JSON financiero.")

                # A. RESTITUCIÓN DE FONDOS (Devolver lo que se gastó antes)
                # Iteramos sobre el resumen global antiguo para devolver la plata
                if contrato.distribucion_cuentas_json:
                    for item in contrato.distribucion_cuentas_json:
                        # Necesitamos el ID de la cuenta para devolver el saldo
                        cuenta_id = item.get('cuenta_id')
                        if cuenta_id:
                            cuenta = CuentaPresupuestaria.query.get(cuenta_id)
                            if cuenta:
                                cuenta.saldo_actual += int(item['monto'])
                                db.session.add(cuenta) # Marcamos para update
                
                # B. LIMPIEZA DE CUOTAS ANTIGUAS
                # Borramos todas las cuotas asociadas (Cascada borrará detalles)
                ContratoCuota.query.filter_by(contrato_id=contrato.id).delete()
                
                # C. PROCESAMIENTO NUEVO (Lógica idéntica a crear)
                nuevo_monto_total = int(data.get('monto_total', contrato.monto_total))
                programa_id = int(data.get('programa_id', contrato.programa_id))
                
                # Actualizamos cabecera
                contrato.monto_total = nuevo_monto_total
                contrato.programa_id = programa_id
                contrato.numero_cuotas = len(nuevas_cuotas_data)

                # Pre-carga de cuentas para validación
                programa = Programa.query.get(programa_id)
                mapa_cuentas = {c.codigo: c.id for c in programa.cuentas}
                
                distribucion_nueva_map = {}

                # Crear Nuevas Cuotas
                for index, c_data in enumerate(nuevas_cuotas_data):
                    nueva_cuota = ContratoCuota(
                        contrato_id=contrato.id,
                        numero_cuota=index + 1,
                        mes=int(c_data['mes']),
                        anio=int(c_data['anio']),
                        monto=int(c_data['monto']),
                        estado='PENDIENTE'
                    )
                    db.session.add(nueva_cuota)
                    db.session.flush()

                    for d_data in c_data['distribucion']:
                        monto = int(d_data['monto'])
                        codigo = d_data['codigo']
                        # Buscar ID robustamente
                        c_id = d_data.get('cuenta_id') or mapa_cuentas.get(codigo)
                        
                        if not c_id:
                             raise ValueError(f"Cuenta {codigo} no existe en programa {programa_id}")

                        if monto > 0:
                            detalle = ContratoCuotaDetalle(
                                cuota_id=nueva_cuota.id,
                                codigo_cuenta=codigo,
                                monto_parcial=monto
                            )
                            db.session.add(detalle)
                            
                            # Acumular para el descuento global
                            if codigo in distribucion_nueva_map:
                                distribucion_nueva_map[codigo]['monto'] += monto
                            else:
                                distribucion_nueva_map[codigo] = {'monto': monto, 'cuenta_id': c_id}

                # D. DESCUENTO NUEVO SALDO
                distribucion_nueva_list = [
                    {'codigo': k, 'monto': v['monto'], 'cuenta_id': v['cuenta_id']} 
                    for k, v in distribucion_nueva_map.items()
                ]
                
                # Actualizamos el JSON de resumen en el contrato
                contrato.distribucion_cuentas_json = distribucion_nueva_list
                
                # Aplicamos la rebaja del nuevo presupuesto
                ProgramasService.rebajar_saldo(distribucion_nueva_list)

            db.session.commit()
            return contrato

        except Exception as e:
            db.session.rollback()
            print(f"[ContratosService] Error Actualizar: {str(e)}")
            raise e

    @staticmethod
    def generar_word_contrato(contrato_id):
        """Genera el DOCX usando la plantilla específica."""
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
        """Arma las variables {{variable}} para el Word."""
        persona = contrato.persona
        programa = contrato.programa
        autoridad = contrato.autoridad   
        secretario = contrato.secretario 
        
        lineas_alcalde = [l.upper() for l in [autoridad.firma_linea_1, autoridad.firma_linea_2, autoridad.firma_linea_3, autoridad.firma_linea_4] if l]
        bloque_alcalde = "\n".join(lineas_alcalde)

        lineas_secretario = [l.upper() for l in [secretario.firma_linea_1, secretario.firma_linea_2, secretario.firma_linea_3, secretario.firma_linea_4] if l]
        bloque_secretario = "\n".join(lineas_secretario)

        cargo_legal = autoridad.firma_linea_4 or autoridad.firma_linea_3 or autoridad.cargo
        horas = contrato.horas_semanales
        if horas == 44:
            texto_jornada = "Jornada Completa (44 Horas Semanales)"
        else:
            texto_jornada = f"Jornada Parcial de {horas} Horas Semanales según distribución horaria anexa"

        fecha_decreto_uso = contrato.fecha_decreto if contrato.fecha_decreto else contrato.fecha_firma

        cuentas_imputadas = []
        if contrato.distribucion_cuentas_json:
            for item in contrato.distribucion_cuentas_json:
                if 'codigo' in item:
                    cuentas_imputadas.append(item['codigo'])
        texto_imputacion = ", ".join(cuentas_imputadas) if cuentas_imputadas else "S/I"

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
        meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
        return f"{fecha_obj.day} de {meses.get(fecha_obj.month)} de {fecha_obj.year}"

    @staticmethod
    def procesar_carga_masiva(lector_csv):
        """
        Versión final compatible con planilla de 12 columnas.
        Incluye búsqueda inteligente de autoridades por RUT y Cargo.
        """
        exitos = 0
        errores = 0
        
        for fila in lector_csv:
            try:
                # Validar que venga RUT
                if not fila.get('rut'): continue

                # 1. TRADUCCIÓN DE RUT A ID (ALCALDE Y SECRETARIO)
                # Buscamos en cfg_autoridades_firmantes basándonos en el RUT del CSV
                # INTENTO 1: Buscar por RUT y coincidencia de texto en el Cargo
                rut_alcalde_csv = fila.get('Rut Alcalde', '').strip()
                rut_secretario_csv = fila.get('Rut Secretario', '').strip()

                alcalde = AutoridadFirmante.query.filter(
                    AutoridadFirmante.rut == rut_alcalde_csv,
                    AutoridadFirmante.cargo.ilike('%Alcalde%')
                ).first()
                
                # INTENTO 2 (Fallback): Si no coincide el cargo, buscar solo por RUT
                if not alcalde:
                    alcalde = AutoridadFirmante.query.filter_by(rut=rut_alcalde_csv).first()

                secretario = AutoridadFirmante.query.filter(
                    AutoridadFirmante.rut == rut_secretario_csv,
                    AutoridadFirmante.cargo.ilike('%Secretario%')
                ).first()

                if not secretario:
                    secretario = AutoridadFirmante.query.filter_by(rut=rut_secretario_csv).first()
                
                if not alcalde or not secretario:
                    raise ValueError(f"No se encontró Autoridad para: {rut_alcalde_csv} o {rut_secretario_csv}")

                # 2. PROCESAMIENTO FINANCIERO BASADO EN CUOTAS MANUALES
                monto_total = int(fila['Monto Total'])
                num_cuotas = int(fila['Numero de Cuotas']) 
                monto_cuota = monto_total // num_cuotas
                
                f_inicio = datetime.strptime(fila['Fecha Inicio'], '%Y-%m-%d').date()
                
                # Generamos la estructura JSON para las cuotas (Niveles 2 y 3)
                detalle_cuotas = []
                for i in range(num_cuotas):
                    mes_actual = (f_inicio.month + i - 1) % 12 + 1
                    anio_actual = f_inicio.year + (f_inicio.month + i - 1) // 12
                    
                    detalle_cuotas.append({
                        "mes": mes_actual,
                        "anio": anio_actual,
                        "monto": monto_cuota,
                        # NOTA: No enviamos 'cuenta_id', crear_contrato lo buscará por 'codigo'
                        "distribucion": [{"codigo": fila['cuenta_presupuestaria'], "monto": monto_cuota}]
                    })

                # 3. MAPEO DE TODOS LOS CAMPOS DE LA TABLA
                data_contrato = {
                    'persona_id': fila['rut'],
                    'programa_id': int(fila['programa_id']),
                    'tipo_contrato_id': int(fila.get('tipo_id', 1)), 
                    'autoridad_id': alcalde.id,
                    'secretario_id': secretario.id,
                    'monto_total': monto_total,
                    'fecha_inicio': fila['Fecha Inicio'],
                    'fecha_fin': fila['Fecha Termino'],
                    'fecha_firma': fila.get('Fecha Contrato', fila['Fecha Inicio']),
                    'fecha_decreto': fila.get('fecha decreto'),
                    'numero_decreto_autoriza': fila.get('numero decreto'),
                    'horas_semanales': int(fila.get('Horas semanales', 44)),
                    'funciones': [fila.get('Funciones', 'Labores según convenio municipal')],
                    'json_detalle_completo': json.dumps(detalle_cuotas)
                }

                # 4. CREACIÓN CON VALIDACIÓN INTEGRAL Y REBAJA DE SALDO
                ContratosService.crear_contrato(data_contrato)
                exitos += 1
                
            except Exception as e:
                # Log del error por consola y rollback para seguridad de la DB
                print(f"Error procesando fila de RUT {fila.get('rut', 'desc')}: {str(e)}")
                db.session.rollback()
                errores += 1
                continue
        
        return {'exitos': exitos, 'errores': errores}