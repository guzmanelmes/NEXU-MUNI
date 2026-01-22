from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from app.services.horas_extras_service import HorasExtrasService
from app.services.report_service import ReportService 
from app.models.contratos import AutoridadFirmante
from app.models.personas import Persona
from app.models.nombramientos import Nombramiento
from app.models.horas_extras import HeOrdenServicio 
from datetime import datetime
import json

he_bp = Blueprint('he_bp', __name__, url_prefix='/horas_extras')

# ==============================================================================
# 1. API: BÚSQUEDA DE DATOS
# ==============================================================================
@he_bp.route('/api/funcionario/<rut>')
def api_get_funcionario(rut):
    persona = Persona.query.get(rut)
    
    if not persona:
        return jsonify({'found': False, 'msg': f'RUT {rut} no encontrado en Personas.'})
    
    nombramiento = Nombramiento.query.filter_by(persona_id=rut, estado='VIGENTE').first()
    
    if not nombramiento:
        return jsonify({'found': False, 'msg': 'Persona encontrada, pero sin nombramiento vigente.'})

    return jsonify({
        'found': True,
        'nombre': f"{persona.nombres} {persona.apellido_paterno} {persona.apellido_materno}",
        'calidad': nombramiento.calidad_juridica,
        'grado': nombramiento.grado,
        'unidad': getattr(nombramiento, 'unidad_id', 'Sin asignar') 
    })


# ==============================================================================
# 2. CREAR SOLICITUD
# ==============================================================================
@he_bp.route('/solicitud/nueva', methods=['GET', 'POST'])
def create_solicitud():
    if request.method == 'POST':
        detalle_json = request.form.get('detalle_json') 
        if not detalle_json:
            flash('Error: Debe ingresar al menos una jornada.', 'danger')
            return redirect(request.referrer)

        datos_formulario = {
            'rut': request.form.get('rut_funcionario'),
            'numero_decreto': request.form.get('numero_decreto'),
            'fecha_decreto': request.form.get('fecha_decreto'),
            'id_firmante_alcalde': request.form.get('firmante_alcalde'),
            'id_firmante_secretario': request.form.get('firmante_secretario')
        }

        try:
            dias_lista = json.loads(detalle_json)
            exito, mensaje = HorasExtrasService.crear_solicitud_completa(datos_formulario, dias_lista)
            if exito:
                flash(mensaje, 'success')
                return redirect(url_for('he_bp.index')) 
            else:
                flash(mensaje, 'danger')
                return redirect(request.referrer)
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            return redirect(request.referrer)

    firmantes = AutoridadFirmante.query.all()
    return render_template('horas_extras/create_solicitud.html', firmantes=firmantes)


# ==============================================================================
# 3. EDITAR SOLICITUD
# ==============================================================================
@he_bp.route('/solicitud/editar/<int:id>', methods=['GET', 'POST'])
def edit_solicitud(id):
    orden = HeOrdenServicio.query.get_or_404(id)
    
    if request.method == 'POST':
        detalle_json = request.form.get('detalle_json')
        if not detalle_json:
            flash('Error: La planificación no puede estar vacía.', 'danger')
            return redirect(request.referrer)

        datos_formulario = {
            'numero_decreto': request.form.get('numero_decreto'),
            'fecha_decreto': request.form.get('fecha_decreto'),
            'id_firmante_alcalde': request.form.get('firmante_alcalde'),
            'id_firmante_secretario': request.form.get('firmante_secretario')
        }

        try:
            dias_lista = json.loads(detalle_json)
            exito, mensaje = HorasExtrasService.actualizar_solicitud(id, datos_formulario, dias_lista)
            
            if exito:
                flash(mensaje, 'success')
                return redirect(url_for('he_bp.index'))
            else:
                flash(mensaje, 'danger')
                return redirect(request.referrer)
        except Exception as e:
            flash(f'Error al procesar la actualización: {str(e)}', 'danger')
            return redirect(request.referrer)

    firmantes = AutoridadFirmante.query.all()
    return render_template('horas_extras/edit_solicitud.html', 
                           orden=orden, 
                           firmantes=firmantes)


# ==============================================================================
# 4. DETALLE DE SOLICITUD (PARA MODAL)
# ==============================================================================
@he_bp.route('/solicitud/detalle/<int:id>')
def obtener_detalle(id):
    """Retorna los datos de la orden y su planificación en JSON."""
    orden = HeOrdenServicio.query.get_or_404(id)
    
    planificacion = [{
        'fecha': p.fecha.strftime('%d-%m-%Y'),
        'horario': f"{p.hora_inicio.strftime('%H:%M')} - {p.hora_termino.strftime('%H:%M')}",
        'horas': f"{p.horas_estimadas:g}", # Formatea para quitar ceros innecesarios
        'tipo': p.tipo_jornada,
        'actividad': p.actividad_especifica,
        'vehiculo': f"Sí ({p.placa_patente})" if p.solicita_vehiculo else "No"
    } for p in orden.planificacion]

    return jsonify({
        'id': orden.id,
        'funcionario': f"{orden.funcionario.nombres} {orden.funcionario.apellido_paterno}",
        'rut': orden.rut_funcionario,
        'estado': orden.estado,
        'decreto': orden.decreto_auth.numero_decreto if orden.decreto_auth else "No asignado",
        'fecha_decreto': orden.decreto_auth.fecha_decreto.strftime('%d-%m-%Y') if (orden.decreto_auth and orden.decreto_auth.fecha_decreto) else "-",
        'planificacion': planificacion,
        'es_emergencia': orden.es_emergencia,
        'justificacion': orden.justificacion_emergencia
    })


# ==============================================================================
# 5. GENERACIÓN DE DOCUMENTO WORD
# ==============================================================================
@he_bp.route('/solicitud/descargar_word/<int:id>')
def descargar_word(id):
    orden = HeOrdenServicio.query.get_or_404(id)
    try:
        ruta_archivo = ReportService.generar_decreto_word(orden)
        rut_limpio = orden.rut_funcionario.replace('.', '').replace('-', '')
        nombre_descarga = f"Decreto_HE_{rut_limpio}_{datetime.now().strftime('%Y%m%d')}.docx"
        
        return send_file(
            ruta_archivo, 
            as_attachment=True, 
            download_name=nombre_descarga,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        flash(f"Error al generar el documento Word: {str(e)}", "danger")
        return redirect(url_for('he_bp.index'))


# ==============================================================================
# 6. DASHBOARD (VISTA PRINCIPAL)
# ==============================================================================
@he_bp.route('/')
def index():
    try:
        ordenes = HeOrdenServicio.query.order_by(HeOrdenServicio.created_at.desc()).all()
    except Exception as e:
        flash(f'Error al cargar listado: {str(e)}', 'danger')
        ordenes = []
        
    return render_template('horas_extras/dashboard.html', ordenes=ordenes)