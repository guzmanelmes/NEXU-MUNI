from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.viaticos_service import ViaticosService

viaticos_bp = Blueprint('viaticos_bp', __name__, url_prefix='/viaticos')

# 1. RUTA PRINCIPAL (Listado solo, si existiera un index separado)
@viaticos_bp.route('/', methods=['GET'])
def listar_escala():
    try:
        escalas = ViaticosService.get_todas_escalas()
        # Si usas el mismo HTML para todo, redirige a configurar o usa el mismo template
        return render_template('viaticos/create.html', escalas=escalas)
    except Exception as e:
        flash(f'Error al cargar escalas: {str(e)}', 'danger')
        return render_template('viaticos/create.html', escalas=[])

# 2. RUTA DE CONFIGURACIÓN (Aquí estaba el problema)
@viaticos_bp.route('/configurar', methods=['GET', 'POST'])
def configurar_escala():
    """
    Maneja tanto el GUARDADO (POST) como la VISTA DEL FORMULARIO + TABLA (GET).
    """
    if request.method == 'POST':
        try:
            ViaticosService.crear_escala(request.form)
            flash('Nueva escala registrada. Las vigencias se han ajustado automáticamente.', 'success')
            # Redirigimos a la misma ruta para ver los cambios
            return redirect(url_for('viaticos_bp.configurar_escala'))
            
        except ValueError as e:
            flash(f'Atención: {str(e)}', 'warning')
        except Exception as e:
            flash(f'Error crítico al guardar: {str(e)}', 'danger')
            
        return redirect(url_for('viaticos_bp.configurar_escala'))

    # --- PARTE CORREGIDA (GET) ---
    # Antes solo hacías return render_template(...), por eso la tabla salía vacía.
    # Ahora cargamos las escalas también aquí:
    try:
        escalas = ViaticosService.get_todas_escalas()
    except:
        escalas = []
        
    return render_template('viaticos/create.html', escalas=escalas)

# 3. RUTA DE ELIMINACIÓN
@viaticos_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_escala(id):
    try:
        if ViaticosService.eliminar_escala(id):
            flash('Registro eliminado y vigencias restauradas correctamente.', 'success')
        else:
            flash('No se encontró el registro a eliminar.', 'warning')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')
        
    # Redirigimos a configurar para volver a ver la tabla actualizada
    return redirect(url_for('viaticos_bp.configurar_escala'))