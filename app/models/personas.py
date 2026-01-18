# app/models/personas.py
from app.extensions import db
from datetime import datetime

class Persona(db.Model):
    __tablename__ = 'personas'

    # Identificación
    rut = db.Column(db.String(12), primary_key=True) # PK manual según tu script
    nombres = db.Column(db.String(100), nullable=False)
    apellido_paterno = db.Column(db.String(100), nullable=False)
    apellido_materno = db.Column(db.String(100), nullable=False)

    # Demográficos
    fecha_nacimiento = db.Column(db.Date, nullable=False)
    nacionalidad = db.Column(db.String(50), nullable=False, default='Chilena')
    sexo_id = db.Column(db.Integer, db.ForeignKey('cat_sexo.id'), nullable=False)

    # Contacto
    direccion = db.Column(db.String(255))
    comuna_residencia = db.Column(db.String(100), default='Santa Juana')
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))

    # Perfil Profesional (Se llenan vía Trigger o Lógica, pero deben existir aquí)
    nivel_estudios_id = db.Column(db.Integer, db.ForeignKey('cat_nivel_estudios.id'))
    titulo_profesional = db.Column(db.String(100))

    # Inclusión (Mapeamos TINYINT a Boolean para fácil uso en Python)
    es_discapacitado = db.Column(db.Boolean, default=False)
    tiene_credencial_compin = db.Column(db.Boolean, default=False)
    recibe_pension_invalidez = db.Column(db.Boolean, default=False)
    tipo_discapacidad = db.Column(db.String(100))
    porcentaje_discapacidad = db.Column(db.Integer, default=0)

    # Fechas Históricas
    fecha_ingreso_municipio = db.Column(db.Date)
    fecha_ingreso_sector_publico = db.Column(db.Date)

    # Datos Bancarios
    banco_nombre = db.Column(db.String(100))
    tipo_cuenta = db.Column(db.String(50))
    numero_cuenta = db.Column(db.String(50))

    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- RELACIONES (La magia de SQLAlchemy) ---
    # Nos permite hacer persona.sexo.descripcion
    sexo = db.relationship('CatSexo', backref='personas')
    # Nos permite hacer persona.nivel_estudios_actual.descripcion
    nivel_estudios_actual = db.relationship('CatNivelEstudios', foreign_keys=[nivel_estudios_id])
    # Nos permite hacer persona.historial_academico (lista de títulos)
    historial_academico = db.relationship('HistorialAcademico', backref='persona', cascade="all, delete-orphan")


class HistorialAcademico(db.Model):
    __tablename__ = 'historial_academico'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rut_persona = db.Column(db.String(12), db.ForeignKey('personas.rut', ondelete='CASCADE'), nullable=False)
    
    nivel_estudios_id = db.Column(db.Integer, db.ForeignKey('cat_nivel_estudios.id'), nullable=False)
    nombre_titulo = db.Column(db.String(150), nullable=False)
    institucion = db.Column(db.String(150))
    fecha_titulacion = db.Column(db.Date)
    
    es_principal = db.Column(db.Boolean, default=False)

    # Relación para acceder al detalle del nivel desde el historial
    nivel_detalle = db.relationship('CatNivelEstudios')