from app.extensions import db

# =======================================================
# TABLA INTERMEDIA (MUCHOS A MUCHOS)
# Vincula qué Haberes están disponibles para qué Estamentos
# =======================================================
haber_estamento = db.Table('haber_estamento',
    db.Column('haber_id', db.Integer, db.ForeignKey('config_tipo_haberes.id'), primary_key=True),
    # Nota: Aquí se usa el nombre de la TABLA SQL ('cat_estamentos'), eso está correcto en plural.
    db.Column('estamento_id', db.Integer, db.ForeignKey('cat_estamentos.id'), primary_key=True)
)

# =======================================================
# MODELOS DE CONFIGURACIÓN
# =======================================================

class ConfigTipoHaberes(db.Model):
    __tablename__ = 'config_tipo_haberes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    es_imponible = db.Column(db.Boolean, default=True)
    es_tributable = db.Column(db.Boolean, default=True)
    
    # --- CLASIFICACIÓN DE GESTIÓN ---
    es_manual = db.Column(db.Boolean, default=True)
    
    # True = Permanente (Se paga todos los meses: Zona, Base)
    # False = Ocasional (Se paga por evento: Bonos, Extras)
    es_permanente = db.Column(db.Boolean, default=True)

    # --- NUEVO CAMPO: CONTROL DE VISUALIZACIÓN EN MATRIZ ---
    # True = Aparece en la Matriz General para edición (ej: Asignaciones variables locales)
    # False = Se oculta en la Matriz (ej: Valores fijos por ley o reajustados por Contraloría)
    es_visible_matriz = db.Column(db.Boolean, default=True)
    
    # Campo para el Motor de Cálculo (Fórmulas Matemáticas)
    formula = db.Column(db.String(255), nullable=True) 

    # RELACIÓN: Un haber puede estar habilitado para muchos estamentos
    # CORRECCIÓN: Cambiado 'CatEstamentos' a 'CatEstamento' (Singular)
    estamentos_habilitados = db.relationship(
        'CatEstamento', 
        secondary=haber_estamento, 
        backref=db.backref('haberes_disponibles', lazy='dynamic')
    )

class EscalaRemuneraciones(db.Model):
    __tablename__ = 'escala_remuneraciones'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_vigencia = db.Column(db.Date, nullable=False)
    estamento_id = db.Column(db.Integer, db.ForeignKey('cat_estamentos.id'), nullable=False)
    grado = db.Column(db.Integer, nullable=False)
    sueldo_base = db.Column(db.Integer, default=0)
    fecha_fin = db.Column(db.Date, nullable=True)

    # Relaciones
    # CORRECCIÓN: Cambiado 'CatEstamentos' a 'CatEstamento' (Singular)
    estamento = db.relationship('CatEstamento', backref='escalas')
    
    # Relación "Uno a Muchos": Una escala tiene muchos detalles
    detalles = db.relationship('EscalaRemuneracionesDetalle', backref='escala', cascade="all, delete-orphan")

class EscalaRemuneracionesDetalle(db.Model):
    __tablename__ = 'escala_remuneraciones_detalle'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    escala_id = db.Column(db.Integer, db.ForeignKey('escala_remuneraciones.id'), nullable=False)
    haber_id = db.Column(db.Integer, db.ForeignKey('config_tipo_haberes.id'), nullable=False)
    monto = db.Column(db.Integer, nullable=False, default=0)

    # Relación para acceder al nombre del haber desde el detalle
    haber = db.relationship('ConfigTipoHaberes')