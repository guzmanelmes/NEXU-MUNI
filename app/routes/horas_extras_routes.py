import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import extract, or_
from app.extensions import db
from app.services.horas_extras_service import HorasExtrasService
from app.services.report_service import ReportService 
from app.models.contratos import AutoridadFirmante
from app.models.personas import Persona
from app.models.nombramientos import Nombramiento
from app.models.horas_extras import HeOrdenServicio, HeConsolidadoMensual, HeDecreto, HePlanificacionDiaria
from datetime import datetime

he_bp = Blueprint('he_bp', __name__, url_prefix='/horas_extras')

# Configuración de subidas
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==============================================================================
# 1. API: BÚSQUEDA DE DATOS
# ==============================================================================
@he_bp.route('/api/funcionario/<rut>')
def api_get_funcionario(rut):
    persona = Persona.query.get(rut)
    if not persona:
        return jsonify({'found': False, 'msg': f'RUT {rut} no encontrado.'})
    
    nombramiento = Nombramiento.query.filter_by(persona_id=rut, estado='VIGENTE').first()
    if not nombramiento:
        return jsonify({'found': False, 'msg': 'Sin nombramiento vigente.'})

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
    return render_template('horas_extras/edit_solicitud.html', orden=orden, firmantes=firmantes)

# ==============================================================================
# 4. DETALLE DE SOLICITUD (PARA MODAL)
# ==============================================================================
@he_bp.route('/solicitud/detalle/<int:id>')
def obtener_detalle(id):
    orden = HeOrdenServicio.query.get_or_404(id)
    planificacion = [{
        'fecha': p.fecha.strftime('%d-%m-%Y'),
        'horario': f"{p.hora_inicio.strftime('%H:%M')} - {p.hora_termino.strftime('%H:%M')}",
        'horas': f"{p.horas_estimadas:g}",
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
        'justificacion': orden.justificacion_emergencia,
        'archivo_digital': orden.decreto_auth.archivo_digital if orden.decreto_auth else None
    })

# ==============================================================================
# 5. ACTUALIZAR DECRETO Y SUBIR PDF ESCANEADO
# ==============================================================================
@he_bp.route('/solicitud/subir_decreto/<int:id>', methods=['POST'])
def subir_decreto(id):
    orden = HeOrdenServicio.query.get_or_404(id)
    decreto = orden.decreto_auth
    
    if not decreto:
        flash("Error: No existe un decreto asociado a esta orden.", "danger")
        return redirect(url_for('he_bp.index'))

    nuevo_numero = request.form.get('numero_decreto')
    archivo = request.files.get('archivo_pdf')

    try:
        if nuevo_numero:
            decreto.numero_decreto = nuevo_numero

        if archivo and archivo.filename != '':
            if allowed_file(archivo.filename):
                filename = secure_filename(f"decreto_firmado_{id}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf")
                upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'decretos')
                
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)
                
                archivo.save(os.path.join(upload_path, filename))
                decreto.archivo_digital = filename
                decreto.estado = 'TRAMITADO'
            else:
                flash("Error: El archivo debe ser un PDF.", "danger")
                return redirect(url_for('he_bp.index'))

        db.session.commit()
        flash("Decreto actualizado y archivo cargado exitosamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al procesar el decreto: {str(e)}", "danger")

    return redirect(url_for('he_bp.index'))

# ==============================================================================
# 6. GENERACIÓN DE DOCUMENTO WORD (SOLICITUD)
# ==============================================================================
@he_bp.route('/solicitud/descargar_word/<int:id>')
def descargar_word(id):
    orden = HeOrdenServicio.query.get_or_404(id)
    try:
        ruta_archivo = ReportService.generar_decreto_word(orden)
        rut_limpio = orden.rut_funcionario.replace('.', '').replace('-', '')
        nombre_descarga = f"Decreto_HE_{rut_limpio}_{datetime.now().strftime('%Y%m%d')}.docx"
        return send_file(ruta_archivo, as_attachment=True, download_name=nombre_descarga)
    except Exception as e:
        flash(f"Error al generar el documento Word: {str(e)}", "danger")
        return redirect(url_for('he_bp.index'))

# ==============================================================================
# 7. DASHBOARD (VISTA PRINCIPAL)
# ==============================================================================
@he_bp.route('/')
def index():
    try:
        ordenes = HeOrdenServicio.query.order_by(HeOrdenServicio.created_at.desc()).all()
    except Exception as e:
        flash(f'Error al cargar listado: {str(e)}', 'danger')
        ordenes = []
    return render_template('horas_extras/dashboard.html', ordenes=ordenes)

