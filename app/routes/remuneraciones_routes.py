# app/routes/remuneraciones_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.services.remuneraciones_service import RemuneracionesService
from app.services.catalogos_service import CatalogosService
from app.models.remuneraciones import ConfigTipoHaberes
from app.models.catalogos import CatEstamentos 

remuneraciones_bp = Blueprint('remuneraciones_bp', __name__, url_prefix='/remuneraciones')

# =======================================================
# DASHBOARD PRINCIPAL Y ACCIONES MASIVAS
# =======================================================

@remuneraciones_bp.route('/')
def index():
    fechas = RemuneracionesService.get_fechas_disponibles()
    estamentos = CatalogosService.get_estamentos()
    return render_template('remuneraciones/dashboard.html', fechas=fechas, estamentos=estamentos)

@remuneraciones_bp.route('/generar_plantilla', methods=['POST'])
def generar_plantilla():
    try:
        fecha = request.form.get('fecha_inicio')
        estamento_id = request.form.get('estamento_id') 
        
        if not fecha:
            flash('Debe seleccionar una fecha de inicio.', 'warning')
            return redirect(url_for('remuneraciones_bp.index'))

        if estamento_id:
            cnt = RemuneracionesService.generar_plantilla_vacia(fecha, estamento_id)
        else:
            cnt = 0
            todos = CatalogosService.get_estamentos()
            for est in todos:
                cnt += RemuneracionesService.generar_plantilla_vacia(fecha, est.id)

        flash(f'Proceso completado. Se generaron {cnt} filas listas para llenar.', 'success')
        return redirect(url_for('remuneraciones_bp.ver_matriz', fecha_vigencia=fecha))
        
    except Exception as e:
        flash(f'Error al generar plantilla: {str(e)}', 'danger')
        return redirect(url_for('remuneraciones_bp.index'))

@remuneraciones_bp.route('/clonar_periodo', methods=['POST'])
def clonar_periodo():
    try:
        origen = request.form.get('fecha_origen')
        destino = request.form.get('fecha_destino')
        pct = request.form.get('porcentaje', 0)
        
        g_min = request.form.get('grado_min', 1)
        g_max = request.form.get('grado_max', 30)
        
        if not origen or not destino:
            flash('Debe seleccionar fecha de origen y destino.', 'warning')
            return redirect(url_for('remuneraciones_bp.index'))

        cnt = RemuneracionesService.clonar_periodo(
            origen, 
            destino, 
            float(pct),
            int(g_min),
            int(g_max)
        )
        
        flash(f'Proceso exitoso. Se clonaron {cnt} registros (Reajuste del {pct}% aplicado solo entre grados {g_min} y {g_max}).', 'success')
        return redirect(url_for('remuneraciones_bp.ver_matriz', fecha_vigencia=destino))
        
    except Exception as e:
        flash(f'Error al clonar periodo: {str(e)}', 'danger')
        return redirect(url_for('remuneraciones_bp.index'))

@remuneraciones_bp.route('/eliminar_periodo', methods=['POST'])
def eliminar_periodo():
    try:
        fecha = request.form.get('fecha_vigencia')
        if not fecha:
            flash('Error: Fecha no especificada.', 'danger')
            return redirect(url_for('remuneraciones_bp.index'))
            
        cnt = RemuneracionesService.eliminar_periodo(fecha)
        flash(f'Se eliminaron {cnt} registros de la fecha {fecha}.', 'warning')
        
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')
        
    return redirect(url_for('remuneraciones_bp.index'))


# =======================================================
# MÉTODOS ANTERIORES (COMPATIBILIDAD)
# =======================================================

