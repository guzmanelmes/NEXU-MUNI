# app/routes/historial_routes.py
from flask import Blueprint, request, jsonify
from app.services.historial_service import HistorialService
from app.schemas.personas_schema import HistorialAcademicoSchema
from marshmallow import ValidationError

historial_bp = Blueprint('historial_bp', __name__, url_prefix='/api/historial')
historial_schema = HistorialAcademicoSchema()

@historial_bp.route('/', methods=['POST'])
def add_titulo():
    json_data = request.get_json()
    try:
        # Validamos datos
        data = historial_schema.load(json_data)
        
        # Creamos usando el servicio (que maneja la lógica de 'es_principal')
        nuevo_titulo = HistorialService.create(data)
        
        return jsonify(historial_schema.dump(nuevo_titulo)), 201
        
    except ValidationError as err:
        return jsonify({"errores": err.messages}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@historial_bp.route('/<int:id>/set-principal', methods=['PATCH'])
def set_principal(id):
    """Ruta para cambiar el título principal rápidamente"""
    try:
        titulo = HistorialService.set_principal(id)
        if not titulo:
            return jsonify({"error": "Título no encontrado"}), 404
            
        return jsonify(historial_schema.dump(titulo)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@historial_bp.route('/<int:id>', methods=['DELETE'])
def delete_titulo(id):
    if HistorialService.delete(id):
        return jsonify({"mensaje": "Título eliminado"}), 200
    return jsonify({"error": "Título no encontrado"}), 404