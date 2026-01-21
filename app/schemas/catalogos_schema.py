from app.extensions import ma, db
# IMPORTANTE: Usamos CatEstamento (Singular) como definimos en el modelo
from app.models.catalogos import CatSexo, CatNivelEstudios, CatEstamento

class CatSexoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = CatSexo
        load_instance = True
        sqla_session = db.session

class CatNivelEstudiosSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = CatNivelEstudios
        load_instance = True
        sqla_session = db.session

class CatEstamentoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        # Aquí vinculamos con el modelo singular
        model = CatEstamento
        load_instance = True
        sqla_session = db.session