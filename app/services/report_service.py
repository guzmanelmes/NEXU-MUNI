import os
from docx import Document
from flask import current_app
from datetime import datetime

class ReportService:
    @staticmethod
    def generar_decreto_word(orden):
        try:
            # 1. Configuración de Rutas
            # Obtenemos la ruta base del proyecto para llegar a /app/plantillas_word/
            base_dir = os.path.abspath(os.path.dirname(current_app.instance_path))
            template_path = os.path.join(base_dir, 'app', 'plantillas_word', 'decreto_autorizacion.docx')
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"No se encontró la plantilla en: {template_path}")

            doc = Document(template_path)

            # 2. Preparar Contexto de Reemplazo
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            fecha_dec = orden.decreto_auth.fecha_decreto
            fecha_formateada = f"{fecha_dec.day} de {meses[fecha_dec.month - 1]} de {fecha_dec.year}"

            contexto = {
                "{{FOLIO}}": str(orden.id),
                "{{NUM_DECRETO}}": orden.decreto_auth.numero_decreto or "____",
                "{{FECHA_DECRETO}}": fecha_formateada,
                "{{RUT}}": orden.rut_funcionario,
                "{{NOMBRE_FUNCIONARIO}}": f"{orden.funcionario.nombres} {orden.funcionario.apellido_paterno} {orden.funcionario.apellido_materno}".upper(),
                "{{ALCALDE}}": orden.decreto_auth.firmante_alcalde.firma_linea_1 if orden.decreto_auth.firmante_alcalde else "",
                "{{SECRETARIO}}": orden.decreto_auth.firmante_secretario.firma_linea_1 if orden.decreto_auth.firmante_secretario else "",
                "{{CARGO_ALCALDE}}": orden.decreto_auth.firmante_alcalde.cargo if orden.decreto_auth.firmante_alcalde else "",
                "{{CARGO_SECRETARIO}}": orden.decreto_auth.firmante_secretario.cargo if orden.decreto_auth.firmante_secretario else "",
            }

            # 3. Reemplazar en Párrafos
            for p in doc.paragraphs:
                for key, value in contexto.items():
                    if key in p.text:
                        p.text = p.text.replace(key, str(value))

            # 4. Reemplazar en Tablas (Cabeceras o datos fijos)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            for key, value in contexto.items():
                                if key in p.text:
                                    p.text = p.text.replace(key, str(value))

            # 5. INSERTAR TABLA DE JORNADAS (Planificación)
            # Buscamos la tabla que tenga la etiqueta {{TABLA_JORNADAS}} o simplemente la segunda tabla
            # Aquí un ejemplo de cómo añadir filas a la primera tabla que encuentres con 3+ columnas
            if doc.tables:
                tabla_detalle = doc.tables[0] # Ajustar índice según tu Word
                for jornada in orden.planificacion:
                    row_cells = tabla_detalle.add_row().cells
                    row_cells[0].text = jornada.fecha.strftime('%d/%m/%Y')
                    row_cells[1].text = f"{jornada.hora_inicio.strftime('%H:%M')} - {jornada.hora_termino.strftime('%H:%M')}"
                    row_cells[2].text = str(jornada.horas_estimadas)
                    row_cells[3].text = jornada.actividad_especifica

            # 6. Guardar archivo temporal
            output_folder = os.path.join(current_app.root_path, 'static', 'temp')
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
                
            file_name = f"Solicitud_{orden.id}_{orden.rut_funcionario.replace('.','')}.docx"
            output_path = os.path.join(output_folder, file_name)
            doc.save(output_path)

            return output_path

        except Exception as e:
            print(f"Error en ReportService: {str(e)}")
            raise e