# ==============================================================================
# 8. API DE ASISTENCIA ("TAREO")
# ==============================================================================
@he_bp.route('/api/asistencia/<rut>/<int:anio>/<int:mes>')
def obtener_asistencia_mensual(rut, anio, mes):
    """Devuelve el detalle día a día para mostrar en el modal."""
    dias = db.session.query(HePlanificacionDiaria).join(HeOrdenServicio).join(HeDecreto).filter(
        HeOrdenServicio.rut_funcionario == rut,
        extract('month', HeDecreto.fecha_decreto) == mes,
        extract('year', HeDecreto.fecha_decreto) == anio,
        HeDecreto.estado.in_(['FIRMADO', 'TRAMITADO'])
    ).order_by(HePlanificacionDiaria.fecha).all()

    resultado = []
    for d in dias:
        h_real = d.horas_reales if d.horas_reales is not None else d.horas_estimadas
        resultado.append({
            'id': d.id,
            'fecha': d.fecha.strftime('%d-%m-%Y'),
            'dia_nombre': d.fecha.strftime('%A'), 
            'inicio': d.hora_inicio.strftime('%H:%M'),
            'termino': d.hora_termino.strftime('%H:%M'),
            'tipo': d.tipo_jornada, 
            'horas_plan': float(d.horas_estimadas),
            'horas_real': float(h_real),
            'actividad': d.actividad_especifica
        })
    return jsonify(resultado)

