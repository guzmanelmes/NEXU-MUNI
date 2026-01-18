# seed_data.py
from app import create_app
from app.extensions import db
from app.models.catalogos import CatSexo, CatNivelEstudios, CatEstamentos
from app.models.personas import Persona, HistorialAcademico
from datetime import date

# Iniciamos la app solo para tener contexto de BDD
app = create_app()

def seed_catalogos():
    """Asegura que los catálogos base existan"""
    # Verificamos si ya existen datos para no duplicar
    if CatSexo.query.first():
        print("✅ Catálogos ya parecen existir. Saltando carga de catálogos.")
        return

    # Si por alguna razón la BDD está vacía, cargamos lo básico
    print("⚠️ Cargando catálogos base...")
    sexos = [CatSexo(id=1, descripcion='Femenino'), CatSexo(id=2, descripcion='Masculino')]
    
    niveles = [
        CatNivelEstudios(id=1, descripcion='Sin Estudios'),
        CatNivelEstudios(id=2, descripcion='Básicos'),
        CatNivelEstudios(id=3, descripcion='Medios'),
        CatNivelEstudios(id=4, descripcion='Técnicos'),
        CatNivelEstudios(id=5, descripcion='Pregrado'),
        CatNivelEstudios(id=6, descripcion='Postgrados')
    ]
    
    db.session.add_all(sexos)
    db.session.add_all(niveles)
    db.session.commit()
    print("✅ Catálogos creados.")

def seed_personas():
    """Crea personas y su historial"""
    
    # Revisar si ya existe la persona para no romper el script
    rut_juan = "11.111.111-1"
    if Persona.query.get(rut_juan):
        print("✅ Datos de personas ya existen.")
        return

    print("🌱 Creando personas de prueba...")

    # 1. Crear a Juan Pérez (Funcionario Antiguo)
    juan = Persona(
        rut=rut_juan,
        nombres="Juan Alberto",
        apellido_paterno="Pérez",
        apellido_materno="Soto",
        fecha_nacimiento=date(1975, 5, 20),
        sexo_id=2, # Masculino
        nacionalidad="Chilena",
        direccion="Av. Principal 123",
        email="juan.perez@nexu-muni.cl",
        fecha_ingreso_municipio=date(2000, 3, 1),
        es_discapacitado=False
    )

    # 2. Crear a Maria González (Joven profesional)
    maria = Persona(
        rut="22.222.222-2",
        nombres="Maria Ignacia",
        apellido_paterno="González",
        apellido_materno="López",
        fecha_nacimiento=date(1995, 8, 15),
        sexo_id=1, # Femenino
        email="m.gonzalez@nexu-muni.cl",
        direccion="Calle Los Alerces 45",
        es_discapacitado=True,
        tipo_discapacidad="Movilidad Reducida",
        tiene_credencial_compin=True
    )

    db.session.add(juan)
    db.session.add(maria)
    db.session.commit()

    print("📚 Agregando historial académico...")

    # A Juan le agregamos un título técnico
    # IMPORTANTE: Al guardar esto con es_principal=True, el Trigger de MySQL
    # debería actualizar automáticamente el campo 'titulo_profesional' en la tabla 'personas'
    historial_juan = HistorialAcademico(
        rut_persona=juan.rut,
        nivel_estudios_id=4, # Técnico
        nombre_titulo="Técnico en Administración",
        institucion="Instituto AIEP",
        fecha_titulacion=date(1998, 12, 1),
        es_principal=True
    )

    # A Maria le agregamos un título profesional
    historial_maria = HistorialAcademico(
        rut_persona=maria.rut,
        nivel_estudios_id=5, # Pregrado
        nombre_titulo="Ingeniera Comercial",
        institucion="Universidad de Concepción",
        fecha_titulacion=date(2019, 1, 15),
        es_principal=True
    )

    db.session.add(historial_juan)
    db.session.add(historial_maria)
    db.session.commit()
    
    print("✅ Personas y Títulos creados exitosamente.")

if __name__ == "__main__":
    with app.app_context():
        try:
            seed_catalogos()
            seed_personas()
            print("\n🚀 Carga de datos finalizada correctamente.")
        except Exception as e:
            print(f"\n❌ Error durante la carga de datos: {e}")
            db.session.rollback()