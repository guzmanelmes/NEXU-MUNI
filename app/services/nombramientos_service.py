from app.extensions import db
from app.models.nombramientos import Nombramiento
from app.models.catalogos import CatEstamento 
from datetime import datetime

class NombramientosService:

    @staticmethod
    def listar_todos():
        """
        Retorna todos los nombramientos registrados, ordenados por fecha de inicio.
        """
        return Nombramiento.query.order_by(Nombramiento.fecha_inicio.desc()).all()

    @staticmethod
    def obtener_por_id(id):
        """
        Busca un nombramiento específico por su ID.
        """
        return Nombramiento.query.get_or_404(id)

    @staticmethod
    def crear_nombramiento(data):
        """
        Crea un nombramiento validando que el grado esté dentro del rango del estamento.
        """
        try:
            # 1. Extracción y procesamiento de datos
            rut = data.get('persona_id')
            estamento_id = int(data.get('estamento_id'))
            grado = int(data.get('grado'))
            calidad_juridica = data.get('calidad_juridica')
            
            # Captura de unidad organizacional
            unidad_id = data.get('unidad_id')
            if not unidad_id or unidad_id == "":
                unidad_id = None
            else:
                unidad_id = int(unidad_id)
            
            fecha_inicio = datetime.strptime(data.get('fecha_inicio'), '%Y-%m-%d').date()
            fecha_decreto = datetime.strptime(data.get('fecha_decreto'), '%Y-%m-%d').date()
            
            fecha_fin = None
            if data.get('fecha_fin'):
                fecha_fin = datetime.strptime(data.get('fecha_fin'), '%Y-%m-%d').date()

            # 2. VALIDACIÓN DE REGLAS DE NEGOCIO (Rangos de Grados)
            estamento_config = CatEstamento.query.get(estamento_id)
            if not estamento_config:
                raise ValueError("El estamento seleccionado no existe en el sistema.")

            if grado < estamento_config.grado_min or grado > estamento_config.grado_max:
                raise ValueError(
                    f"Error de Validación: El estamento '{estamento_config.estamento}' "
                    f"solo permite grados entre {estamento_config.grado_min} y {estamento_config.grado_max}. "
                    f"Grado {grado} es inválido."
                )

            # 3. GUARDADO (Se incluye unidad_id)
            nuevo_nombramiento = Nombramiento(
                persona_id=rut,
                estamento_id=estamento_id,
                unidad_id=unidad_id,
                calidad_juridica=calidad_juridica,
                grado=grado,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                horas_semanales=int(data.get('horas_semanales', 44)),
                numero_decreto=data.get('numero_decreto'),
                fecha_decreto=fecha_decreto,
                estado='VIGENTE'
            )

            db.session.add(nuevo_nombramiento)
            db.session.commit()
            return nuevo_nombramiento

        except ValueError as ve:
            db.session.rollback()
            raise ve
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def actualizar_nombramiento(id, data):
        """
        Actualiza un nombramiento existente aplicando las mismas validaciones de rango.
        """
        try:
            nombramiento = Nombramiento.query.get(id)
            if not nombramiento:
                raise ValueError("Nombramiento no encontrado.")

            # Validación de Rango de Grados (Integridad de datos)
            estamento_id = int(data.get('estamento_id'))
            grado = int(data.get('grado'))
            estamento_config = CatEstamento.query.get(estamento_id)

            if grado < estamento_config.grado_min or grado > estamento_config.grado_max:
                raise ValueError(
                    f"Grado {grado} no válido para {estamento_config.estamento}. "
                    f"Rango permitido: {estamento_config.grado_min} al {estamento_config.grado_max}."
                )

            # Actualización de unidad organizacional
            unidad_id = data.get('unidad_id')
            if not unidad_id or unidad_id == "":
                nombramiento.unidad_id = None
            else:
                nombramiento.unidad_id = int(unidad_id)

            # Actualización de campos permitidos
            nombramiento.estamento_id = estamento_id
            nombramiento.grado = grado
            nombramiento.calidad_juridica = data.get('calidad_juridica')
            nombramiento.numero_decreto = data.get('numero_decreto')
            nombramiento.fecha_decreto = datetime.strptime(data.get('fecha_decreto'), '%Y-%m-%d').date()
            nombramiento.fecha_inicio = datetime.strptime(data.get('fecha_inicio'), '%Y-%m-%d').date()
            nombramiento.horas_semanales = int(data.get('horas_semanales', 44))
            
            # Gestión de fecha de término
            if data.get('fecha_fin'):
                nombramiento.fecha_fin = datetime.strptime(data.get('fecha_fin'), '%Y-%m-%d').date()
            else:
                nombramiento.fecha_fin = None

            db.session.commit()
            return nombramiento

        except ValueError as ve:
            db.session.rollback()
            raise ve
        except Exception as e:
            db.session.rollback()
            raise e

    # =======================================================
    # NUEVOS MÉTODOS DE GESTIÓN DE CICLO DE VIDA
    # =======================================================

    @staticmethod
    def finalizar_nombramiento(id, motivo, fecha_termino):
        """
        Cambia el estado del nombramiento y establece la fecha de término definitiva.
        """
        try:
            nombramiento = Nombramiento.query.get_or_404(id)
            nombramiento.estado = motivo
            if fecha_termino:
                nombramiento.fecha_fin = datetime.strptime(fecha_termino, '%Y-%m-%d').date()
            
            db.session.commit()
            return nombramiento
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def eliminar_nombramiento(id):
        """
        Elimina físicamente el registro del nombramiento de la base de datos.
        """
        try:
            nombramiento = Nombramiento.query.get_or_404(id)
            db.session.delete(nombramiento)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e