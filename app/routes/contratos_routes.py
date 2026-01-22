from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from werkzeug.utils import secure_filename
from app.services.contratos_service import ContratosService
from app.models.contratos import ContratoHonorario, TipoContratoHonorario, AutoridadFirmante
from app.models.programas import Programa
from app.models.personas import Persona
from app.extensions import db
import os
import csv
import io

# Definimos el Blueprint
contratos_bp = Blueprint('contratos_bp', __name__, url_prefix='/contratos')

# Configuración de archivos permitidos
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@contratos_bp.route('/', methods=['GET'])
def listar():
    """
    Lista todos los contratos existentes.
    Renderiza: contratos/index.html
    """
    try:
        # Ordenamos por ID descendente (lo último creado primero)
        contratos = ContratoHonorario.query.order_by(ContratoHonorario.id.desc()).all()
        return render_template('contratos/index.html', contratos=contratos)
    except Exception as e:
        flash(f'Error al cargar contratos: {str(e)}', 'danger')
        return render_template('contratos/index.html', contratos=[])

@contratos_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo_contrato():
    """
    Gestión de Contratos Honorarios (Creación).
    Procesa el formulario complejo:
    1. Datos básicos.
    2. Horarios.
    3. JSON oculto con el detalle financiero (Cuotas y Distribución).
    """
    if request.method == 'POST':
        try:
            # 1. Captura todo el formulario (incluyendo el input hidden 'json_detalle_completo')
            data = request.form.to_dict()
            
            # 2. Captura de listas explícitas (Funciones)
            data['funciones'] = request.form.getlist('funciones[]')
            
            # 3. Procesar Horario (Estructura de Diccionario compleja)
            horario_dict = {}
            dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes']
            for dia in dias_semana:
                # Capturamos entrada, salida y colacion
                entrada = request.form.get(f'horario[{dia}][entrada]')
                salida = request.form.get(f'horario[{dia}][salida]')
                colacion = request.form.get(f'horario[{dia}][colacion]')
                
                # Solo guardamos el día si tiene datos
                if entrada or salida:
                    horario_dict[dia] = {
                        'entrada': entrada, 
                        'salida': salida, 
                        'colacion': colacion
                    }
            
            data['horario'] = horario_dict if horario_dict else None
            data['estado'] = 'BORRADOR'

            # 4. Llamar al Servicio (El cerebro que procesa todo, incluido el JSON financiero)
            nuevo_contrato = ContratosService.crear_contrato(data)

            flash(f'Contrato creado exitosamente (Folio {nuevo_contrato.id}). Estado: BORRADOR.', 'success')
            return redirect(url_for('contratos_bp.listar'))
            
        except ValueError as ve:
            # Errores de validación de negocio (saldos insuficientes, fechas, etc.)
            flash(f'Atención: {str(ve)}', 'warning')
            return redirect(url_for('contratos_bp.nuevo_contrato'))
        except Exception as e:
            # Errores técnicos
            print(f"Error al crear contrato: {e}") # Log en consola
            flash(f'Error crítico al guardar: {str(e)}', 'danger')
            return redirect(url_for('contratos_bp.nuevo_contrato'))

    # --- GET: Cargar formulario ---
    try:
        programas = Programa.query.order_by(Programa.id.desc()).all()
        tipos_contrato = TipoContratoHonorario.query.all()
        # IMPORTANTE: Cargamos las autoridades para pasarlas al template
        # Esto permite que los selectores de Alcalde/Secretario funcionen correctamente
        autoridades = AutoridadFirmante.query.all()
        
        return render_template('contratos/create.html', 
                               programas=programas,
                               tipos_contrato=tipos_contrato,
                               autoridades=autoridades)
    except Exception as e:
        flash(f'Error al cargar formulario: {str(e)}', 'danger')
        return redirect(url_for('main_bp.dashboard'))

