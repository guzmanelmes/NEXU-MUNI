# app/routes/personas_routes.py
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, send_file
from app.services.persona_service import PersonaService
from app.schemas.personas_schema import PersonaSchema
from marshmallow import ValidationError
import pandas as pd
import io

# 1. Ajuste de Prefijo para compatibilidad con AJAX: /personas/api/<rut>
personas_bp = Blueprint('personas_bp', __name__, url_prefix='/personas')

# Instancias de Schemas
persona_schema = PersonaSchema()
personas_schema = PersonaSchema(many=True)

# =======================================================
# RUTAS API (JSON - Para sistemas externos o AJAX)
# =======================================================

@personas_bp.route('/api/', methods=['GET'])
def get_personas():
    """Retorna listado de personas en formato JSON."""
    personas = PersonaService.get_all()
    return jsonify(personas_schema.dump(personas)), 200

@personas_bp.route('/api/<rut>', methods=['GET'])
def get_persona(rut):
    """
    Busca una persona por RUT. 
    Actualizado para devolver el campo 'success' requerido por el buscador AJAX.
    """
    persona = PersonaService.get_by_rut(rut)
    if not persona:
        return jsonify({"success": False, "error": "Persona no encontrada"}), 404
    
    # Preparamos la respuesta con el flag 'success' para el frontend
    data = persona_schema.dump(persona)
    return jsonify({
        "success": True,
        **data # Desempaqueta nombres, apellidos y título profesional
    }), 200

@personas_bp.route('/api/', methods=['POST'])
def create_persona():
    """Crea una nueva persona vía API JSON."""
    json_data = request.get_json()
    if not json_data:
        return jsonify({"error": "No se enviaron datos"}), 400

    try:
        data = persona_schema.load(json_data)
        nueva_persona = PersonaService.create(data)
        return jsonify(persona_schema.dump(nueva_persona)), 201
        
    except ValidationError as err:
        return jsonify({"errores_validacion": err.messages}), 422
    except ValueError as err:
        return jsonify({"error": str(err)}), 409
    except Exception as err:
        return jsonify({"error": "Error interno del servidor", "detalle": str(err)}), 500

@personas_bp.route('/api/<rut>', methods=['PUT'])
def update_persona(rut):
    """Actualiza datos de una persona vía API JSON."""
    json_data = request.get_json()
    try:
        data = persona_schema.load(json_data, partial=True)
        persona_actualizada = PersonaService.update(rut, data)
        if not persona_actualizada:
            return jsonify({"error": "Persona no encontrada"}), 404
            
        return jsonify(persona_schema.dump(persona_actualizada)), 200
    except ValidationError as err:
        return jsonify({"errores_validacion": err.messages}), 422

@personas_bp.route('/api/<rut>', methods=['DELETE'])
def delete_persona(rut):
    """Elimina una persona del sistema."""
    eliminado = PersonaService.delete(rut)
    if not eliminado:
        return jsonify({"error": "Persona no encontrada"}), 404
    
    return jsonify({"mensaje": f"Persona con RUT {rut} eliminada correctamente"}), 200

# =======================================================
# RUTAS DE CARGA MASIVA (VISTAS HTML)
# =======================================================

@personas_bp.route('/carga_masiva', methods=['GET', 'POST'])
def carga_masiva():
    """Renderiza el formulario de carga masiva y procesa el archivo Excel."""
    if request.method == 'POST':
        if 'archivo_excel' not in request.files:
            flash('No se seleccionó ningún archivo.', 'danger')
            return redirect(request.url)
        
        file = request.files['archivo_excel']
        if file.filename == '':
            flash('Nombre de archivo inválido.', 'danger')
            return redirect(request.url)

        if file:
            try:
                procesados, n_errores, lista_errores = PersonaService.procesar_carga_masiva(file)
                
                if procesados > 0:
                    flash(f'Proceso finalizado. Se guardaron/actualizaron {procesados} funcionarios.', 'success')
                
                if n_errores > 0:
                    flash(f'Atención: Hubo {n_errores} filas que no se pudieron procesar.', 'warning')
                    return render_template('personas/carga_masiva.html', errores=lista_errores)
                
                return redirect(url_for('personas_bp.carga_masiva'))

            except Exception as e:
                flash(f'Error crítico al procesar el archivo: {str(e)}', 'danger')
                return redirect(request.url)

    return render_template('personas/carga_masiva.html')

@personas_bp.route('/descargar_plantilla')
def descargar_plantilla():
    """Genera y descarga un Excel de ejemplo para la carga masiva."""
    try:
        columnas = [
            'RUT', 'Nombres', 'Apellido Paterno', 'Apellido Materno', 
            'Fecha Nacimiento', 'Sexo', 'Email', 'Telefono', 
            'Direccion', 'Comuna', 'Nivel Estudios', 'Titulo',
            'Banco', 'Tipo Cuenta', 'Numero Cuenta',
            'Es Discapacitado', 'Tiene Credencial COMPIN', 
            'Tipo Discapacidad', 'Pension Invalidez',
            'Fecha Ingreso Municipio', 'Fecha Ingreso Sector Publico'
        ]

        df = pd.DataFrame(columns=columnas)
        df.loc[0] = [
            '12.345.678-9', 'Juan', 'Pérez', 'Soto', 
            '1990-01-01', 'Masculino', 'juan@ejemplo.cl', '+56912345678', 
            'Calle Falsa 123', 'Santa Juana', 'Profesional', 'Ingeniero Informático',
            'Banco Estado', 'Cuenta RUT', '12345678',
            'No', 'No', '', 'No', 
            '2024-01-01', '2020-03-01'
        ]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Plantilla')
            worksheet = writer.sheets['Plantilla']
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + i) if i < 26 else 'AA'].width = column_len
        
        output.seek(0)
        return send_file(
            output, 
            download_name="Plantilla_Carga_Personas_Completa.xlsx", 
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f"Error al generar plantilla: {str(e)}", "danger")
        return redirect(url_for('personas_bp.carga_masiva'))