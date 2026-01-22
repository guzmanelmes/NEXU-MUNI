from flask import Flask
from config import DevelopmentConfig
from app.extensions import db, ma

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. Inicializar extensiones
    db.init_app(app)
    ma.init_app(app)

    # 2. Registro de Modelos
    # Es vital importar los modelos aquí para que SQLAlchemy los detecte antes de cualquier operación
    with app.app_context():
        from app.models import catalogos, personas
        from app.models import remuneraciones
        from app.models import viaticos
        from app.models import programas, contratos
        from app.models import nombramientos
        # NUEVO: Modelo de Horas Extras
        from app.models import horas_extras 

    # 3. Registro de Blueprints (Rutas del Sistema)

    # --- HOME / DASHBOARD ---
    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)
    
    # --- API JSON ---
    from app.routes.personas_routes import personas_bp
    from app.routes.historial_routes import historial_bp
    app.register_blueprint(personas_bp)
    app.register_blueprint(historial_bp)

    # --- WEB (Gestión de Personas) ---
    from app.routes.web_routes import web_bp
    app.register_blueprint(web_bp)

    # --- CONFIGURACIONES GENERALES ---
    from app.routes.catalogos_routes import catalogos_bp
    app.register_blueprint(catalogos_bp)

    # --- REMUNERACIONES ---
    from app.routes.remuneraciones_routes import remuneraciones_bp
    app.register_blueprint(remuneraciones_bp)

    # --- VIÁTICOS ---
    from app.routes.viaticos_routes import viaticos_bp
    app.register_blueprint(viaticos_bp)

    # --- HORAS EXTRAS (NUEVO MÓDULO) ---
    from app.routes.horas_extras_routes import he_bp
    app.register_blueprint(he_bp)

    # --- PRESUPUESTO (Billetera) ---
    from app.routes.programas_routes import programas_bp
    app.register_blueprint(programas_bp)

    # --- CONTRATOS HONORARIOS (Operación) ---
    from app.routes.contratos_routes import contratos_bp
    app.register_blueprint(contratos_bp)

    # --- CONFIGURACIÓN DE CONTRATOS (CMS / Plantillas) ---
    from app.routes.config_contratos_routes import config_contratos_bp
    app.register_blueprint(config_contratos_bp)

    # --- FIRMANTES (Alcalde / Secretario) --- 
    from app.routes.autoridades_routes import autoridades_bp
    app.register_blueprint(autoridades_bp)

    # --- NOMBRAMIENTOS (Planta y Contrata) --- 
    from app.routes.nombramientos_routes import nombramientos_bp
    app.register_blueprint(nombramientos_bp)

    return app