@remuneraciones_bp.route('/nueva', methods=['GET', 'POST'])
def crear_escala():
    estamentos = CatalogosService.get_estamentos()
    haberes = RemuneracionesService.get_haberes()

    if request.method == 'POST':
        try:
            data_header = {
                'fecha_vigencia': request.form.get('fecha_vigencia'),
                'estamento_id': request.form.get('estamento_id'),
                'grado': request.form.get('grado'),
                'sueldo_base': 0 
            }
            lista_montos = []
            for h in haberes:
                input_name = f"monto_{h.id}"
                valor = request.form.get(input_name)
                if valor and int(valor) > 0:
                    lista_montos.append({'haber_id': h.id, 'monto': valor})
                    if h.codigo == 'SUELDO_BASE':
                        data_header['sueldo_base'] = valor

            RemuneracionesService.crear_escala(data_header, lista_montos)
            flash('Escala de remuneraciones creada correctamente.', 'success')
            return redirect(url_for('remuneraciones_bp.index'))
        except Exception as e:
            flash(f'Error al guardar: {str(e)}', 'danger')

    return render_template('remuneraciones/create.html', estamentos=estamentos, haberes=haberes)

# =======================================================
# GESTIÓN DE CATÁLOGO DE HABERES
# =======================================================

@remuneraciones_bp.route('/haberes', methods=['GET', 'POST'])
def gestionar_haberes():
    estamentos = CatalogosService.get_estamentos()

    if request.method == 'POST':
        try:
            codigo = request.form.get('codigo').upper().strip()
            nombre = request.form.get('nombre').strip()
            formula = request.form.get('formula', '').strip()
            
            es_manual = True if request.form.get('es_manual') else False
            es_permanente = True if request.form.get('es_permanente') else False 
            es_visible_matriz = True if request.form.get('es_visible_matriz') else False 
            
            estamentos_ids = request.form.getlist('estamentos_seleccionados')

            # Validación de fórmula
            if not es_manual and formula:
                try:
                    variables_prueba = {
                        'SUELDO_BASE': 100000,
                        'ASIG_MUN': 10000,
                        'ASIG_ZONA': 5000,
                        'ASIG_PROF': 20000
                    }
                    eval(formula, {"__builtins__": None}, variables_prueba)
                except SyntaxError:
                    flash('Error de sintaxis en la fórmula. Verifique paréntesis y operadores.', 'danger')
                    return redirect(url_for('remuneraciones_bp.gestionar_haberes'))
                except ZeroDivisionError:
                    flash('Error: La fórmula implica una división por cero.', 'danger')
                    return redirect(url_for('remuneraciones_bp.gestionar_haberes'))
                except Exception as e:
                    flash(f'Advertencia en fórmula: {str(e)}. Verifique los códigos.', 'warning')

            # Guardado
            haber = ConfigTipoHaberes.query.filter_by(codigo=codigo).first()
            if not haber:
                haber = ConfigTipoHaberes(codigo=codigo)
                db.session.add(haber)
            
            haber.nombre = nombre
            haber.es_manual = es_manual
            haber.es_permanente = es_permanente 
            haber.es_visible_matriz = es_visible_matriz 
            haber.formula = formula

            haber.estamentos_habilitados = [] 
            for eid in estamentos_ids:
                est = CatEstamentos.query.get(eid)
                if est:
                    haber.estamentos_habilitados.append(est)
            
            db.session.commit()
            flash(f'Haber "{nombre}" guardado correctamente.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar haber: {str(e)}', 'danger')
        
        return redirect(url_for('remuneraciones_bp.gestionar_haberes'))

    haberes = RemuneracionesService.get_haberes()
    return render_template('remuneraciones/manage_haberes.html', haberes=haberes, estamentos=estamentos)

# =======================================================
# TABLA MAESTRA UNIFICADA (VISTA CONTRALORÍA)
# =======================================================

