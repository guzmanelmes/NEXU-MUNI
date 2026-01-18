# app/routes/viaticos_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.viaticos_service import ViaticosService

# Definimos el Blueprint
viaticos_bp = Blueprint('viaticos_bp', __name__, url_prefix='/viaticos')

@viaticos_bp.route('/configuracion', methods=['GET', 'POST'])
def configurar_escala():
    """Vista para administrar los valores de los viáticos por grado"""
    
    if request.method == 'POST':
        try:
            # Enviamos todo el formulario al servicio
            ViaticosService.crear_escala(request.form.to_dict())
            flash('Tramo de viático registrado correctamente.', 'success')
            return redirect(url_for('viaticos_bp.configurar_escala'))
            
        except ValueError as e:
            flash(f'Error de validación: {str(e)}', 'warning')
        except Exception as e:
            flash(f'Error al guardar: {str(e)}', 'danger')

    # GET: Listar escalas existentes
    escalas = ViaticosService.get_todas_escalas()
    
    return render_template('viaticos/escala.html', escalas=escalas)

@viaticos_bp.route('/configuracion/eliminar/<int:id>', methods=['POST'])
def eliminar_escala(id):
    try:
        if ViaticosService.eliminar_escala(id):
            flash('Tramo eliminado correctamente.', 'info')
        else:
            flash('No se encontró el registro.', 'warning')
    except Exception as e:
        flash(f'Error crítico: {str(e)}', 'danger')
        
    return redirect(url_for('viaticos_bp.configurar_escala'))