from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.services.programas_service import ProgramasService
from app.models.programas import Programa, CuentaPresupuestaria
from app.models.contratos import ContratoHonorario

# Definimos el Blueprint
programas_bp = Blueprint('programas_bp', __name__, url_prefix='/programas')

# --------------------------------------------------------------------------
# 1. LISTADO (INDEX)
# --------------------------------------------------------------------------
@programas_bp.route('/', methods=['GET'])
def listar():
    """
    Lista todos los programas presupuestarios existentes.
    Renderiza: programas/index.html
    """
    try:
        # Obtenemos todos los programas ordenados por fecha de decreto (más reciente primero)
        programas = Programa.query.order_by(Programa.fecha_decreto.desc()).all()
        return render_template('programas/index.html', programas=programas)
    except Exception as e:
        flash(f'Error al cargar programas: {str(e)}', 'danger')
        return render_template('programas/index.html', programas=[])

# --------------------------------------------------------------------------
# 2. CREAR NUEVO PROGRAMA
# --------------------------------------------------------------------------
@programas_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo_programa():
    """
    Crea un nuevo programa presupuestario junto con sus cuentas iniciales.
    """
    if request.method == 'POST':
        try:
            # 1. Recopilar datos básicos del Programa
            data_prog = {
                'nombre': request.form.get('nombre'),
                'numero_decreto': request.form.get('numero_decreto'),
                'fecha_decreto': request.form.get('fecha_decreto')
            }

            # 2. Recopilar y estructurar las Cuentas Presupuestarias
            codigos = request.form.getlist('cuenta_codigo[]')
            montos = request.form.getlist('cuenta_monto[]')
            
            lista_cuentas = []
            
            for codigo, monto in zip(codigos, montos):
                if codigo.strip() and monto.strip():
                    lista_cuentas.append({
                        'codigo': codigo.strip(),
                        'monto': int(monto)
                    })

            if not lista_cuentas:
                raise ValueError("Debe ingresar al menos una cuenta presupuestaria.")

            # 3. Guardar usando el servicio (Transacción Atómica)
            ProgramasService.crear_programa(data_prog, lista_cuentas)

            flash('Programa Presupuestario creado correctamente.', 'success')
            return redirect(url_for('programas_bp.listar'))
            
        except ValueError as ve:
            flash(f'Error de validación: {str(ve)}', 'warning')
        except Exception as e:
            flash(f'Error crítico al guardar: {str(e)}', 'danger')

    return render_template('programas/create.html')

# --------------------------------------------------------------------------
# 3. VER DETALLE (CARTOLA)
# --------------------------------------------------------------------------
@programas_bp.route('/ver/<int:id>', methods=['GET'])
def ver_programa(id):
    """
    Muestra el detalle financiero del programa (La Cartola) y su historial.
    """
    try:
        programa = Programa.query.get_or_404(id)
        # Buscamos los contratos asociados para mostrar el historial de gastos
        contratos = ContratoHonorario.query.filter_by(programa_id=id).order_by(ContratoHonorario.fecha_inicio.desc()).all()
        
        return render_template('programas/show.html', programa=programa, contratos=contratos)
    except Exception as e:
        flash(f'Error al cargar el programa: {str(e)}', 'danger')
        return redirect(url_for('programas_bp.listar'))

# --------------------------------------------------------------------------
# 4. EDITAR PROGRAMA
# --------------------------------------------------------------------------
@programas_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_programa(id):
    """
    Edita datos básicos. Si se agregan cuentas nuevas:
    - Si el código YA existe: Se SUPLEMENTA (suma al saldo existente).
    - Si el código NO existe: Se CREA la cuenta nueva.
    """
    programa = Programa.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # 1. Actualizar datos de cabecera (Nombre, Decreto, Fecha)
            programa.nombre = request.form.get('nombre')
            programa.numero_decreto = request.form.get('numero_decreto')
            programa.fecha_decreto = request.form.get('fecha_decreto')
            
            # 2. Procesar SUPLEMENTACIONES O NUEVAS CUENTAS
            codigos_nuevos = request.form.getlist('cuenta_codigo_nueva[]')
            montos_nuevos = request.form.getlist('cuenta_monto_nueva[]')
            
            cuentas_procesadas = 0
            
            for codigo, monto in zip(codigos_nuevos, montos_nuevos):
                codigo_limpio = codigo.strip()
                # Convertimos a int asegurando que no falle si viene vacío
                monto_int = int(monto) if monto.strip() else 0
                
                if codigo_limpio and monto_int > 0:
                    # BUSCAR SI YA EXISTE ESE CÓDIGO EN ESTE PROGRAMA
                    cuenta_existente = CuentaPresupuestaria.query.filter_by(
                        programa_id=programa.id, 
                        codigo=codigo_limpio
                    ).first()
                    
                    if cuenta_existente:
                        # CASO A: SUPLEMENTACIÓN (El código ya existía)
                        # Le sumamos la plata a lo que ya tenía
                        cuenta_existente.monto_inicial += monto_int
                        cuenta_existente.saldo_actual += monto_int
                        flash(f'Se suplementó la cuenta {codigo_limpio} con ${monto_int:,.0f}', 'info')
                    else:
                        # CASO B: CUENTA NUEVA (El código no existía)
                        nueva_cuenta = CuentaPresupuestaria(
                            programa_id=programa.id,
                            codigo=codigo_limpio,
                            monto_inicial=monto_int,
                            saldo_actual=monto_int
                        )
                        db.session.add(nueva_cuenta)
                        flash(f'Se creó la nueva cuenta {codigo_limpio}', 'success')
                    
                    cuentas_procesadas += 1
            
            db.session.commit()
            
            if cuentas_procesadas == 0:
                flash('Datos básicos actualizados correctamente.', 'success')
            
            return redirect(url_for('programas_bp.ver_programa', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')

    return render_template('programas/edit.html', programa=programa)

# --------------------------------------------------------------------------
# 5. ELIMINAR PROGRAMA
# --------------------------------------------------------------------------
@programas_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_programa(id):
    """
    Elimina un programa SOLO si no tiene contratos asociados.
    """
    try:
        programa = Programa.query.get_or_404(id)
        
        # Validación de seguridad: Verificar si hay contratos usando este dinero
        contratos_asociados = ContratoHonorario.query.filter_by(programa_id=id).count()
        if contratos_asociados > 0:
            flash(f'No se puede eliminar: El programa tiene {contratos_asociados} contratos vigentes asociados.', 'warning')
            return redirect(url_for('programas_bp.listar'))

        db.session.delete(programa)
        db.session.commit()
        flash('Programa eliminado correctamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
        
    return redirect(url_for('programas_bp.listar'))