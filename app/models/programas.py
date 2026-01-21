from app.extensions import db
from datetime import datetime

class Programa(db.Model):
    __tablename__ = 'programas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)  # Ej: "Gestión Territorial y Ayuda Social"
    numero_decreto = db.Column(db.String(50), nullable=False)
    fecha_decreto = db.Column(db.Date, nullable=False)
    archivo_adjunto = db.Column(db.String(255), nullable=True) # Ruta al PDF del decreto (Opcional)

    # Relación Master-Detail: Un programa tiene muchas cuentas.
    # cascade="all, delete-orphan" asegura que si borras el programa, se borren sus cuentas.
    cuentas = db.relationship('CuentaPresupuestaria', backref='programa', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Programa {self.nombre} (Dec. {self.numero_decreto})>'

class CuentaPresupuestaria(db.Model):
    __tablename__ = 'cuentas_presupuestarias'

    id = db.Column(db.Integer, primary_key=True)
    programa_id = db.Column(db.Integer, db.ForeignKey('programas.id'), nullable=False)
    
    codigo = db.Column(db.String(50), nullable=False) # Ej: 215.21.04.004
    descripcion = db.Column(db.String(100), nullable=True) # Ej: "Prestación de Servicios Comunitarios"
    
    monto_inicial = db.Column(db.Integer, default=0) # El monto original del decreto
    saldo_actual = db.Column(db.Integer, default=0)  # El monto que queda disponible (se descuenta con cada contrato)

    def __repr__(self):
        return f'<{self.codigo}: ${self.saldo_actual}>'