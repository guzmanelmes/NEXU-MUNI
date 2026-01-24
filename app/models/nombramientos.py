from app.extensions import db
from datetime import date

class Nombramiento(db.Model):
    __tablename__ = 'nombramientos'

    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    
    # Clasificación Jurídica
    calidad_juridica = db.Column(db.Enum('PLANTA', 'CONTRATA', 'SUPLENCIA'), nullable=False)
    
    # Ubicación en Escalafón (Relación con Catálogos)
    estamento_id = db.Column(db.Integer, db.ForeignKey('cat_estamentos.id'), nullable=False)
    grado = db.Column(db.Integer, nullable=False)
    
    # Vínculo con la Estructura Organizacional (Clave para jerarquía de turnos)
    unidad_id = db.Column(db.Integer, db.ForeignKey('cat_unidades.id'), nullable=True)
    
    # Documento de Respaldo
    numero_decreto = db.Column(db.String(50), nullable=False)
    fecha_decreto = db.Column(db.Date, nullable=False)
    
    # Detalles del Cargo
    horas_semanales = db.Column(db.Integer, default=44)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=True)
    
    # Estado del Nombramiento
    estado = db.Column(db.Enum('VIGENTE', 'FINALIZADO', 'ANULADO'), default='VIGENTE')

    # --- Relaciones ---
    persona = db.relationship('Persona', backref=db.backref('nombramientos', lazy=True))
    estamento = db.relationship('CatEstamento', backref='nombramientos')
    unidad = db.relationship('CatUnidad', backref='nombramientos')

    @property
    def es_indefinido(self):
        """Indica si el cargo es de planta."""
        return self.calidad_juridica == 'PLANTA'

    def __repr__(self):
        return f"<Nombramiento {self.persona_id} - {self.calidad_juridica} - {self.estado}>"