from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.contratos import AutoridadFirmante 
from app.extensions import db

autoridades_bp = Blueprint('autoridades_bp', __name__, url_prefix='/config/autoridades')

@autoridades_bp.route('/')
def listar():
    """Lista todos los firmantes registrados en el catálogo de roles."""
    autoridades = AutoridadFirmante.query.all()
    return render_template('config/autoridades/index.html', autoridades=autoridades)

@autoridades_bp.route('/nueva', methods=['GET', 'POST'])
def nueva():
    """
    Registra un nuevo rol de firmante. 
    Permite que un mismo RUT tenga múltiples cargos (Alcalde y Secretario).
    """
    if request.method == 'POST':
        try:
            # Captura del RUT validado en el catálogo de personas
            rut_autoridad = request.form.get('rut_filtro')
            cargo_solicitado = request.form.get('cargo')
            
            # VALIDACIÓN DE DUALIDAD:
            # Solo bloqueamos si el RUT ya tiene asignado EXACTAMENTE el mismo cargo.
            # Esto permite que un RUT sea Alcalde y Secretario a la vez en registros distintos.
            existe_rol = AutoridadFirmante.query.filter_by(
                rut=rut_autoridad, 
                cargo=cargo_solicitado
            ).first()

            if existe_rol:
                flash(f'La persona con RUT {rut_autoridad} ya está configurada como {cargo_solicitado}.', 'warning')
                return redirect(url_for('autoridades_bp.nueva'))

            # Creación del registro basado en el modelo actualizado
            # Se omite el campo 'nombre' ya que se obtiene vía relación con Persona.
            nueva_aut = AutoridadFirmante(
                rut=rut_autoridad, 
                cargo=cargo_solicitado,
                es_subrogante='es_subrogante' in request.form,
                decreto_nombramiento=request.form.get('decreto'),
                firma_linea_1=request.form.get('linea1'),
                firma_linea_2=request.form.get('linea2'),
                firma_linea_3=request.form.get('linea3'),
                firma_linea_4=request.form.get('linea4')
            )
            
            db.session.add(nueva_aut)
            db.session.commit()
            flash(f'Rol de {cargo_solicitado} vinculado exitosamente.', 'success')
            return redirect(url_for('autoridades_bp.listar'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar el registro: {str(e)}', 'danger')
            
    return render_template('config/autoridades/create.html')