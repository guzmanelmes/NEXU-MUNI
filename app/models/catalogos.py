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

class CatEstamento(db.Model):
    __tablename__ = 'cat_estamentos'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    estamento = db.Column(db.String(100), nullable=False)
    grado_min = db.Column(db.Integer, default=1)
    grado_max = db.Column(db.Integer, default=20)

    def __repr__(self):
        return f"<Estamento {self.estamento}>"

# --- NUEVO MODELO PARA ESTRUCTURA ORGANIZACIONAL ---

class CatUnidad(db.Model):
    __tablename__ = 'cat_unidades'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(150), nullable=False)
    sigla = db.Column(db.String(20))
    # Tipos: ALCALDIA, DIRECCION, DEPARTAMENTO, UNIDAD, OFICINA
    tipo = db.Column(db.String(50), nullable=False) 
    
    # Relación jerárquica: Una unidad puede depender de otra (ej: Oficina depende de Depto)
    padre_id = db.Column(db.Integer, db.ForeignKey('cat_unidades.id'), nullable=True)

    # Propiedad para acceder a la unidad superior
    padre = db.relationship('CatUnidad', remote_side=[id], backref='subunidades')

    def __repr__(self):
        return f"<Unidad {self.nombre} ({self.tipo})>"