@he_bp.route('/gestion-mensual/guardar-asistencia', methods=['POST'])
def guardar_asistencia():
    """Guarda las horas reales editadas desde el modal."""
    try:
        data = request.json
        items = data.get('cambios', [])
        rut_funcionario = data.get('rut')
        mes = data.get('mes')
        anio = data.get('anio')

        for item in items:
            plan_id = item['id']
            try:
                horas_nuevas = float(item['valor'])
            except (ValueError, TypeError):
                continue
            
            registro = HePlanificacionDiaria.query.get(plan_id)
            if registro:
                registro.horas_reales = horas_nuevas
        
        db.session.commit()
        
        # Recalcular inmediatamente
        HorasExtrasService.calcular_valores_mes(rut_funcionario, int(anio), int(mes))
        return jsonify({'status': 'ok', 'msg': 'Asistencia actualizada y montos recalculados.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@he_bp.route('/procesar-calculo/<rut>', methods=['POST'])
def procesar_calculo_funcionario(rut):
    """Gatilla el cálculo financiero para un funcionario específico."""
    try:
        anio = int(request.form.get('anio'))
        mes = int(request.form.get('mes'))
        exito, msg = HorasExtrasService.calcular_valores_mes(rut, anio, mes)
        if exito:
            flash(msg, "success")
        else:
            flash(f"Error: {msg}", "danger")
        return redirect(url_for('he_bp.gestion_mensual', mes=mes, anio=anio))
    except ValueError:
        flash("Error: Datos de periodo inválidos.", "danger")
        return redirect(url_for('he_bp.index'))

@he_bp.route('/gestion-mensual/actualizar', methods=['POST'])
def actualizar_consolidado():
    """Recibe la edición manual de horas a pagar vs compensar."""
    try:
        rut = request.form.get('rut_funcionario')
        anio = int(request.form.get('anio'))
        mes = int(request.form.get('mes'))
        
        h_pagar_25 = request.form.get('horas_pagar_25', '0').replace(',', '.')
        h_pagar_50 = request.form.get('horas_pagar_50', '0').replace(',', '.')
        h_comp_25 = request.form.get('horas_compensar_25', '0').replace(',', '.')
        h_comp_50 = request.form.get('horas_compensar_50', '0').replace(',', '.')

        consolidado = HeConsolidadoMensual.query.filter_by(
            rut_funcionario=rut, anio=anio, mes=mes
        ).first()

        if not consolidado:
            flash("Error: No se encontró el registro para editar.", "danger")
            return redirect(url_for('he_bp.gestion_mensual', mes=mes, anio=anio))

        consolidado.horas_a_pagar_25 = float(h_pagar_25)
        consolidado.horas_a_pagar_50 = float(h_pagar_50)
        consolidado.horas_compensar_25 = float(h_comp_25)
        consolidado.horas_compensar_50 = float(h_comp_50)
        
        consolidado.calcular_montos_dinero()
        consolidado.estado = 'REVISADO'
        db.session.commit()
        flash("Distribución de horas actualizada correctamente.", "success")

    except ValueError:
        flash("Error: Ingrese valores numéricos válidos.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error técnico al actualizar: {str(e)}", "danger")

    return redirect(url_for('he_bp.gestion_mensual', mes=mes, anio=anio))

# ==============================================================================
# 9. GESTIÓN MENSUAL (VISTA + HISTORIAL + FIRMANTES)
# ==============================================================================
@he_bp.route('/gestion-mensual')
def gestion_mensual():
    """Vista principal para RRHH."""
    anio = int(request.args.get('anio', datetime.now().year))
    mes = int(request.args.get('mes', datetime.now().month))
    
    # 1. Datos consolidados del mes
    consolidados = HeConsolidadoMensual.query.filter_by(anio=anio, mes=mes).all()
    ruts_calculados = [c.rut_funcionario for c in consolidados]

    # 2. Pendientes de cálculo
    pendientes = db.session.query(
        HeOrdenServicio.rut_funcionario, 
        Persona.nombres, 
        Persona.apellido_paterno,
        Persona.apellido_materno
    ).join(Persona).join(HeOrdenServicio.decreto_auth).filter(
        extract('month', HeDecreto.fecha_decreto) == mes,
        extract('year', HeDecreto.fecha_decreto) == anio,
        HeDecreto.estado.in_(['FIRMADO', 'TRAMITADO']), 
        HeOrdenServicio.rut_funcionario.notin_(ruts_calculados)
    ).distinct().all()
    
    # 3. Firmantes para el Modal
    firmantes = AutoridadFirmante.query.all()

    # 4. Historial de decretos de pago generados este mes (Para no perderlos)
    historial_decretos = HeDecreto.query.filter(
        HeDecreto.tipo_decreto == 'PAGO',
        extract('year', HeDecreto.fecha_decreto) == anio,
        extract('month', HeDecreto.fecha_decreto) == mes
    ).order_by(HeDecreto.id.desc()).all()

    return render_template('horas_extras/gestion_mensual.html', 
                           consolidados=consolidados, 
                           pendientes=pendientes,
                           mes_actual=mes, 
                           anio_actual=anio,
                           firmantes=firmantes,
                           historial_decretos=historial_decretos)

@he_bp.route('/gestion-mensual/generar-decreto', methods=['POST'])
def generar_decreto_pago():
    """Genera el Decreto Masivo con datos MANUALES y guarda referencia."""
    try:
        anio = int(request.form.get('anio'))
        mes = int(request.form.get('mes'))
        
        # DATOS MANUALES DEL MODAL
        num_decreto = request.form.get('numero_decreto')
        fec_decreto_str = request.form.get('fecha_decreto')
        id_alcalde = request.form.get('id_firmante_alcalde')
        id_secretario = request.form.get('id_firmante_secretario')

        if not fec_decreto_str or not id_alcalde or not id_secretario:
            flash("Error: Faltan datos para generar el decreto.", "danger")
            return redirect(url_for('he_bp.gestion_mensual', mes=mes, anio=anio))

        fec_decreto_obj = datetime.strptime(fec_decreto_str, '%Y-%m-%d').date()

        # Buscar items a pagar
        consolidados = HeConsolidadoMensual.query.filter(
            HeConsolidadoMensual.anio == anio,
            HeConsolidadoMensual.mes == mes,
            HeConsolidadoMensual.monto_total_pagar > 0,
            HeConsolidadoMensual.estado.in_(['CALCULADO', 'REVISADO', 'EN_DECRETO']) 
        ).all()

        if not consolidados:
            flash("No hay registros calculados con monto a pagar.", "warning")
            return redirect(url_for('he_bp.gestion_mensual', mes=mes, anio=anio))

        # Crear Decreto (PAGO)
        nuevo_decreto = HeDecreto(
            tipo_decreto='PAGO',
            numero_decreto=num_decreto, 
            fecha_decreto=fec_decreto_obj, 
            descripcion=f"PAGO HORAS EXTRAS {mes}/{anio}",
            id_firmante_alcalde=id_alcalde, 
            id_firmante_secretario=id_secretario, 
            estado='BORRADOR'
        )
        db.session.add(nuevo_decreto)
        db.session.flush()

        for item in consolidados:
            item.id_decreto_pago = nuevo_decreto.id
            item.estado = 'EN_DECRETO'
        
        # Generar Word Físico
        path_archivo = ReportService.generar_nomina_pago_word(anio, mes, consolidados, nuevo_decreto)
        
        # Guardar nombre de archivo en BD para el historial
        nombre_archivo = os.path.basename(path_archivo)
        nuevo_decreto.archivo_digital = nombre_archivo
        
        db.session.commit()

        # Descargar
        return send_file(path_archivo, as_attachment=True, download_name=nombre_archivo)

    except Exception as e:
        db.session.rollback()
        flash(f"Error al generar el decreto: {str(e)}", "danger")
        return redirect(url_for('he_bp.gestion_mensual', mes=mes, anio=anio))