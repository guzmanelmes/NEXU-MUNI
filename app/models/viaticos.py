# app/models/viaticos.py
from app.extensions import db

class EscalaViaticos(db.Model):
    __tablename__ = 'escala_viaticos'

    id = db.Column(db.Integer, primary_key=True)
    grado_min = db.Column(db.Integer, nullable=False)
    grado_max = db.Column(db.Integer, nullable=False)
    
    # Valores monetarios
    monto_100 = db.Column(db.Integer, default=0, nullable=False)
    monto_40 = db.Column(db.Integer, default=0, nullable=False)
    monto_20 = db.Column(db.Integer, default=0, nullable=False)
    
    # Vigencia
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=True) # <--- AHORA ES NULLABLE

    def __repr__(self):
        estado = "Vigente" if self.fecha_fin is None else f"hasta {self.fecha_fin}"
        return f'<Escala {self.grado_min}-{self.grado_max}: {estado}>'