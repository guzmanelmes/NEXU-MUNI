from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app, Response, make_response
from app.services.viaticos_service import ViaticosService
from app.models.contratos import AutoridadFirmante
from app.models.personas import Persona
from app.models.nombramientos import Nombramiento
import os

viaticos_bp = Blueprint('viaticos_bp', __name__, url_prefix='/viaticos')

# ==============================================================================
# GESTIÓN DE ESCALAS (Configuración)
# ==============================================================================

@viaticos_bp.route('/', methods=['GET'])
def listar_escala():
    try:
        escalas = ViaticosService.get_todas_escalas()
        return render_template('viaticos/create.html', escalas=escalas)
    except Exception as e:
        flash(f'Error al cargar escalas: {str(e)}', 'danger')
        return render_template('viaticos/create.html', escalas=[])

@viaticos_bp.route('/configurar', methods=['GET', 'POST'])
def configurar_escala():
    if request.method == 'POST':
        try:
            ViaticosService.crear_escala(request.form)
            flash('Nueva escala registrada. Las vigencias se han ajustado automáticamente.', 'success')
            return redirect(url_for('viaticos_bp.configurar_escala'))
        except ValueError as e:
            flash(f'Atención: {str(e)}', 'warning')
        except Exception as e:
            flash(f'Error crítico al guardar: {str(e)}', 'danger')
        return redirect(url_for('viaticos_bp.configurar_escala'))

    try:
        escalas = ViaticosService.get_todas_escalas()
    except:
        escalas = []
    return render_template('viaticos/create.html', escalas=escalas)

@viaticos_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_escala(id):
    try:
        if ViaticosService.eliminar_escala(id):
            flash('Registro eliminado y vigencias restauradas correctamente.', 'success')
        else:
            flash('No se encontró el registro a eliminar.', 'warning')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('viaticos_bp.configurar_escala'))

# ==============================================================================
# GESTIÓN DE DECRETOS DE VIÁTICOS
# ==============================================================================

@viaticos_bp.route('/decretos', methods=['GET'])
def listar_decretos():
    try:
        decretos = ViaticosService.get_decretos()
        return render_template('viaticos/index_decretos.html', decretos=decretos)
    except Exception as e:
        flash(f'Error al cargar historial: {str(e)}', 'danger')
        return render_template('viaticos/index_decretos.html', decretos=[])

@viaticos_bp.route('/decretos/nuevo', methods=['GET', 'POST'])
def nuevo_decreto():
    if request.method == 'POST':
        try:
            nuevo = ViaticosService.crear_decreto_viatico(request.form)
            flash(f'Decreto de Viático creado exitosamente (Monto: ${nuevo.monto_total_calculado:,}).', 'success')
            return redirect(url_for('viaticos_bp.listar_decretos'))
        except ValueError as ve:
            flash(f'Validación: {str(ve)}', 'warning')
        except Exception as e:
            flash(f'Error crítico al guardar viático: {str(e)}', 'danger')

    try:
        autoridades = AutoridadFirmante.query.all()
    except Exception as e:
        flash(f'Error cargando autoridades: {str(e)}', 'warning')
        autoridades = []

    return render_template('viaticos/create_decreto.html', autoridades=autoridades)

@viaticos_bp.route('/decretos/editar/<int:id>', methods=['GET', 'POST'])
def editar_decreto(id):
    if request.method == 'POST':
        try:
            actualizado = ViaticosService.actualizar_decreto_viatico(id, request.form)
            flash(f'Decreto #{id} actualizado. Nuevo Monto: ${actualizado.monto_total_calculado:,}', 'success')
            return redirect(url_for('viaticos_bp.listar_decretos'))
        except Exception as e:
            flash(f'Error al editar: {str(e)}', 'danger')
            return redirect(url_for('viaticos_bp.editar_decreto', id=id))

    try:
        decreto = ViaticosService.get_decreto_por_id(id)
        autoridades = AutoridadFirmante.query.all()
        return render_template('viaticos/edit_decreto.html', decreto=decreto, autoridades=autoridades)
    except Exception as e:
        flash(f'Error cargando decreto: {str(e)}', 'danger')
        return redirect(url_for('viaticos_bp.listar_decretos'))

# ==============================================================================
# GESTIÓN DE DOCUMENTOS (WORD / PDF)
# ==============================================================================

@viaticos_bp.route('/descargar_word/<int:id>')
def descargar_word(id):
    try:
        filename = ViaticosService.generar_word_decreto(id)
        return send_from_directory(
            directory=os.path.join(current_app.root_path, 'static', 'downloads'),
            path=filename,
            as_attachment=True
        )
    except FileNotFoundError:
        flash('Error: No se encuentra la plantilla base "plantilla_decreto_viatico.docx".', 'danger')
        return redirect(url_for('viaticos_bp.listar_decretos'))
    except Exception as e:
        flash(f'Error al generar documento: {str(e)}', 'danger')
        return redirect(url_for('viaticos_bp.listar_decretos'))

