# app/routes/web_routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request
from app.services.persona_service import PersonaService
from app.services.catalogos_service import CatalogosService # <--- Centralizamos catálogos
from app.services.historial_service import HistorialService

web_bp = Blueprint('web_bp', __name__)

# --- RUTA RAÍZ ---
@web_bp.route('/')
def index():
    return redirect(url_for('web_bp.listar_personas'))

# --- LISTAR (READ) ---
@web_bp.route('/personas')
def listar_personas():
    personas = PersonaService.get_all()
    return render_template('personas/index.html', personas=personas)

# --- CREAR (CREATE) ---
@web_bp.route('/personas/nueva', methods=['GET', 'POST'])
def crear_persona():
    if request.method == 'POST':
        # Capturamos todos los datos del formulario en un diccionario
        data = request.form.to_dict()
        
        # LÓGICA PARA CHECKBOXES (HTML no envía el campo si no está marcado)
        data['es_discapacitado'] = 1 if 'es_discapacitado' in request.form else 0
        data['tiene_credencial_compin'] = 1 if 'tiene_credencial_compin' in request.form else 0
        data['recibe_pension_invalidez'] = 1 if 'recibe_pension_invalidez' in request.form else 0

        try:
            PersonaService.create(data)
            flash('Funcionario creado exitosamente.', 'success')
            return redirect(url_for('web_bp.listar_personas'))
            
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash(f'Ocurrió un error: {str(e)}', 'danger')

    # CARGA DE CATÁLOGOS (Asegura que los nombres coincidan con el HTML)
    sexos = CatalogosService.get_sexos()
    niveles_estudios = CatalogosService.get_niveles_estudios() # <--- MÉTODO CLAVE

    return render_template('personas/create.html', 
                           sexos=sexos, 
                           niveles_estudios=niveles_estudios)

# --- EDITAR (UPDATE) ---
@web_bp.route('/personas/editar/<rut>', methods=['GET', 'POST'])
def editar_persona(rut):
    persona = PersonaService.get_by_rut(rut)
    if not persona:
        flash('La persona solicitada no existe.', 'danger')
        return redirect(url_for('web_bp.listar_personas'))

    if request.method == 'POST':
        data = request.form.to_dict()
        
        # Lógica para checkboxes en edición
        data['es_discapacitado'] = 1 if 'es_discapacitado' in request.form else 0
        data['tiene_credencial_compin'] = 1 if 'tiene_credencial_compin' in request.form else 0

        try:
            PersonaService.update(rut, data)
            flash(f'Datos de {persona.nombres} actualizados correctamente.', 'success')
            return redirect(url_for('web_bp.listar_personas'))
        except Exception as e:
            flash(f'Error al actualizar: {str(e)}', 'danger')

    # Carga de datos para los Selects
    sexos = CatalogosService.get_sexos()
    niveles_estudios = CatalogosService.get_niveles_estudios()

    return render_template('personas/edit.html', 
                           persona=persona, 
                           sexos=sexos, 
                           niveles_estudios=niveles_estudios)

# --- ELIMINAR (DELETE) ---
@web_bp.route('/personas/eliminar/<rut>', methods=['POST'])
def eliminar_persona(rut):
    try:
        if PersonaService.delete(rut):
            flash('Funcionario eliminado correctamente.', 'warning')
        else:
            flash('Error: No se encontró el funcionario para eliminar.', 'danger')
    except Exception as e:
        flash(f'No se pudo eliminar: {str(e)}', 'danger')
        
    return redirect(url_for('web_bp.listar_personas'))

# --- PERFIL DETALLADO ---
@web_bp.route('/personas/perfil/<rut>')
def ver_perfil(rut):
    persona = PersonaService.get_by_rut(rut)
    if not persona:
        flash('Persona no encontrada', 'danger')
        return redirect(url_for('web_bp.listar_personas'))
    
    niveles = CatalogosService.get_niveles_estudios()

    return render_template('personas/profile.html', persona=persona, niveles=niveles)

# --- HISTORIAL ACADÉMICO ---
@web_bp.route('/historial/agregar', methods=['POST'])
def agregar_titulo():
    rut = request.form.get('rut_persona')
    es_principal = 1 if request.form.get('es_principal') else 0

    data = {
        'rut_persona': rut,
        'nivel_estudios_id': request.form.get('nivel_estudios_id'),
        'nombre_titulo': request.form.get('nombre_titulo'),
        'institucion': request.form.get('institucion'),
        'fecha_titulacion': request.form.get('fecha_titulacion'),
        'es_principal': es_principal
    }

    try:
        HistorialService.create(data)
        flash('Título agregado correctamente.', 'success')
    except Exception as e:
        flash(f'Error al agregar título: {str(e)}', 'danger')
    
    return redirect(url_for('web_bp.ver_perfil', rut=rut))

@web_bp.route('/historial/eliminar/<int:id_historial>', methods=['POST'])
def eliminar_titulo(id_historial):
    rut_retorno = request.form.get('rut_retorno')
    try:
        HistorialService.delete(id_historial)
        flash('Registro académico eliminado.', 'warning')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('web_bp.ver_perfil', rut=rut_retorno))