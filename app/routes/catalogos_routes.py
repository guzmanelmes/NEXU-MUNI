from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.catalogos_service import CatalogosService

# Prefijo /config para todas las rutas de este archivo.
# El nombre catalogos_bp es indispensable para que app/__init__.py lo reconozca.
catalogos_bp = Blueprint('catalogos_bp', __name__, url_prefix='/config')

# --- RUTA PRINCIPAL (LISTADO GENERAL) ---
@catalogos_bp.route('/')
def index():
    """
    Carga de forma consolidada todos los catálogos para la vista principal.
    """
    try:
        # Obtiene datos desde CatalogosService
        unidades = CatalogosService.get_unidades()
        sexos = CatalogosService.get_sexos()
        niveles = CatalogosService.get_niveles_estudios()
        estamentos = CatalogosService.get_estamentos()
        
        return render_template('catalogos/index.html', 
                               unidades=unidades,
                               sexos=sexos, 
                               niveles=niveles, 
                               estamentos=estamentos)
    except Exception as e:
        flash(f'Error al cargar la configuración: {str(e)}', 'danger')
        return redirect(url_for('main_bp.dashboard'))

# =======================================================
# RUTAS PARA ESTRUCTURA ORGANIZACIONAL (UNIDADES)
# =======================================================

@catalogos_bp.route('/unidad/crear', methods=['POST'])
def crear_unidad():
    """Crea una nueva repartición municipal."""
    try:
        CatalogosService.crear_unidad(request.form)
        flash('Unidad organizacional agregada con éxito.', 'success')
    except Exception as e:
        flash(f'Error al crear unidad: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/unidad/editar', methods=['POST'])
def editar_unidad():
    """Actualiza los datos de una unidad u oficina."""
    try:
        id_unidad = request.form.get('id')
        CatalogosService.actualizar_unidad(id_unidad, request.form)
        flash('Unidad actualizada correctamente.', 'success')
    except Exception as e:
        flash(f'Error al actualizar unidad: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

# =======================================================
# RUTAS PARA ESTAMENTOS
# =======================================================

@catalogos_bp.route('/estamento/crear', methods=['POST'])
def crear_estamento():
    """Registra un nuevo estamento y sus rangos de grados."""
    try:
        CatalogosService.crear_estamento(
            request.form.get('estamento'),
            request.form.get('grado_min'),
            request.form.get('grado_max')
        )
        flash('Estamento registrado exitosamente.', 'success')
    except Exception as e:
        flash(f'Error al crear estamento: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/estamento/editar', methods=['POST'])
def editar_estamento():
    """Modifica un estamento existente."""
    try:
        CatalogosService.actualizar_estamento(
            request.form.get('id'),
            request.form.get('estamento'),
            request.form.get('grado_min'),
            request.form.get('grado_max')
        )
        flash('Estamento actualizado.', 'success')
    except Exception as e:
        flash(f'Error al actualizar estamento: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

# =======================================================
# RUTAS PARA NIVELES DE ESTUDIO Y SEXO
# =======================================================

@catalogos_bp.route('/nivel/crear', methods=['POST'])
def crear_nivel():
    """Agrega una nueva opción al catálogo de estudios."""
    try:
        CatalogosService.crear_nivel(request.form.get('descripcion'))
        flash('Nivel de estudios agregado.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/nivel/editar', methods=['POST'])
def editar_nivel():
    """Edita un nivel de estudio."""
    try:
        CatalogosService.actualizar_nivel(request.form.get('id'), request.form.get('descripcion'))
        flash('Nivel de estudios actualizado.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/sexo/crear', methods=['POST'])
def crear_sexo():
    """Agrega una opción de sexo."""
    try:
        CatalogosService.crear_sexo(request.form.get('descripcion'))
        flash('Opción agregada al catálogo de sexo.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

@catalogos_bp.route('/sexo/editar', methods=['POST'])
def editar_sexo():
    """Edita una opción de sexo."""
    try:
        CatalogosService.actualizar_sexo(request.form.get('id'), request.form.get('descripcion'))
        flash('Catálogo de sexo actualizado.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('catalogos_bp.index'))

# =======================================================
# RUTA ÚNICA DE ELIMINACIÓN (GENÉRICA)
# =======================================================

@catalogos_bp.route('/eliminar/<tipo>/<int:id>', methods=['POST'])
def eliminar(tipo, id):
    """
    Ruta centralizada que utiliza el parámetro 'tipo' para decidir qué eliminar.
    Maneja la integridad referencial para evitar errores de base de datos.
    """
    try:
        if tipo == 'unidad':
            CatalogosService.eliminar_unidad(id)
        elif tipo == 'estamento':
            CatalogosService.eliminar_estamento(id)
        elif tipo == 'nivel':
            CatalogosService.eliminar_nivel(id)
        elif tipo == 'sexo':
            CatalogosService.eliminar_sexo(id)
            
        flash(f'Registro de {tipo} eliminado correctamente.', 'warning')
    except Exception:
        # Se activa si el dato está siendo usado por algún funcionario o repartición.
        flash('No se puede eliminar: El dato está vinculado a otros registros activos.', 'danger')
    
    return redirect(url_for('catalogos_bp.index'))