# app/__init__.py
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
    # Importamos los modelos para que SQLAlchemy los reconozca al iniciar
    from app.models import catalogos, personas
    from app.models import remuneraciones
    from app.models import viaticos 

    # 3. Registro de Blueprints (Rutas)

    # --- MAIN (DASHBOARD / HOME) --- <--- NUEVO: Ruta Principal
    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)
    
    # --- API (Backend JSON) ---
    from app.routes.personas_routes import personas_bp
    from app.routes.historial_routes import historial_bp
    
    app.register_blueprint(personas_bp)
    app.register_blueprint(historial_bp)

    # --- WEB (Frontend Bootstrap) ---
    # Registramos las rutas que sirven el HTML (CRUD Personas)
    from app.routes.web_routes import web_bp
    app.register_blueprint(web_bp)

    # --- CONFIGURACIÓN ---
    # Registramos el módulo de gestión de catálogos (Sexos, Estamentos, Niveles)
    from app.routes.catalogos_routes import catalogos_bp
    app.register_blueprint(catalogos_bp)

    # --- REMUNERACIONES ---
    # Registramos el módulo de escalas de sueldo
    from app.routes.remuneraciones_routes import remuneraciones_bp
    app.register_blueprint(remuneraciones_bp)

    # --- VIÁTICOS ---
    # Registramos el módulo de configuración de escala de viáticos
    from app.routes.viaticos_routes import viaticos_bp
    app.register_blueprint(viaticos_bp)

    return app