from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.contratos import TipoContratoHonorario
import os

# Definimos el Blueprint
config_contratos_bp = Blueprint('config_contratos_bp', __name__, url_prefix='/config/contratos')

@config_contratos_bp.route('/', methods=['GET'])
def listar():
    """
    Lista todos los tipos de contrato configurados.
    """
    try:
        tipos = TipoContratoHonorario.query.all()
        # Asegúrate de que esta ruta coincida con donde guardaste el HTML anterior
        return render_template('config/tipos_contrato/index.html', tipos=tipos)
    except Exception as e:
        flash(f'Error al cargar listado: {str(e)}', 'danger')
        return render_template('config/tipos_contrato/index.html', tipos=[])

@config_contratos_bp.route('/guardar', methods=['POST'])
def guardar():
    """
    Maneja tanto la CREACIÓN (nuevo) como la EDICIÓN (existente) de tipos de contrato.
    """
    try:
        # 1. Obtener datos del formulario
        tipo_id = request.form.get('id')
        nombre = request.form.get('nombre')
        
        # Checkboxes: HTML envía 'on' si está marcado, o nada si no lo está.
        es_jornada_completa = True if request.form.get('es_jornada_completa') else False
        usa_asistencia = True if request.form.get('usa_asistencia') else False
        
        archivo = request.files.get('plantilla_word')

        # 2. Lógica: ¿Crear o Actualizar?
        if tipo_id:
            # --- EDICIÓN ---
            tipo = TipoContratoHonorario.query.get_or_404(tipo_id)
            tipo.nombre = nombre
            tipo.es_jornada_completa = es_jornada_completa
            tipo.usa_asistencia = usa_asistencia
            mensaje = 'Tipo de contrato actualizado correctamente.'
        else:
            # --- CREACIÓN ---
            # Validación: Al crear es obligatorio subir el archivo
            if not archivo or archivo.filename == '':
                flash('Error: Debe subir una plantilla Word para crear un nuevo tipo.', 'warning')
                return redirect(url_for('config_contratos_bp.listar'))
                
            tipo = TipoContratoHonorario(
                nombre=nombre,
                es_jornada_completa=es_jornada_completa,
                usa_asistencia=usa_asistencia
            )
            db.session.add(tipo)
            mensaje = 'Nuevo tipo de contrato creado exitosamente.'

        # 3. GESTIÓN DEL ARCHIVO WORD (.docx)
        # Solo procesamos si el usuario subió un archivo nuevo
        if archivo and archivo.filename != '':
            if not archivo.filename.endswith('.docx'):
                flash('Error: Solo se permiten archivos Word (.docx)', 'danger')
                return redirect(url_for('config_contratos_bp.listar'))

            nombre_seguro = secure_filename(archivo.filename)
            
            # Definimos la ruta: app/templates/docs/
            folder_path = os.path.join(current_app.root_path, 'templates', 'docs')
            os.makedirs(folder_path, exist_ok=True) 
            
            # Guardamos el archivo físico
            ruta_final = os.path.join(folder_path, nombre_seguro)
            archivo.save(ruta_final)
            
            # Actualizamos el nombre en la BD
            tipo.plantilla_word = nombre_seguro

        db.session.commit()
        flash(mensaje, 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al guardar: {str(e)}', 'danger')

    return redirect(url_for('config_contratos_bp.listar'))

@config_contratos_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    """
    Elimina un tipo de contrato. Esta es la función que faltaba y causaba el BuildError.
    """
    try:
        tipo = TipoContratoHonorario.query.get_or_404(id)
        
        # Opcional: Podrías verificar aquí si hay contratos usando este tipo antes de borrar
        # if tipo.contratos: ...
        
        db.session.delete(tipo)
        db.session.commit()
        flash('Tipo de contrato eliminado correctamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
        
    return redirect(url_for('config_contratos_bp.listar'))