# app/models/catalogos.py
from app.extensions import db

class CatSexo(db.Model):
    __tablename__ = 'cat_sexo'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    descripcion = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f"<Sexo {self.descripcion}>"

class CatNivelEstudios(db.Model):
    __tablename__ = 'cat_nivel_estudios'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    descripcion = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<NivelEstudios {self.descripcion}>"

class CatEstamentos(db.Model):
    __tablename__ = 'cat_estamentos'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    estamento = db.Column(db.String(100), nullable=False)
    grado_min = db.Column(db.Integer, default=1)
    grado_max = db.Column(db.Integer, default=20)

    def __repr__(self):
        return f"<Estamento {self.estamento}>"