@contratos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_contrato(id):
    """
    Permite modificar un contrato existente.
    Ahora incluye recálculo financiero completo si se modifica el monto/cuotas.
    """
    contrato = ContratoHonorario.query.get_or_404(id)

    if contrato.estado == 'ANULADO':
        flash('No se puede editar un contrato anulado.', 'warning')
        return redirect(url_for('contratos_bp.listar'))

    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            data['funciones'] = request.form.getlist('funciones[]')
            
            # Procesar Horario en Edición
            horario_dict = {}
            for dia in ['lunes', 'martes', 'miercoles', 'jueves', 'viernes']:
                entrada = request.form.get(f'horario[{dia}][entrada]')
                salida = request.form.get(f'horario[{dia}][salida]')
                colacion = request.form.get(f'horario[{dia}][colacion]')
                
                if entrada or salida:
                    horario_dict[dia] = {'entrada': entrada, 'salida': salida, 'colacion': colacion}

            data['horario'] = horario_dict if horario_dict else None

            ContratosService.actualizar_contrato(id, data)
            
            flash(f'Contrato #{id} actualizado correctamente.', 'success')
            return redirect(url_for('contratos_bp.listar'))

        except Exception as e:
            flash(f'Error al editar: {str(e)}', 'danger')
            return redirect(url_for('contratos_bp.editar_contrato', id=id))

    try:
        # --- CORRECCIÓN: Se agrega la consulta de programas ---
        programas = Programa.query.order_by(Programa.id.desc()).all()
        
        tipos = TipoContratoHonorario.query.all()
        autoridades = AutoridadFirmante.query.all()
        
        return render_template('contratos/edit.html', 
                               contrato=contrato, 
                               programas=programas, # SE AGREGA ESTA VARIABLE QUE FALTABA
                               tipos_contrato=tipos, 
                               autoridades=autoridades)
    except Exception as e:
        flash(f'Error al cargar edición: {str(e)}', 'danger')
        return redirect(url_for('contratos_bp.listar'))

@contratos_bp.route('/descargar-word/<int:id>')
def descargar_word(id):
    """
    Genera el Word y cambia el estado a 'PENDIENTE_FIRMA'.
    """
    try:
        contrato = ContratoHonorario.query.get_or_404(id)

        nombre_archivo = ContratosService.generar_word_contrato(id)
        
        if contrato.estado == 'BORRADOR':
            contrato.estado = 'PENDIENTE_FIRMA'
            db.session.commit()
            flash('Documento generado. El estado cambió a "Pendiente de Firma".', 'info')
        
        directorio_descargas = os.path.join(current_app.root_path, 'static', 'downloads')
        return send_from_directory(
            directory=directorio_descargas, 
            path=nombre_archivo, 
            as_attachment=True
        )
    except Exception as e:
        flash(f'Error al generar documento: {str(e)}', 'danger')
        return redirect(url_for('contratos_bp.listar'))

@contratos_bp.route('/subir_firmado/<int:id>', methods=['POST'])
def subir_contrato_firmado(id):
    """
    Recibe el PDF escaneado, lo guarda y activa el contrato (VIGENTE).
    """
    try:
        contrato = ContratoHonorario.query.get_or_404(id)
        
        if 'archivo_pdf' not in request.files:
            flash('No se seleccionó ningún archivo.', 'warning')
            return redirect(url_for('contratos_bp.listar'))
            
        file = request.files['archivo_pdf']
        
        if file.filename == '':
            flash('El nombre del archivo está vacío.', 'warning')
            return redirect(url_for('contratos_bp.listar'))

        if file and allowed_file(file.filename):
            filename = f"contrato_{contrato.id}_firmado.pdf"
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'contratos')
            os.makedirs(upload_folder, exist_ok=True)
            
            file.save(os.path.join(upload_folder, filename))
            
            contrato.archivo_firmado = filename
            contrato.estado = 'VIGENTE'
            db.session.commit()
            
            flash('¡Contrato activado correctamente! El documento digitalizado ha sido vinculado.', 'success')
        else:
            flash('Formato no permitido. Solo se aceptan archivos PDF.', 'danger')

    except Exception as e:
        flash(f'Error al subir archivo: {str(e)}', 'danger')

    return redirect(url_for('contratos_bp.listar'))

@contratos_bp.route('/ver_pdf/<filename>')
def ver_pdf(filename):
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'contratos')
    return send_from_directory(upload_folder, filename)

@contratos_bp.route('/anular/<int:id>', methods=['POST'])
def anular_contrato(id):
    try:
        contrato = ContratoHonorario.query.get_or_404(id)
        contrato.estado = 'ANULADO'
        # Nota: Aquí idealmente se debería llamar a un servicio que también
        # libere (devuelva) el saldo presupuestario reservado.
        db.session.commit()
        flash('Contrato anulado correctamente.', 'warning')
    except Exception as e:
        flash(f'Error al anular: {str(e)}', 'danger')
        
    return redirect(url_for('contratos_bp.listar'))

# ==========================================
# APIs PARA AJAX (FRONTEND DINÁMICO)
# ==========================================

