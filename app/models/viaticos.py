from app.extensions import db
from datetime import datetime

class EscalaViaticos(db.Model):
    __tablename__ = 'escala_viaticos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # ESTÁNDAR: Usamos 'fecha_vigencia' (Requiere que hayas ejecutado el ALTER TABLE en SQL)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=True) 
    
    # Rango de Grados (Ej: del 1 al 5)
    grado_min = db.Column(db.Integer, nullable=False)
    grado_max = db.Column(db.Integer, nullable=False)
    
    # Valores monetarios
    monto_100 = db.Column(db.Integer, default=0, nullable=False)
    monto_40 = db.Column(db.Integer, default=0, nullable=False)
    monto_20 = db.Column(db.Integer, default=0, nullable=False)
    
    def __repr__(self):
        estado = "Vigente" if self.fecha_fin is None else f"hasta {self.fecha_fin}"
        return f'<EscalaViaticos {self.fecha_inicio} (G{self.grado_min}-{self.grado_max}): {estado}>'

class SolicitudViatico(db.Model):
    __tablename__ = 'solicitud_viaticos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Funcionario
    persona_id = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    
    # Detalle del Viaje
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    destino = db.Column(db.String(200), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    
    # Cálculos
    dias_100 = db.Column(db.Float, default=0.0) # Con pernoctación
    dias_40 = db.Column(db.Float, default=0.0)  # Sin pernoctación
    total_pagar = db.Column(db.Integer, default=0)
    
    estado = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, APROBADO, PAGADO
    
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con Persona
    persona = db.relationship('Persona', backref=db.backref('viaticos', lazy=True))

    def __repr__(self):
        return f'<SolicitudViatico {self.id} - {self.persona_id}>'