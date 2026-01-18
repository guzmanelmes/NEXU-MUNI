from flask import Blueprint, render_template
from app.models.personas import Persona
from app.models.viaticos import EscalaViaticos
from datetime import date

# Creamos un Blueprint para las rutas generales
main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
def dashboard():
    """
    Panel de Control Principal.
    Recopila métricas clave de todos los módulos.
    """
    # 1. ESTADÍSTICAS DE RRHH
    total_funcionarios = Persona.query.count()
    
    # Funcionarios Hombres vs Mujeres (Ejemplo de métrica rápida)
    # Asumiendo ID 1=Hombre, 2=Mujer según tu catálogo
    total_hombres = Persona.query.filter_by(sexo_id=1).count()
    total_mujeres = Persona.query.filter_by(sexo_id=2).count()

    # 2. ESTADÍSTICAS DE VIÁTICOS
    # Verificamos si hay una escala vigente hoy
    hoy = date.today()
    escala_vigente = EscalaViaticos.query.filter(
        EscalaViaticos.fecha_inicio <= hoy,
        (EscalaViaticos.fecha_fin == None) | (EscalaViaticos.fecha_fin >= hoy)
    ).first()

    estado_viaticos = "Operativo" if escala_vigente else "Sin Configuración"
    color_viaticos = "success" if escala_vigente else "danger"

    return render_template('dashboard.html', 
                           total_funcionarios=total_funcionarios,
                           total_hombres=total_hombres,
                           total_mujeres=total_mujeres,
                           estado_viaticos=estado_viaticos,
                           color_viaticos=color_viaticos)