@contratos_bp.route('/api/buscar_persona/<path:rut>', methods=['GET'])
def buscar_persona_api(rut):
    """
    API robusta v2: Busca el RUT probando 3 formatos distintos para asegurar coincidencia
    sin importar cómo esté guardado en la Base de Datos.
    Usamos <path:rut> para evitar problemas con los puntos en la URL.
    """
    try:
        # Normalizamos a mayúsculas
        rut_entrada = rut.upper()
        
        # Generamos las 3 variantes posibles del RUT para intentar buscar
        variante_con_puntos = rut_entrada                   # Ej: "12.345.678-9"
        variante_sin_puntos = rut_entrada.replace('.', '')  # Ej: "12345678-9"
        variante_solo_numeros = variante_sin_puntos.replace('-', '') # Ej: "123456789"

        intentos = [variante_con_puntos, variante_sin_puntos, variante_solo_numeros]
        persona = None
        
        for intento in intentos:
            persona = Persona.query.get(intento)
            if persona:
                break # ¡Lo encontramos!

        if persona:
            return jsonify({
                'encontrado': True,
                'nombre_completo': f"{persona.nombres} {persona.apellido_paterno} {persona.apellido_materno}",
                'profesion': persona.titulo_profesional or 'Sin título registrado',
                'direccion': persona.direccion or 'Sin dirección registrada',
                'comuna': persona.comuna_residencia or 'Santa Juana'
            })
        else:
            return jsonify({'encontrado': False})
            
    except Exception as e:
        print(f"Error búsqueda API Persona: {e}")
        return jsonify({'encontrado': False, 'error': str(e)})

@contratos_bp.route('/api/cuentas_programa/<int:programa_id>', methods=['GET'])
def obtener_cuentas_programa(programa_id):
    """
    API CRÍTICA: Retorna las cuentas contables asociadas a un programa y su saldo disponible.
    Es llamada por el JavaScript de create.html para llenar el select de imputaciones en las cuotas.
    """
    try:
        programa = Programa.query.get_or_404(programa_id)
        cuentas = []
        
        for c in programa.cuentas:
            # Usamos getattr por seguridad si el modelo no tiene 'nombre'
            nombre_cuenta = getattr(c, 'nombre', 'Cuenta Presupuestaria')
            
            cuentas.append({
                'id': c.id,
                'codigo': c.codigo,
                'nombre': nombre_cuenta,
                'saldo': int(c.saldo_actual) 
            })
            
        return jsonify({'cuentas': cuentas})
    except Exception as e:
        print(f"Error API Cuentas: {str(e)}")
        return jsonify({'error': str(e)}), 500

@contratos_bp.route('/carga-masiva', methods=['GET', 'POST'])
def carga_masiva():
    """
    Procesa la carga masiva de honorarios para la Municipalidad de Santa Juana.
    Requiere un CSV con 12 columnas incluyendo Rut Alcalde y Rut Secretario.
    """
    if request.method == 'POST':
        archivo = request.files.get('archivo_csv')
        
        # Validaciones iniciales del archivo
        if not archivo or not archivo.filename.endswith('.csv'):
            flash('Por favor, sube un archivo CSV válido (.csv).', 'danger')
            return redirect(request.url)

        try:
            # 1. Lectura del flujo de datos con codificación UTF-8
            # Usamos 'utf-8-sig' por si el archivo viene de Excel con BOM (marca de orden de bytes)
            contenido = archivo.stream.read().decode("utf-8-sig")
            stream = io.StringIO(contenido, newline=None)
            
            # 2. Configuración del Lector CSV
            # Delimitador ';' es el estándar en Excel configurado para Chile
            lector = csv.DictReader(stream, delimiter=';') 
            
            # 3. Ejecución del proceso en el Service
            # Este método ahora busca a los firmantes por RUT de forma exacta
            resultado = ContratosService.procesar_carga_masiva(lector)
            
            # 4. Notificación de resultados al usuario
            if resultado['errores'] == 0:
                flash(f"Éxito: Se han cargado {resultado['exitos']} contratos correctamente.", 'success')
            else:
                flash(
                    f"Carga parcial: {resultado['exitos']} exitosos y {resultado['errores']} fallidos. "
                    f"Revisa los logs de la consola para ver los RUTs que fallaron.", 
                    'warning'
                )
                
        except UnicodeDecodeError:
            flash('Error de codificación: Asegúrate de guardar el CSV como UTF-8.', 'danger')
        except Exception as e:
            db.session.rollback() # Seguridad ante fallos inesperados
            flash(f'Error crítico procesando el archivo: {str(e)}', 'danger')
        
        return redirect(url_for('contratos_bp.listar'))

    return render_template('contratos/carga_masiva.html')