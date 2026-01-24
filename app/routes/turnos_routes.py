from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models.turnos import HeJornadaBase, HeCalendarioEspecial
from app.services.turnos_service import TurnosService
from datetime import datetime

turnos_bp = Blueprint('turnos_bp', __name__, url_prefix='/configuracion/turnos')

# ==============================================================================
# 1. GESTIÓN DE JORNADAS BASE
# ==============================================================================
@turnos_bp.route('/')
def index():
    """Listado principal de reglas de jornada y feriados."""
    jornadas = HeJornadaBase.query.all()
    feriados = HeCalendarioEspecial.query.order_by(HeCalendarioEspecial.fecha.desc()).all()
    return render_template('turnos/index.html', jornadas=jornadas, feriados=feriados)

@turnos_bp.route('/jornada/nueva', methods=['POST'])
def crear_jornada():
    """Crea la cabecera de una nueva regla (General, Estamento o Funcionario)."""
    nombre = request.form.get('nombre')
    tipo = request.form.get('tipo_ambito')
    valor = request.form.get('valor_ambito')

    try:
        nueva = HeJornadaBase(
            nombre=nombre, 
            tipo_ambito=tipo, 
            valor_ambito=valor if valor and valor.strip() != "" else None
        )
        db.session.add(nueva)
        db.session.commit()
        flash(f"Jornada '{nombre}' creada. Proceda a configurar los horarios.", "success")
        return redirect(url_for('turnos_bp.configurar_detalle', id=nueva.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Error al crear jornada: {str(e)}", "danger")
        return redirect(url_for('turnos_bp.index'))

# ==============================================================================
# 2. CONFIGURACIÓN DE HORARIOS DIARIOS (LUNES A DOMINGO)
# ==============================================================================
@turnos_bp.route('/jornada/<int:id>/configurar', methods=['GET', 'POST'])
def configurar_detalle(id):
    """Interfaz para definir horas de entrada/salida de lunes a domingo."""
    jornada = HeJornadaBase.query.get_or_404(id)
    
    if request.method == 'POST':
        datos_semana = {}
        for dia in range(7):
            inicio = request.form.get(f'inicio_{dia}')
            termino = request.form.get(f'termino_{dia}')
            colacion = request.form.get(f'colacion_{dia}', 0)
            
            if inicio and termino:
                datos_semana[dia] = {
                    'inicio': inicio,
                    'termino': termino,
                    'colacion': colacion
                }
        
        # Uso del Service para persistencia transaccional
        exito, mensaje = TurnosService.guardar_horarios_semanales(id, datos_semana)
        
        if exito:
            flash(mensaje, "success")
            return redirect(url_for('turnos_bp.index'))
        else:
            flash(mensaje, "danger")

    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    detalles_dict = {d.dia_semana: d for d in jornada.detalles}
    
    return render_template('turnos/configurar_jornada.html', 
                           jornada=jornada, 
                           dias_nombres=dias_nombres,
                           detalles=detalles_dict)

# ==============================================================================
# 3. GESTIÓN DE CALENDARIO (FERIADOS)
# ==============================================================================
@turnos_bp.route('/calendario/agregar', methods=['POST'])
def agregar_feriado():
    """Registra un día como inhábil para el cálculo automático al 50%."""
    fecha_str = request.form.get('fecha')
    desc = request.form.get('descripcion')
    tipo = request.form.get('tipo_dia')
    irrenunciable = True if request.form.get('es_irrenunciable') else False

    try:
        nuevo_feriado = HeCalendarioEspecial(
            fecha=datetime.strptime(fecha_str, '%Y-%m-%d').date(),
            descripcion=desc,
            tipo_dia=tipo,
            es_irrenunciable=irrenunciable
        )
        db.session.add(nuevo_feriado)
        db.session.commit()
        flash("Día especial agregado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error: La fecha ya existe o es inválida.", "danger")
    
    return redirect(url_for('turnos_bp.index'))

@turnos_bp.route('/calendario/eliminar/<int:id>', methods=['POST'])
def eliminar_feriado(id):
    """Elimina un feriado del calendario."""
    feriado = HeCalendarioEspecial.query.get_or_404(id)
    try:
        db.session.delete(feriado)
        db.session.commit()
        flash("Fecha eliminada del calendario.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar: {str(e)}", "danger")
    return redirect(url_for('turnos_bp.index'))

# ==============================================================================
# 4. UTILIDADES
# ==============================================================================
@turnos_bp.route('/jornada/eliminar/<int:id>', methods=['POST'])
def eliminar_jornada(id):
    """Elimina una jornada base y sus detalles en cascada."""
    jornada = HeJornadaBase.query.get_or_404(id)
    try:
        db.session.delete(jornada)
        db.session.commit()
        flash("Jornada eliminada exitosamente.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar jornada: {str(e)}", "danger")
    return redirect(url_for('turnos_bp.index'))