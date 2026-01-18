# app/services/persona_service.py
import pandas as pd
from app.extensions import db
from app.models.personas import Persona
from app.models.catalogos import CatSexo, CatNivelEstudios
from sqlalchemy.exc import IntegrityError

class PersonaService:
    
    # =======================================================
    # MÉTODOS CRUD BÁSICOS
    # =======================================================

    @staticmethod
    def get_all():
        """Obtiene todas las personas registradas"""
        return Persona.query.all()

    @staticmethod
    def get_by_rut(rut):
        """Busca una persona por su RUT exacto"""
        return Persona.query.get(rut)

    @staticmethod
    def create(data):
        """
        Crea una nueva persona individualmente.
        Recibe un diccionario con los datos del formulario.
        """
        rut = data.get('rut')
        if Persona.query.get(rut):
            raise ValueError(f"La persona con RUT {rut} ya existe.")

        # **data desempaqueta todos los campos del formulario
        nueva_persona = Persona(**data)
        
        try:
            db.session.add(nueva_persona)
            db.session.commit()
            return nueva_persona
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Error de integridad (posible clave foránea inválida o RUT duplicado).")
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update(rut, data):
        """Actualiza datos de una persona existente"""
        persona = Persona.query.get(rut)
        if not persona:
            return None

        for key, value in data.items():
            if hasattr(persona, key):
                # Manejo especial para campos vacíos que deben ser NULL en BD
                # Evita que strings vacíos "" se guarden en campos que no sean obligatorios
                if value == '' and key not in ['rut', 'nombres', 'apellido_paterno', 'apellido_materno']:
                    setattr(persona, key, None)
                else:
                    setattr(persona, key, value)

        db.session.commit()
        return persona

    @staticmethod
    def delete(rut):
        """Elimina una persona"""
        persona = Persona.query.get(rut)
        if not persona:
            return False

        db.session.delete(persona)
        db.session.commit()
        return True

    # =======================================================
    # LÓGICA DE CARGA MASIVA (EXCEL)
    # =======================================================

    @staticmethod
    def procesar_carga_masiva(file):
        """
        Lee un Excel y guarda/actualiza personas masivamente.
        Soporta todos los campos de la BD, incluyendo bancarios e inclusión.
        """
        try:
            # 1. Leer Excel
            df = pd.read_excel(file)
            
            # Normalizar columnas (minúsculas, sin espacios)
            df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

            # 2. Cargar Catálogos para mapeo rápido (Evita N queries)
            try:
                map_sexo = {s.descripcion.lower(): s.id for s in CatSexo.query.all()}
                map_estudios = {e.descripcion.lower(): e.id for e in CatNivelEstudios.query.all()}
            except Exception:
                map_sexo = {}
                map_estudios = {}

            # --- HELPERS INTERNOS ---
            def parse_bool(valor):
                if pd.isna(valor): return 0
                s = str(valor).strip().lower()
                return 1 if s in ['si', 'yes', '1', 'true', 's'] else 0

            def clean_str(valor, max_len=None):
                if pd.isna(valor) or str(valor).strip() == '' or str(valor).lower() == 'nan':
                    return None
                texto = str(valor).strip()
                return texto[:max_len] if max_len else texto

            def parse_int(valor):
                try:
                    return int(float(valor))
                except:
                    return 0

            procesados = 0
            errores = []

            for index, row in df.iterrows():
                fila_n = index + 2 
                
                # RUT es la clave primaria obligatoria
                rut_raw = row.get('rut')
                if pd.isna(rut_raw) or str(rut_raw).strip() == '':
                    errores.append(f"Fila {fila_n}: Columna 'RUT' vacía.")
                    continue
                
                rut = str(rut_raw).strip()

                try:
                    # --- A. BUSCAR O CREAR (Upsert) ---
                    persona = Persona.query.get(rut)
                    es_nuevo = False
                    if not persona:
                        persona = Persona(rut=rut)
                        es_nuevo = True

                    # --- B. MAPEO DE DATOS ---
                    
                    # 1. Identificación y Contacto
                    persona.nombres = clean_str(row.get('nombres'), 100)
                    persona.apellido_paterno = clean_str(row.get('apellido_paterno'), 100)
                    persona.apellido_materno = clean_str(row.get('apellido_materno'), 100)
                    persona.nacionalidad = clean_str(row.get('nacionalidad')) or 'Chilena'
                    persona.email = clean_str(row.get('email'), 100)
                    persona.telefono = clean_str(row.get('telefono'), 20)
                    persona.direccion = clean_str(row.get('direccion'), 255)
                    persona.comuna_residencia = clean_str(row.get('comuna')) or 'Santa Juana'

                    # 2. Catálogos (Sexo y Estudios)
                    sexo_txt = str(row.get('sexo', '')).strip().lower()
                    persona.sexo_id = map_sexo.get(sexo_txt, 3) # Default: 3 (Prefiero no decir)

                    estudio_txt = str(row.get('nivel_estudios', '')).strip().lower()
                    persona.nivel_estudios_id = map_estudios.get(estudio_txt) # Default: None

                    persona.titulo_profesional = clean_str(row.get('titulo'), 100)

                    # 3. Fechas (Nacimiento e Ingresos)
                    campos_fecha = ['fecha_nacimiento', 'fecha_ingreso_municipio', 'fecha_ingreso_sector_publico']
                    for campo in campos_fecha:
                        val = row.get(campo)
                        if pd.notnull(val):
                            try:
                                setattr(persona, campo, pd.to_datetime(val).date())
                            except:
                                pass # Si la fecha es inválida, se mantiene la que tenía o null

                    # 4. Datos Bancarios
                    persona.banco_nombre = clean_str(row.get('banco'), 100)
                    persona.tipo_cuenta = clean_str(row.get('tipo_cuenta'), 50)
                    persona.numero_cuenta = clean_str(row.get('numero_cuenta'), 50)

                    # 5. Inclusión / Discapacidad
                    persona.es_discapacitado = parse_bool(row.get('es_discapacitado'))
                    persona.tiene_credencial_compin = parse_bool(row.get('tiene_credencial_compin'))
                    persona.tipo_discapacidad = clean_str(row.get('tipo_discapacidad'), 100)
                    persona.porcentaje_discapacidad = parse_int(row.get('porcentaje_discapacidad')) # Nuevo campo
                    persona.recibe_pension_invalidez = parse_bool(row.get('pension_invalidez'))

                    # --- C. GUARDAR ---
                    if es_nuevo:
                        db.session.add(persona)
                    
                    procesados += 1

                except Exception as e:
                    errores.append(f"Fila {fila_n} (RUT {rut}): {str(e)}")
            
            db.session.commit()
            return procesados, len(errores), errores

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Error crítico al procesar archivo: {str(e)}")