from app.extensions import db
from datetime import datetime
# Importamos AutoridadFirmante explícitamente para evitar problemas de "nombre no encontrado"
from app.models.contratos import AutoridadFirmante

# ==============================================================================
# MÓDULO 1: SOLICITUD Y PLANIFICACIÓN
# ==============================================================================

class HeDecreto(db.Model):
    __tablename__ = 'he_decretos'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo_decreto = db.Column(db.Enum('AUTORIZACION', 'PAGO'), nullable=False)
    
    # Opcional (puede ser NULL)
    numero_decreto = db.Column(db.String(50))
    
    # Obligatorio (NOT NULL)
    fecha_decreto = db.Column(db.Date, nullable=False)
    
    # ELIMINADOS: anio y mes
    
    # Firmantes (Claves Foráneas)
    id_firmante_alcalde = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)
    id_firmante_secretario = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)
    
    # El nombre correcto en la BD es 'archivo_digital'
    archivo_digital = db.Column(db.String(255)) 
    
    estado = db.Column(db.Enum('BORRADOR', 'FIRMADO', 'TRAMITADO'), default='BORRADOR')

    # Relaciones
    firmante_alcalde = db.relationship('AutoridadFirmante', foreign_keys=[id_firmante_alcalde])
    firmante_secretario = db.relationship('AutoridadFirmante', foreign_keys=[id_firmante_secretario])


class HeOrdenServicio(db.Model):
    __tablename__ = 'he_orden_servicio'
    
    id = db.Column(db.Integer, primary_key=True)
    rut_funcionario = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    
    # ELIMINADOS: anio y mes
    
    # NOTA: Se eliminó 'motivo_trabajo'.
    
    es_emergencia = db.Column(db.Boolean, default=False)
    justificacion_emergencia = db.Column(db.Text)
    
    estado = db.Column(db.Enum('BORRADOR', 'EN_REVISION', 'AUTORIZADA', 'RECHAZADA', 'ANULADA'), default='BORRADOR')
    
    id_decreto_autorizacion = db.Column(db.Integer, db.ForeignKey('he_decretos.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    funcionario = db.relationship('Persona', backref='he_ordenes')
    decreto_auth = db.relationship('HeDecreto', foreign_keys=[id_decreto_autorizacion])
    
    # Cascade para borrar los días si borro la solicitud
    planificacion = db.relationship('HePlanificacionDiaria', backref='orden', cascade="all, delete-orphan", lazy=True)


class HePlanificacionDiaria(db.Model):
    __tablename__ = 'he_planificacion_diaria'
    
    id = db.Column(db.Integer, primary_key=True)
    id_orden = db.Column(db.Integer, db.ForeignKey('he_orden_servicio.id'), nullable=False)
    
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_termino = db.Column(db.Time, nullable=False)
    
    # Esta columna debe existir en la BD como ENUM('DIURNO', 'NOCTURNO', 'MIXTO')
    tipo_jornada = db.Column(db.Enum('DIURNO', 'NOCTURNO', 'MIXTO'), nullable=False)
    
    horas_estimadas = db.Column(db.Numeric(4, 2), nullable=False)
    actividad_especifica = db.Column(db.String(255), nullable=False)
    
    solicita_vehiculo = db.Column(db.Boolean, default=False)
    placa_patente = db.Column(db.String(20))


# ==============================================================================
# MÓDULO 2: ASISTENCIA REAL
# ==============================================================================

class HeAsistenciaReal(db.Model):
    __tablename__ = 'he_asistencia_real'
    
    id = db.Column(db.Integer, primary_key=True)
    rut_funcionario = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    
    marca_entrada = db.Column(db.DateTime)
    marca_salida = db.Column(db.DateTime)
    
    minutos_brutos = db.Column(db.Integer, default=0)
    descuento_colacion = db.Column(db.Integer, default=0)
    
    minutos_diurnos_25 = db.Column(db.Integer, default=0)
    minutos_nocturnos_50 = db.Column(db.Integer, default=0)
    
    origen_marca = db.Column(db.Enum('RELOJ_BIOMETRICO', 'WEB', 'MANUAL', 'JUSTIFICADO'), default='RELOJ_BIOMETRICO')
    observacion_control = db.Column(db.Text)

    funcionario = db.relationship('Persona', backref='he_asistencias')


# ==============================================================================
# MÓDULO 3 Y 4: CONSOLIDADO Y PAGO
# ==============================================================================

class HeConsolidadoMensual(db.Model):
    __tablename__ = 'he_consolidado_mensual'
    
    id = db.Column(db.Integer, primary_key=True)
    rut_funcionario = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    
    total_minutos_diurnos_validos = db.Column(db.Integer, default=0)
    total_minutos_nocturnos_validos = db.Column(db.Integer, default=0)
    
    horas_a_pagar_25 = db.Column(db.Numeric(5, 2), default=0)
    horas_a_pagar_50 = db.Column(db.Numeric(5, 2), default=0)
    horas_a_compensar = db.Column(db.Numeric(5, 2), default=0)
    
    factor_hora_25 = db.Column(db.Integer, default=0)
    factor_hora_50 = db.Column(db.Integer, default=0)
    monto_total_pagar = db.Column(db.Integer, default=0)
    
    id_decreto_pago = db.Column(db.Integer, db.ForeignKey('he_decretos.id'))
    
    funcionario = db.relationship('Persona', backref='he_consolidados')
    decreto_pago = db.relationship('HeDecreto', foreign_keys=[id_decreto_pago])