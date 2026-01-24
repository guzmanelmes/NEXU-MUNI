from app.extensions import db
from app.models.horas_extras import HeOrdenServicio, HePlanificacionDiaria, HeDecreto, HeConsolidadoMensual
from app.models.turnos import HeJornadaBase, HeJornadaDetalle, HeCalendarioEspecial
from app.models.nombramientos import Nombramiento
from app.services.turnos_service import TurnosService
from datetime import datetime, timedelta, time
from sqlalchemy import extract

class HorasExtrasService:

    # ==========================================================================
    # LÓGICA DE VALIDACIÓN DE HORARIOS Y TURNOS
    # ==========================================================================

    @staticmethod
    def es_horario_ordinario(rut_funcionario, fecha, h_inicio, h_termino):
        """
        Verifica si el bloque solicitado choca con la jornada ordinaria.
        Utiliza TurnosService para obtener la jornada jerárquica o de vísperas.
        """
        # Se pasa la fecha para que TurnosService detecte si es 17-sep, 24-dic o 31-dic
        jornada_base = TurnosService.obtener_horario_funcionario(rut_funcionario, fecha)
        if not jornada_base:
            return False # Si no hay jornada definida, no hay choque (asume libertad)

        dia_semana = fecha.weekday()
        # Busca el detalle configurado para ese día específico (0=Lunes...6=Domingo)
        detalle = next((d for d in jornada_base.detalles if d.dia_semana == dia_semana), None)

        if not detalle:
            return False # Si no trabaja ese día de forma ordinaria (ej: Sábado), es extra

        # Hay conflicto si: (Inicio Solicitado < Salida Ordinaria) Y (Término Solicitado > Entrada Ordinaria)
        # Esto cubre solapamientos parciales y totales.
        if h_inicio < detalle.hora_termino and h_termino > detalle.hora_inicio:
            return True
        
        return False

    @staticmethod
    def calcular_jornada(fecha, h_inicio, h_termino):
        """
        Determina si es 25% (Diurno) o 50% (Nocturno/Festivo) usando TurnosService.
        """
        # Consulta centralizada de días inhábiles
        es_inhabil = TurnosService.es_dia_inhabil(fecha)
        
        dt_inicio = datetime.combine(fecha, h_inicio)
        dt_termino = datetime.combine(fecha, h_termino)
        if dt_termino < dt_inicio:
            dt_termino += timedelta(days=1) # Cruce de medianoche

        duracion = round((dt_termino - dt_inicio).total_seconds() / 3600, 2)
        dia_semana = fecha.weekday()

        # REGLA DEL 50%:
        # 1. Fin de Semana (Sábado/Domingo)
        # 2. Feriado registrado en BD (es_inhabil)
        # 3. Horario Nocturno (Inicio >= 21:00 o Inicio < 07:00)
        if dia_semana >= 5 or es_inhabil or h_inicio.hour >= 21 or h_inicio.hour < 7:
            return 'NOCTURNO', duracion
        
        return 'DIURNO', duracion

    # ==========================================================================
    # LÓGICA TRANSACCIONAL: CREACIÓN Y EDICIÓN DE SOLICITUDES
    # ==========================================================================

    @staticmethod
    def crear_solicitud_completa(datos_form, dias_lista):
        try:
            if not datos_form.get('fecha_decreto'):
                return False, "Error: La Fecha del Decreto es obligatoria."
            
            fecha_dec_obj = datetime.strptime(datos_form['fecha_decreto'], '%Y-%m-%d').date()
            rut_funcionario_val = datos_form['rut']

            # 1. Crear Cabecera de Decreto (Borrador)
            nuevo_decreto = HeDecreto(
                tipo_decreto='AUTORIZACION',
                numero_decreto=datos_form.get('numero_decreto') or None,
                fecha_decreto=fecha_dec_obj,
                id_firmante_alcalde=datos_form['id_firmante_alcalde'],
                id_firmante_secretario=datos_form['id_firmante_secretario'],
                estado='BORRADOR'
            )
            db.session.add(nuevo_decreto)
            db.session.flush() 

            # 2. Crear Orden de Servicio vinculada
            nueva_orden = HeOrdenServicio(
                rut_funcionario=rut_funcionario_val,
                estado='BORRADOR',
                id_decreto_autorizacion=nuevo_decreto.id
            )
            db.session.add(nueva_orden)
            db.session.flush()

            # 3. Procesar y Validar Días
            res_detalle = HorasExtrasService._procesar_jornadas(nueva_orden, rut_funcionario_val, dias_lista)
            if not res_detalle[0]:
                raise ValueError(res_detalle[1])

            db.session.commit()
            return True, f"Solicitud Nº {nueva_orden.id} creada exitosamente."

        except ValueError as ve:
            db.session.rollback()
            return False, str(ve) 
        except Exception as e:
            db.session.rollback()
            return False, f"Error técnico: {str(e)}"

    @staticmethod
    def actualizar_solicitud(id_orden, datos_form, dias_lista):
        try:
            orden = HeOrdenServicio.query.get(id_orden)
            if not orden:
                return False, "Orden no encontrada."

            # Actualizar datos del Decreto asociado
            decreto = orden.decreto_auth
            if not datos_form.get('fecha_decreto'):
                return False, "Fecha de decreto requerida."
            
            decreto.fecha_decreto = datetime.strptime(datos_form['fecha_decreto'], '%Y-%m-%d').date()
            decreto.numero_decreto = datos_form.get('numero_decreto') or None
            decreto.id_firmante_alcalde = datos_form['id_firmante_alcalde']
            decreto.id_firmante_secretario = datos_form['id_firmante_secretario']

            # Limpiar días anteriores para re-procesar
            HePlanificacionDiaria.query.filter_by(id_orden=id_orden).delete()

            res_detalle = HorasExtrasService._procesar_jornadas(orden, orden.rut_funcionario, dias_lista, editando=True)
            if not res_detalle[0]:
                raise ValueError(res_detalle[1])

            db.session.commit()
            return True, f"Solicitud Nº {orden.id} actualizada."

        except ValueError as ve:
            db.session.rollback()
            return False, str(ve)
        except Exception as e:
            db.session.rollback()
            return False, f"Error al actualizar: {str(e)}"

    @staticmethod
    def _procesar_jornadas(orden, rut, dias_lista, editando=False):
        """
        Motor interno de validación e inserción de días.
        """
        horas_totales_diurnas = 0
        for dia in dias_lista:
            fecha_obj = datetime.strptime(dia['fecha'], '%Y-%m-%d').date()
            h_ini = datetime.strptime(dia['inicio'], '%H:%M').time()
            h_fin = datetime.strptime(dia['termino'], '%H:%M').time()

            # A. VALIDACIÓN INTELIGENTE DE TURNOS Y VÍSPERAS
            if HorasExtrasService.es_horario_ordinario(rut, fecha_obj, h_ini, h_fin):
                return False, f"Conflicto: El horario solicitado el {fecha_obj} coincide con la jornada ordinaria."

            # B. VALIDACIÓN DE SOLAPAMIENTO (No duplicar horas)
            query_conflicto = db.session.query(HePlanificacionDiaria).join(HeOrdenServicio).filter(
                HeOrdenServicio.rut_funcionario == rut,
                HeOrdenServicio.estado.notin_(['RECHAZADA', 'ANULADA']),
                HePlanificacionDiaria.fecha == fecha_obj,
                HePlanificacionDiaria.hora_inicio < h_fin,
                HePlanificacionDiaria.hora_termino > h_ini
            )
            if editando:
                query_conflicto = query_conflicto.filter(HeOrdenServicio.id != orden.id)

            if query_conflicto.first():
                return False, f"Ya existe una solicitud para el día {fecha_obj} en ese horario."

            # C. CÁLCULO DE RECARGO
            tipo, horas = HorasExtrasService.calcular_jornada(fecha_obj, h_ini, h_fin)
            if tipo == 'DIURNO':
                horas_totales_diurnas += horas

            nuevo_plan = HePlanificacionDiaria(
                id_orden=orden.id,
                fecha=fecha_obj,
                hora_inicio=h_ini,
                hora_termino=h_fin,
                tipo_jornada=tipo,
                horas_estimadas=horas,
                actividad_especifica=dia['actividad'],
                solicita_vehiculo=(dia.get('vehiculo') is True),
                placa_patente=dia.get('patente')
            )
            db.session.add(nuevo_plan)

        orden.es_emergencia = (horas_totales_diurnas > 40)
        return True, None

    # ==========================================================================
    # LÓGICA FINANCIERA: CÁLCULO DE VALORES MENSUALES
    # ==========================================================================

    @staticmethod
    def obtener_factor_hora(estamento_nombre):
        """
        Retorna el factor multiplicador según la ley municipal.
        Factor aproximado 1/190 hrs para jornada de 44 hrs.
        """
        # TODO: Refinar según configuración real del municipio
        return 0.0052631 

    @staticmethod
    def calcular_valores_mes(rut_funcionario, anio, mes):
        """
        Cierra el mes calculando el dinero a pagar según horas aprobadas y grado.
        Considera horas_reales si fueron verificadas/editadas.
        """
        try:
            # 1. Obtener Datos del Funcionario (Grado y Estamento)
            nombramiento = Nombramiento.query.filter_by(persona_id=rut_funcionario, estado='VIGENTE').first()
            if not nombramiento:
                return False, "Funcionario sin nombramiento vigente."

            grado = nombramiento.grado
            
            # --- FIX: DETECCIÓN INTELIGENTE DEL NOMBRE DEL ESTAMENTO ---
            estamento_obj = nombramiento.estamento
            if estamento_obj:
                estamento = getattr(estamento_obj, 'nombre', getattr(estamento_obj, 'estamento', getattr(estamento_obj, 'descripcion', 'ADMINISTRATIVO')))
            else:
                estamento = "ADMINISTRATIVO"

            # 2. Obtener Sueldo Base (Simulación)
            # TODO: Conectar con Modelo Remuneraciones real
            sueldo_base = 850000 

            # 3. Calcular Valor Hora Unitario
            factor = HorasExtrasService.obtener_factor_hora(estamento)
            valor_hora_base = int(sueldo_base * factor)
            
            valor_25 = int(valor_hora_base * 1.25)
            valor_50 = int(valor_hora_base * 1.50)

            # 4. SUMAR HORAS DESDE LA BD (AQUÍ ESTÁ LA LÓGICA DE ASISTENCIA)
            # Buscamos todas las planificaciones de este RUT en este MES y AÑO asociadas a Decretos FIRMADO/TRAMITADO
            items_del_mes = db.session.query(HePlanificacionDiaria).join(HeOrdenServicio).join(HeDecreto).filter(
                HeOrdenServicio.rut_funcionario == rut_funcionario,
                extract('month', HeDecreto.fecha_decreto) == mes,
                extract('year', HeDecreto.fecha_decreto) == anio,
                HeDecreto.estado.in_(['FIRMADO', 'TRAMITADO'])
            ).all()

            total_horas_25 = 0.0
            total_horas_50 = 0.0

            for item in items_del_mes:
                # Si se ingresaron horas reales (verificación), usamos esas. Si no, usamos las estimadas.
                horas_finales = item.horas_reales if item.horas_reales is not None else item.horas_estimadas
                
                # Conversión segura a float
                horas_finales = float(horas_finales)

                if item.tipo_jornada == 'DIURNO':
                    total_horas_25 += horas_finales
                else:
                    total_horas_50 += horas_finales

            # 5. Guardar o Actualizar Consolidado
            consolidado = HeConsolidadoMensual.query.filter_by(
                rut_funcionario=rut_funcionario, anio=anio, mes=mes
            ).first()

            if not consolidado:
                consolidado = HeConsolidadoMensual(
                    rut_funcionario=rut_funcionario, anio=anio, mes=mes
                )
                db.session.add(consolidado)

            # Guardamos Snapshot de Valores
            consolidado.grado_al_calculo = grado
            consolidado.sueldo_base_calculo = sueldo_base
            consolidado.valor_hora_25 = valor_25
            consolidado.valor_hora_50 = valor_50
            
            # Seteamos horas (editable posteriormente por RRHH)
            consolidado.horas_a_pagar_25 = total_horas_25
            consolidado.horas_a_pagar_50 = total_horas_50
            
            # Recalculamos totales monetarios
            consolidado.calcular_montos_dinero()
            consolidado.estado = 'CALCULADO'

            db.session.commit()
            return True, f"Cálculo exitoso. {total_horas_25} hrs (25%) y {total_horas_50} hrs (50%)."

        except Exception as e:
            db.session.rollback()
            return False, str(e)