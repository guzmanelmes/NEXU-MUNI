from app.extensions import db
from datetime import datetime

class HeJornadaBase(db.Model):
    """
    Cabecera que define una 'Regla de Horario'.
    Puede ser el horario general de la muni, el de un estamento (ej: Salud)
    o uno específico para un funcionario (RUT).
    """
    __tablename__ = 'he_jornadas_base'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False) # Ej: 'Administrativos Estándar'
    descripcion = db.Column(db.Text)
    
    # Define a quién aplica esta regla
    tipo_ambito = db.Column(db.Enum('GENERAL', 'ESTAMENTO', 'FUNCIONARIO'), default='GENERAL')
    valor_ambito = db.Column(db.String(50), nullable=True) # El ID del Estamento o el RUT
    
    es_vigente = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con los días de la semana
    detalles = db.relationship('HeJornadaDetalle', backref='jornada_madre', cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f'<HeJornadaBase {self.nombre} ({self.tipo_ambito})>'


class HeJornadaDetalle(db.Model):
    """
    Define el horario específico para cada día de una Jornada Base.
    """
    __tablename__ = 'he_jornadas_detalles'
    
    id = db.Column(db.Integer, primary_key=True)
    id_jornada_base = db.Column(db.Integer, db.ForeignKey('he_jornadas_base.id'), nullable=False)
    
    # 0=Lunes, 1=Martes ... 6=Domingo
    dia_semana = db.Column(db.Integer, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_termino = db.Column(db.Time, nullable=False)
    
    # Minutos legales de colación (para descontar de la jornada ordinaria si es necesario)
    minutos_colacion = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<HeJornadaDetalle Dia:{self.dia_semana} {self.hora_inicio}-{self.hora_termino}>'


class HeCalendarioEspecial(db.Model):
    """
    Tabla de feriados y días inhábiles.
    Crucial para que el sistema sepa que cualquier hora en estos días es 50%.
    """
    __tablename__ = 'he_calendario_especial'
    
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, unique=True)
    descripcion = db.Column(db.String(255))
    es_irrenunciable = db.Column(db.Boolean, default=False)
    
    # FERIADO: Festivo nacional | ADMINISTRATIVO_MUNI: Día libre decretado por el Alcalde
    tipo_dia = db.Column(db.Enum('FERIADO', 'ADMINISTRATIVO_MUNI'), default='FERIADO')

    def __repr__(self):
        return f'<HeCalendarioEspecial {self.fecha}: {self.descripcion}>'