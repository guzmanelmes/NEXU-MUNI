from app.extensions import db
from app.models.horas_extras import HeOrdenServicio, HePlanificacionDiaria, HeDecreto
from datetime import datetime, timedelta, time

class HorasExtrasService:

    @staticmethod
    def crear_solicitud_completa(datos_form, dias_lista):
        """
        Orquesta la creación Transaccional con validaciones de negocio.
        """
        try:
            if not datos_form.get('fecha_decreto') or datos_form.get('fecha_decreto').strip() == '':
                return False, "Error: La Fecha del Decreto es obligatoria."
            
            fecha_dec_obj = datetime.strptime(datos_form['fecha_decreto'], '%Y-%m-%d').date()
            num_decreto = datos_form.get('numero_decreto') if datos_form.get('numero_decreto', '').strip() != '' else None
            rut_funcionario_val = datos_form['rut']

            nuevo_decreto = HeDecreto(
                tipo_decreto='AUTORIZACION',
                numero_decreto=num_decreto,
                fecha_decreto=fecha_dec_obj,
                id_firmante_alcalde=datos_form['id_firmante_alcalde'],
                id_firmante_secretario=datos_form['id_firmante_secretario'],
                estado='BORRADOR'
            )
            db.session.add(nuevo_decreto)
            db.session.flush() 

            nueva_orden = HeOrdenServicio(
                rut_funcionario=rut_funcionario_val,
                estado='BORRADOR',
                id_decreto_autorizacion=nuevo_decreto.id,
                es_emergencia=False 
            )
            db.session.add(nueva_orden)
            db.session.flush()

            # Procesar detalle
            res_detalle = HorasExtrasService._procesar_jornadas(nueva_orden, rut_funcionario_val, dias_lista)
            if not res_detalle[0]:
                raise ValueError(res_detalle[1])

            db.session.commit()
            return True, f"Solicitud Nº {nueva_orden.id} creada correctamente."

        except ValueError as ve:
            db.session.rollback()
            return False, str(ve) 
        except Exception as e:
            db.session.rollback()
            return False, f"Error técnico en servicio: {str(e)}"

    @staticmethod
    def actualizar_solicitud(id_orden, datos_form, dias_lista):
        """
        Actualiza una solicitud existente:
        1. Modifica cabecera del Decreto.
        2. Elimina jornadas previas.
        3. Inserta nuevas jornadas validando solapamientos.
        """
        try:
            orden = HeOrdenServicio.query.get(id_orden)
            if not orden:
                return False, "Orden no encontrada."

            # 1. Actualizar Decreto vinculado
            decreto = orden.decreto_auth
            if not datos_form.get('fecha_decreto') or datos_form.get('fecha_decreto').strip() == '':
                return False, "Error: La Fecha del Decreto es obligatoria."
            
            decreto.fecha_decreto = datetime.strptime(datos_form['fecha_decreto'], '%Y-%m-%d').date()
            decreto.numero_decreto = datos_form.get('numero_decreto') if datos_form.get('numero_decreto', '').strip() != '' else None
            decreto.id_firmante_alcalde = datos_form['id_firmante_alcalde']
            decreto.id_firmante_secretario = datos_form['id_firmante_secretario']

            # 2. Eliminar jornadas anteriores (Limpieza para re-inserción)
            HePlanificacionDiaria.query.filter_by(id_orden=id_orden).delete()

            # 3. Procesar nuevas jornadas
            res_detalle = HorasExtrasService._procesar_jornadas(orden, orden.rut_funcionario, dias_lista, editando=True)
            if not res_detalle[0]:
                raise ValueError(res_detalle[1])

            db.session.commit()
            return True, f"Solicitud Nº {orden.id} actualizada correctamente."

        except ValueError as ve:
            db.session.rollback()
            return False, str(ve)
        except Exception as e:
            db.session.rollback()
            return False, f"Error técnico al actualizar: {str(e)}"

    @staticmethod
    def _procesar_jornadas(orden, rut, dias_lista, editando=False):
        """
        Lógica interna para validar e insertar jornadas en la planificación.
        """
        horas_totales_diurnas = 0
        for dia in dias_lista:
            fecha_obj = datetime.strptime(dia['fecha'], '%Y-%m-%d').date()
            h_ini = datetime.strptime(dia['inicio'], '%H:%M').time()
            h_fin = datetime.strptime(dia['termino'], '%H:%M').time()

            # Validación de solapamiento
            query_conflicto = db.session.query(HePlanificacionDiaria).join(HeOrdenServicio).filter(
                HeOrdenServicio.rut_funcionario == rut,
                HeOrdenServicio.estado.notin_(['RECHAZADA', 'ANULADA']),
                HePlanificacionDiaria.fecha == fecha_obj,
                HePlanificacionDiaria.hora_inicio < h_fin,
                HePlanificacionDiaria.hora_termino > h_ini
            )
            
            # Si editamos, ignoramos la propia orden para no chocar con el "fantasma" de lo que estamos borrando
            if editando:
                query_conflicto = query_conflicto.filter(HeOrdenServicio.id != orden.id)

            conflicto = query_conflicto.first()
            if conflicto:
                return False, f"Conflicto de horario: El funcionario ya tiene horas el {fecha_obj} entre {conflicto.hora_inicio} y {conflicto.hora_termino}."

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

    @staticmethod
    def calcular_jornada(fecha, h_inicio, h_termino):
        """
        Calcula horas y determina si es Diurno (25%) o Nocturno (50%)
        """
        dt_inicio = datetime.combine(fecha, h_inicio)
        dt_termino = datetime.combine(fecha, h_termino)

        if dt_termino < dt_inicio:
            dt_termino += timedelta(days=1)

        duracion_horas = round((dt_termino - dt_inicio).total_seconds() / 3600, 2)
        dia_semana = fecha.weekday() # 0=Lunes, 6=Domingo
        
        if dia_semana >= 5 or h_inicio.hour >= 21 or (dt_termino.day > dt_inicio.day):
            return 'NOCTURNO', duracion_horas
        
        return 'DIURNO', duracion_horas