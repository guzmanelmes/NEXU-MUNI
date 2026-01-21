from app.extensions import db
from datetime import date

class Nombramiento(db.Model):
    __tablename__ = 'nombramientos'

    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    calidad_juridica = db.Column(db.Enum('PLANTA', 'CONTRATA', 'SUPLENCIA'), nullable=False)
    
    estamento_id = db.Column(db.Integer, db.ForeignKey('cat_estamentos.id'), nullable=False)
    grado = db.Column(db.Integer, nullable=False)
    
    # NUEVO: Vínculo con la Estructura Organizacional
    unidad_id = db.Column(db.Integer, db.ForeignKey('cat_unidades.id'), nullable=True)
    
    numero_decreto = db.Column(db.String(50), nullable=False)
    fecha_decreto = db.Column(db.Date, nullable=False)
    
    horas_semanales = db.Column(db.Integer, default=44)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=True) # Puede ser nulo para Planta
    
    estado = db.Column(db.String(20), default='VIGENTE')

    # Relaciones
    persona = db.relationship('Persona', backref=db.backref('nombramientos', lazy=True))
    estamento = db.relationship('CatEstamento', backref='nombramientos')
    
    # Relación para acceder a la unidad (Dirección/Depto) directamente
    unidad = db.relationship('CatUnidad', backref='nombramientos')

    @property
    def es_indefinido(self):
        return self.calidad_juridica == 'PLANTA'

    def __repr__(self):
        return f"<Nombramiento {self.persona_id} - {self.calidad_juridica}>"