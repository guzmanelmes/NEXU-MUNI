# app/schemas/catalogos_schema.py
from app.extensions import ma, db  # <--- IMPORTANTE: Importar db
from app.models.catalogos import CatSexo, CatNivelEstudios, CatEstamentos

class CatSexoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = CatSexo
        load_instance = True
        sqla_session = db.session  # <--- Cambiar ma.session por db.session

class CatNivelEstudiosSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = CatNivelEstudios
        load_instance = True
        sqla_session = db.session  # <--- Cambiar ma.session por db.session

class CatEstamentosSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = CatEstamentos
        load_instance = True
        sqla_session = db.session  # <--- Cambiar ma.session por db.session