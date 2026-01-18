# app/routes/catalogos_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.catalogos_service import CatalogosService

# Prefijo /config para todas las rutas de este archivo
catalogos_bp = Blueprint('catalogos_bp', __name__, url_prefix='/config')

# --- RUTA PRINCIPAL (VISTA) ---
@catalogos_bp.route('/')
def index():
    """
    Carga las listas de todos los catálogos para mostrarlas en la vista de configuración.
    """
    # Obtiene lista de sexos registrados
    sexos = CatalogosService.get_sexos()
    
    # Obtiene lista de niveles de estudio usando el método actualizado
    niveles = CatalogosService.get_niveles_estudios() 
    
    # Obtiene lista de estamentos municipales
    estamentos = CatalogosService.get_estamentos()
    
    return render_template('catalogos/index.html', 
                           sexos=sexos, 
                           niveles=niveles, 
                           estamentos=estamentos)

# =======================================================
# RUTAS DE CREACIÓN (CREATE)
# =======================================================

@catalogos_bp.route('/sexo/crear', methods=['POST'])
def crear_sexo():
    try:
        # Crea un nuevo registro de sexo
        CatalogosService.crear_sexo(request.form.get('descripcion'))
        flash('Sexo agregado correctamente.', 'success')
    except Exception as e:
        flash(f'Error al crear: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/nivel/crear', methods=['POST'])
def crear_nivel():
    try:
        # Crea un nuevo nivel de estudios
        CatalogosService.crear_nivel(request.form.get('descripcion'))
        flash('Nivel de estudios agregado.', 'success')
    except Exception as e:
        flash(f'Error al crear: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/estamento/crear', methods=['POST'])
def crear_estamento():
    try:
        # Crea un nuevo estamento con sus rangos de grados
        CatalogosService.crear_estamento(
            request.form.get('estamento'),
            request.form.get('grado_min'),
            request.form.get('grado_max')
        )
        flash('Estamento creado exitosamente.', 'success')
    except Exception as e:
        flash(f'Error al crear: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

# =======================================================
# RUTAS DE EDICIÓN (UPDATE)
# =======================================================

@catalogos_bp.route('/sexo/editar', methods=['POST'])
def editar_sexo():
    try:
        # Actualiza la descripción de un sexo existente
        id = request.form.get('id')
        desc = request.form.get('descripcion')
        CatalogosService.actualizar_sexo(id, desc)
        flash('Sexo actualizado.', 'success')
    except Exception as e:
        flash(f'Error al actualizar: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/nivel/editar', methods=['POST'])
def editar_nivel():
    try:
        # Actualiza la descripción de un nivel de estudios
        CatalogosService.actualizar_nivel(request.form.get('id'), request.form.get('descripcion'))
        flash('Nivel actualizado.', 'success')
    except Exception as e:
        flash(f'Error al actualizar: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/estamento/editar', methods=['POST'])
def editar_estamento():
    try:
        # Actualiza los datos de un estamento municipal
        CatalogosService.actualizar_estamento(
            request.form.get('id'),
            request.form.get('estamento'),
            request.form.get('grado_min'),
            request.form.get('grado_max')
        )
        flash('Estamento actualizado.', 'success')
    except Exception as e:
        flash(f'Error al actualizar: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

# =======================================================
# RUTAS DE ELIMINACIÓN (DELETE)
# =======================================================

@catalogos_bp.route('/eliminar/<tipo>/<int:id>', methods=['POST'])
def eliminar(tipo, id):
    try:
        # Elimina el registro según el tipo de catálogo
        if tipo == 'sexo':
            CatalogosService.eliminar_sexo(id)
        elif tipo == 'nivel':
            CatalogosService.eliminar_nivel(id)
        elif tipo == 'estamento':
            CatalogosService.eliminar_estamento(id)
        flash('Elemento eliminado.', 'warning')
    except Exception:
        # Captura errores si el dato está vinculado a un funcionario (Integridad referencial)
        flash('No se puede eliminar: Este dato está siendo usado por un funcionario en el sistema.', 'danger')
    
    return redirect(url_for('catalogos_bp.index'))