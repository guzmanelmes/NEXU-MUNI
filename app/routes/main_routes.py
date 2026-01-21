from flask import Blueprint, render_template
from sqlalchemy import func
from datetime import datetime
from app.extensions import db

# Importamos los modelos necesarios para los contadores
from app.models.personas import Persona
from app.models.contratos import ContratoHonorario
from app.models.programas import Programa, CuentaPresupuestaria
from app.models.viaticos import EscalaViaticos

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
def dashboard():
    try:
        # 1. KPIs de Personas
        total_funcionarios = Persona.query.count()
        
        # 2. KPIs de Contratos
        total_contratos = ContratoHonorario.query.count()
        
        # 3. KPIs de Programas (Cantidad de programas creados)
        total_programas = Programa.query.count()
        
        # 4. KPI Financiero (Suma Total de la Billetera)
        # Usamos func.sum() para que la Base de Datos haga el cálculo (Más rápido)
        # scalar() devuelve el valor único. Si es None, usamos 'or 0'.
        saldo_total_global = db.session.query(
            func.sum(CuentaPresupuestaria.saldo_actual)
        ).scalar() or 0
        
        # 5. Estado de Configuración (Opcional, para alertas)
        escala_viaticos_ok = EscalaViaticos.query.count() > 0

        # 6. Fecha para el reporte
        fecha_actual = datetime.now().strftime("%d/%m/%Y")

        return render_template('dashboard.html',
                               total_funcionarios=total_funcionarios,
                               total_contratos=total_contratos,
                               total_programas=total_programas,
                               saldo_total_global=saldo_total_global,
                               fecha_actual=fecha_actual,
                               sistema_ok=escala_viaticos_ok)

    except Exception as e:
        # Si algo falla (ej: tablas no creadas), cargamos el dashboard en cero para no bloquear al usuario
        print(f"Error cargando dashboard: {str(e)}")
        return render_template('dashboard.html',
                               total_funcionarios=0,
                               total_contratos=0,
                               total_programas=0,
                               saldo_total_global=0,
                               fecha_actual=datetime.now().strftime("%d/%m/%Y"),
                               sistema_ok=False)