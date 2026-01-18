# app/schemas/personas_schema.py
from app.extensions import ma, db  # <--- IMPORTANTE: Se agrega 'db' para la sesión
from app.models.personas import Persona, HistorialAcademico
from app.schemas.catalogos_schema import CatSexoSchema, CatNivelEstudiosSchema
from marshmallow import fields

class HistorialAcademicoSchema(ma.SQLAlchemyAutoSchema):
    """Esquema para el historial de títulos y grados de un funcionario."""
    class Meta:
        model = HistorialAcademico
        load_instance = True
        include_fk = True
        sqla_session = db.session  # <--- CORREGIDO: Uso de db.session

    # Muestra el nombre del nivel (ej: "Magíster") en lugar de solo el ID
    nivel_detalle = ma.Nested(CatNivelEstudiosSchema, dump_only=True)

class PersonaSchema(ma.SQLAlchemyAutoSchema):
    """Esquema principal de Funcionarios con soporte para todos los nuevos campos."""
    class Meta:
        model = Persona
        load_instance = True
        include_fk = True
        sqla_session = db.session  # <--- CORREGIDO: Uso de db.session
        # Campos que el cliente no puede modificar manualmente al crear/editar
        dump_only = ('created_at', 'updated_at')

    # --- RELACIONES ENRIQUECIDAS (Solo lectura) ---
    
    # Muestra el objeto Sexo completo: { "id": 2, "descripcion": "Masculino" }
    sexo = ma.Nested(CatSexoSchema, dump_only=True)
    
    # Muestra el Nivel de Estudios actual vinculado a la ficha principal
    nivel_estudios = ma.Nested(CatNivelEstudiosSchema, dump_only=True)
    
    # LISTA MÁGICA: Esto traerá todo el historial académico de la persona en un array
    historial_academico = ma.List(ma.Nested(HistorialAcademicoSchema), dump_only=True)

    # --- FORMATEO DE CAMPOS ---
    # Asegura que las fechas siempre se devuelvan en formato ISO (YYYY-MM-DD)
    fecha_nacimiento = fields.Date()
    fecha_ingreso_municipio = fields.Date()
    fecha_ingreso_sector_publico = fields.Date()

# Instancias para uso global
persona_schema = PersonaSchema()
personas_schema = PersonaSchema(many=True)
historial_schema = HistorialAcademicoSchema()