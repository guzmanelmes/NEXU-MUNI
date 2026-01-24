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
    # Se importan aquí para que SQLAlchemy genere/detecte las tablas correctamente
    with app.app_context():
        # Importación de modelos base
        from app.models import catalogos, personas
        from app.models import remuneraciones
        from app.models import viaticos
        from app.models import programas, contratos
        
        # Importación de modelos críticos para el sistema de asistencia
        from app.models import nombramientos
        from app.models import horas_extras 
        from app.models import turnos

    # 3. Registro de Blueprints (Rutas del Sistema)
    
    # --- HOME / DASHBOARD ---
    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)
    
    # --- MÓDULOS DE PERSONAS Y ARCHIVOS ---
    from app.routes.personas_routes import personas_bp
    from app.routes.historial_routes import historial_bp
    from app.routes.web_routes import web_bp
    app.register_blueprint(personas_bp)
    app.register_blueprint(historial_bp)
    app.register_blueprint(web_bp)

    # --- REMUNERACIONES Y VIÁTICOS ---
    from app.routes.remuneraciones_routes import remuneraciones_bp
    from app.routes.viaticos_routes import viaticos_bp
    app.register_blueprint(remuneraciones_bp)
    app.register_blueprint(viaticos_bp)

    # --- ASISTENCIA, HORAS EXTRAS Y TURNOS (MOTOR INTELIGENTE) ---
    from app.routes.horas_extras_routes import he_bp
    from app.routes.turnos_routes import turnos_bp
    app.register_blueprint(he_bp)
    app.register_blueprint(turnos_bp)

    # --- GESTIÓN DE CONTRATOS Y NOMBRAMIENTOS ---
    from app.routes.contratos_routes import contratos_bp
    from app.routes.config_contratos_routes import config_contratos_bp
    from app.routes.nombramientos_routes import nombramientos_bp
    app.register_blueprint(contratos_bp)
    app.register_blueprint(config_contratos_bp)
    app.register_blueprint(nombramientos_bp)

    # --- CONFIGURACIONES GENERALES, BILLETERA Y AUTORIDADES ---
    from app.routes.catalogos_routes import catalogos_bp
    from app.routes.programas_routes import programas_bp
    from app.routes.autoridades_routes import autoridades_bp
    app.register_blueprint(catalogos_bp)
    app.register_blueprint(programas_bp)
    app.register_blueprint(autoridades_bp)

    return app