@remuneraciones_bp.route('/matriz/<string:fecha_vigencia>', methods=['GET', 'POST'])
def ver_matriz(fecha_vigencia):
    if request.method == 'POST':
        try:
            RemuneracionesService.guardar_matriz_unificada(fecha_vigencia, request.form)
            flash('Sueldos actualizados correctamente (cambio aplicado a todos los estamentos del grado).', 'success')
        except Exception as e:
            flash(f'Error al actualizar la matriz: {str(e)}', 'danger')
        return redirect(url_for('remuneraciones_bp.ver_matriz', fecha_vigencia=fecha_vigencia))

    haberes_cols, filas = RemuneracionesService.obtener_matriz_unificada(fecha_vigencia)
    return render_template('remuneraciones/matriz.html', 
                           fecha_vigencia=fecha_vigencia,
                           haberes_cols=haberes_cols,
                           filas=filas)

# --- REAJUSTE DIFERENCIADO ---
@remuneraciones_bp.route('/reajuste_diferenciado', methods=['POST'])
def reajuste_diferenciado():
    try:
        fecha = request.form.get('fecha_vigencia')
        pct = request.form.get('porcentaje')
        g_min = request.form.get('grado_min')
        g_max = request.form.get('grado_max')

        if not fecha or not pct or not g_min or not g_max:
            flash('Faltan datos para realizar el ajuste.', 'warning')
            return redirect(url_for('remuneraciones_bp.ver_matriz', fecha_vigencia=fecha))

        cnt = RemuneracionesService.aplicar_reajuste_diferenciado(
            fecha, float(pct), int(g_min), int(g_max)
        )

        if cnt > 0:
            flash(f'Reajuste del {pct}% aplicado correctamente a {cnt} registros (Grados {g_min} al {g_max}).', 'success')
        else:
            flash('No se encontraron grados en el rango seleccionado para ajustar.', 'warning')

    except Exception as e:
        flash(f'Error al procesar reajuste: {str(e)}', 'danger')

    return redirect(url_for('remuneraciones_bp.ver_matriz', fecha_vigencia=fecha))

# --- SIMULADOR ---
@remuneraciones_bp.route('/simulador')
def simulador():
    fechas = RemuneracionesService.get_fechas_disponibles()
    estamentos = CatalogosService.get_estamentos()
    fecha_actual = fechas[0] if fechas else None
    return render_template('remuneraciones/simulador.html', 
                           fechas=fechas, 
                           estamentos=estamentos,
                           fecha_actual=fecha_actual)

@remuneraciones_bp.route('/api/valores_grado', methods=['POST'])
def api_valores_grado():
    try:
        data = request.get_json()
        fecha = data.get('fecha')
        grado = data.get('grado')
        estamento_id = data.get('estamento_id') 
        
        if not fecha or not grado or not estamento_id:
            return {'error': 'Faltan datos (Fecha, Grado o Estamento)'}, 400

        resultado = RemuneracionesService.obtener_datos_simulacion(fecha, grado, estamento_id)
        
        if 'error' in resultado:
            return resultado, 400
            
        return resultado, 200
    except Exception as e:
        return {'error': str(e)}, 500

# --- ACTUALIZAR FECHA VIGENCIA ---
@remuneraciones_bp.route('/actualizar_fecha_vigencia', methods=['POST'])
def actualizar_fecha_vigencia():
    try:
        fecha_actual = request.form.get('fecha_actual')       # ID original
        fecha_nueva_inicio = request.form.get('fecha_inicio') # Nuevo Inicio
        fecha_nueva_fin = request.form.get('fecha_fin')       # Nuevo Fin (puede ser vacío)
        
        if not fecha_actual or not fecha_nueva_inicio:
            flash('Error: La fecha de inicio es obligatoria.', 'warning')
            return redirect(url_for('remuneraciones_bp.index'))
            
        # Llamamos al servicio con los 3 parámetros
        cnt = RemuneracionesService.actualizar_fecha_masiva(fecha_actual, fecha_nueva_inicio, fecha_nueva_fin)
        
        flash(f'Vigencia actualizada correctamente ({cnt} registros modificados).', 'success')
        
    except Exception as e:
        flash(f'Error al actualizar vigencia: {str(e)}', 'danger')
        
    return redirect(url_for('remuneraciones_bp.index'))