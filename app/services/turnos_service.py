from app.extensions import db
from app.models.turnos import HeJornadaBase, HeJornadaDetalle, HeCalendarioEspecial
from app.models.nombramientos import Nombramiento
from datetime import datetime

class TurnosService:
    @staticmethod
    def obtener_horario_funcionario(rut_funcionario, fecha_consulta=None):
        if not fecha_consulta:
            fecha_consulta = datetime.now().date()

        # Lógica de Vísperas
        dia_mes = (fecha_consulta.day, fecha_consulta.month)
        visperas_fechas = [(17, 9), (24, 12), (31, 12)]

        if dia_mes in visperas_fechas:
            jornada_vispera = HeJornadaBase.query.filter(
                HeJornadaBase.nombre.ilike('%Vísperas%'),
                HeJornadaBase.es_vigente == True
            ).first()
            if jornada_vispera:
                return jornada_vispera

        # Cascada normal
        jornada = HeJornadaBase.query.filter_by(
            tipo_ambito='FUNCIONARIO', valor_ambito=rut_funcionario, es_vigente=True
        ).first()

        if not jornada:
            nombramiento = Nombramiento.query.filter_by(persona_id=rut_funcionario, estado='VIGENTE').first()
            if nombramiento and nombramiento.unidad_id:
                jornada = HeJornadaBase.query.filter_by(
                    tipo_ambito='ESTAMENTO', valor_ambito=str(nombramiento.unidad_id), es_vigente=True
                ).first()

        if not jornada:
            jornada = HeJornadaBase.query.filter_by(tipo_ambito='GENERAL', es_vigente=True).first()

        return jornada

    @staticmethod
    def es_dia_inhabil(fecha):
        if isinstance(fecha, str):
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        feriado = HeCalendarioEspecial.query.filter_by(fecha=fecha).first()
        return feriado is not None

    @staticmethod
    def guardar_horarios_semanales(id_jornada, datos_semana):
        try:
            HeJornadaDetalle.query.filter_by(id_jornada_base=id_jornada).delete()
            for dia_idx, horas in datos_semana.items():
                if horas['inicio'] and horas['termino']:
                    nuevo_detalle = HeJornadaDetalle(
                        id_jornada_base=id_jornada,
                        dia_semana=int(dia_idx),
                        hora_inicio=datetime.strptime(horas['inicio'], '%H:%M').time(),
                        hora_termino=datetime.strptime(horas['termino'], '%H:%M').time(),
                        minutos_colacion=int(horas.get('colacion', 0))
                    )
                    db.session.add(nuevo_detalle)
            db.session.commit()
            return True, "Horarios actualizados exitosamente."
        except Exception as e:
            db.session.rollback()
            return False, f"Error al guardar: {str(e)}"