@viaticos_bp.route('/subir_pdf/<int:id>', methods=['POST'])
def subir_pdf(id):
    try:
        archivo = request.files.get('archivo_pdf')
        if archivo and archivo.filename != '':
            ViaticosService.subir_archivo_firmado(id, archivo)
            flash('Documento firmado subido correctamente. El decreto ahora está APROBADO.', 'success')
        else:
            flash('Debe seleccionar un archivo PDF válido.', 'warning')
    except Exception as e:
        flash(f'Error al subir archivo: {str(e)}', 'danger')
        
    return redirect(url_for('viaticos_bp.listar_decretos'))

@viaticos_bp.route('/ver_pdf/<filename>')
def ver_pdf(filename):
    try:
        return send_from_directory(
            directory=os.path.join(current_app.root_path, 'static', 'uploads', 'viaticos'),
            path=filename
        )
    except Exception as e:
        flash('El archivo no existe o fue eliminado.', 'danger')
        return redirect(url_for('viaticos_bp.listar_decretos'))

# ==============================================================================
# CARGA MASIVA (CSV)
# ==============================================================================

@viaticos_bp.route('/carga_masiva', methods=['GET', 'POST'])
def carga_masiva():
    """
    Procesa la carga masiva de decretos desde un archivo CSV.
    """
    if request.method == 'POST':
        archivo = request.files.get('archivo_csv')
        admin_id = request.form.get('admin_id')
        secretario_id = request.form.get('secretario_id')

        if not archivo or not admin_id or not secretario_id:
            flash('Debe seleccionar un archivo y ambas autoridades firmantes.', 'warning')
            return redirect(url_for('viaticos_bp.carga_masiva'))

        if not archivo.filename.endswith('.csv'):
            flash('Solo se permiten archivos CSV (.csv).', 'warning')
            return redirect(url_for('viaticos_bp.carga_masiva'))

        try:
            exitos, errores = ViaticosService.procesar_carga_masiva(archivo, admin_id, secretario_id)
            
            if exitos > 0:
                flash(f'Proceso finalizado. {exitos} decretos creados correctamente.', 'success')
            
            if errores:
                # Mostrar los primeros errores para no saturar la pantalla
                for err in errores[:5]:
                    flash(err, 'danger')
                if len(errores) > 5:
                    flash(f'... y {len(errores) - 5} errores más.', 'danger')

            return redirect(url_for('viaticos_bp.listar_decretos'))

        except Exception as e:
            flash(f'Error crítico en la carga masiva: {str(e)}', 'danger')
            return redirect(url_for('viaticos_bp.carga_masiva'))

    # GET: Mostrar formulario de carga
    try:
        autoridades = AutoridadFirmante.query.all()
    except:
        autoridades = []
    return render_template('viaticos/bulk_import.html', autoridades=autoridades)

@viaticos_bp.route('/plantilla_csv')
def descargar_plantilla_csv():
    """Descarga la plantilla CSV para la carga masiva."""
    try:
        csv_content = ViaticosService.generar_plantilla_csv()
        response = make_response(csv_content)
        response.headers["Content-Disposition"] = "attachment; filename=plantilla_viaticos.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
    except Exception as e:
        flash(f'Error generando plantilla: {str(e)}', 'danger')
        return redirect(url_for('viaticos_bp.carga_masiva'))

# ==============================================================================
# API JSON: BÚSQUEDA DE FUNCIONARIO
# ==============================================================================

@viaticos_bp.route('/api/buscar_funcionario/<path:rut>', methods=['GET'])
def buscar_funcionario_api(rut):
    try:
        rut_limpio = rut.upper().replace('.', '').replace('-', '')
        intentos = [rut, rut_limpio] 
        persona = None
        
        for intento in intentos:
            persona = Persona.query.filter_by(rut=intento).first()
            if not persona:
                persona = Persona.query.get(intento) 
            if persona: break

        if not persona:
            return jsonify({'encontrado': False})

        datos_contractuales = None
        nombramiento = Nombramiento.query.filter_by(
            persona_id=persona.rut, 
            estado='VIGENTE'
        ).order_by(Nombramiento.fecha_inicio.desc()).first()

        if nombramiento:
            estamento_bd = nombramiento.estamento.estamento.upper()
            mapa_estamentos = {
                'ALCALDES': 'ALCALDE', 'DIRECTIVOS': 'DIRECTIVO', 'PROFESIONALES': 'PROFESIONAL',
                'JEFATURAS': 'JEFATURA', 'TECNICOS': 'TECNICO', 'TÉCNICOS': 'TECNICO',
                'ADMINISTRATIVOS': 'ADMINISTRATIVO', 'AUXILIARES': 'AUXILIAR'
            }
            estamento_val = mapa_estamentos.get(estamento_bd, estamento_bd.rstrip('S'))

            datos_contractuales = {
                'grado': nombramiento.grado,
                'calidad': nombramiento.calidad_juridica,
                'estamento': estamento_val
            }

        return jsonify({
            'encontrado': True,
            'nombre_completo': f"{persona.nombres} {persona.apellido_paterno} {persona.apellido_materno}",
            'rut_formateado': persona.rut,
            'datos_contractuales': datos_contractuales
        })

    except Exception as e:
        print(f"Error API Viáticos (Buscar Funcionario): {str(e)}")
        return jsonify({'encontrado': False, 'error': str(e)})