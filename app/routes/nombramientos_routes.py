from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.nombramientos_service import NombramientosService
from app.models.catalogos import CatEstamento, CatUnidad 
from datetime import datetime

# Definimos el Blueprint
nombramientos_bp = Blueprint('nombramientos_bp', __name__, url_prefix='/nombramientos')

@nombramientos_bp.route('/', methods=['GET'])
def listar():
    """
    Lista todos los nombramientos registrados.
    """
    try:
        nombramientos = NombramientosService.listar_todos()
        return render_template('nombramientos/index.html', 
                               nombramientos=nombramientos, 
                               fecha_actual=datetime.now().date())
    except Exception as e:
        flash(f'Error al cargar listado: {str(e)}', 'danger')
        return render_template('nombramientos/index.html', nombramientos=[])

@nombramientos_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo():
    """
    Crea un nuevo nombramiento.
    """
    if request.method == 'POST':
        try:
            NombramientosService.crear_nombramiento(request.form)
            flash('Nombramiento registrado exitosamente.', 'success')
            return redirect(url_for('nombramientos_bp.listar'))
        except ValueError as ve:
            flash(f'Atención: {str(ve)}', 'warning')
        except Exception as e:
            flash(f'Error crítico al guardar: {str(e)}', 'danger')
        return redirect(url_for('nombramientos_bp.nuevo'))

    try:
        estamentos = CatEstamento.query.order_by(CatEstamento.id).all()
        unidades = CatUnidad.query.order_by(CatUnidad.nombre).all()
        return render_template('nombramientos/create.html', 
                               estamentos=estamentos, 
                               unidades=unidades)
    except Exception as e:
        flash(f'Error al cargar formulario: {str(e)}', 'danger')
        return redirect(url_for('nombramientos_bp.listar'))

@nombramientos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    """
    Edita un nombramiento existente.
    """
    nombramiento = NombramientosService.obtener_por_id(id)
    
    if request.method == 'POST':
        try:
            NombramientosService.actualizar_nombramiento(id, request.form)
            flash('Nombramiento actualizado correctamente.', 'success')
            return redirect(url_for('nombramientos_bp.listar'))
        except ValueError as ve:
            flash(f'Error de validación: {str(ve)}', 'warning')
        except Exception as e:
            flash(f'Error al actualizar: {str(e)}', 'danger')
        return redirect(url_for('nombramientos_bp.editar', id=id))

    try:
        estamentos = CatEstamento.query.order_by(CatEstamento.id).all()
        unidades = CatUnidad.query.order_by(CatUnidad.nombre).all()
        return render_template('nombramientos/edit.html', 
                               n=nombramiento, 
                               estamentos=estamentos, 
                               unidades=unidades)
    except Exception as e:
        flash(f'Error al cargar datos de edición: {str(e)}', 'danger')
        return redirect(url_for('nombramientos_bp.listar'))

# --- NUEVA FUNCIÓN: FINALIZAR (Cerrar ciclo administrativo) ---
@nombramientos_bp.route('/finalizar/<int:id>', methods=['POST'])
def finalizar(id):
    """
    Cambia el estado del nombramiento (Renuncia, Término, etc.)
    """
    try:
        motivo = request.form.get('estado')
        fecha_termino = request.form.get('fecha_fin')
        NombramientosService.finalizar_nombramiento(id, motivo, fecha_termino)
        flash(f'Nombramiento finalizado por {motivo}.', 'warning')
    except Exception as e:
        flash(f'Error al procesar baja: {str(e)}', 'danger')
    return redirect(url_for('nombramientos_bp.listar'))

# --- NUEVA FUNCIÓN: ELIMINAR (Borrado físico) ---
@nombramientos_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """
    Elimina permanentemente el registro de la base de datos.
    """
    try:
        NombramientosService.eliminar_nombramiento(id)
        flash('Registro eliminado permanentemente de la base de datos.', 'success')
    except Exception as e:
        flash(f'Error al eliminar registro: {str(e)}', 'danger')
    return redirect(url_for('nombramientos_bp.listar'))

@nombramientos_bp.route('/ver/<int:id>', methods=['GET'])
def ver_detalle(id):
    try:
        nombramiento = NombramientosService.obtener_por_id(id)
        return render_template('nombramientos/show.html', n=nombramiento)
    except Exception as e:
        flash(f'No se pudo encontrar el registro: {str(e)}', 'danger')
        return redirect(url_for('nombramientos_bp.listar'))