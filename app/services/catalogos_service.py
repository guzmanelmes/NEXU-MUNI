# app/services/catalogos_service.py
from app.extensions import db
from app.models.catalogos import CatSexo, CatEstamentos, CatNivelEstudios

class CatalogosService:
    
    # =======================================================
    # GESTIÓN DE SEXO / GÉNERO
    # =======================================================
    @staticmethod
    def get_sexos():
        """Obtiene todos los registros de sexo."""
        return CatSexo.query.all()
    
    @staticmethod
    def crear_sexo(descripcion):
        nuevo = CatSexo(descripcion=descripcion)
        db.session.add(nuevo)
        db.session.commit()

    @staticmethod
    def actualizar_sexo(id, nueva_descripcion):
        reg = CatSexo.query.get(id)
        if reg:
            reg.descripcion = nueva_descripcion
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_sexo(id):
        reg = CatSexo.query.get(id)
        if reg:
            db.session.delete(reg)
            db.session.commit()

    # =======================================================
    # GESTIÓN DE NIVEL DE ESTUDIOS (ACTUALIZADO)
    # =======================================================
    @staticmethod
    def get_niveles_estudios():
        """
        NOMBRE CORREGIDO: get_niveles_estudios
        Este nombre es el que busca web_routes.py para llenar el select.
        """
        return CatNivelEstudios.query.all()

    @staticmethod
    def crear_nivel(descripcion):
        nuevo = CatNivelEstudios(descripcion=descripcion)
        db.session.add(nuevo)
        db.session.commit()

    @staticmethod
    def actualizar_nivel(id, nueva_descripcion):
        reg = CatNivelEstudios.query.get(id)
        if reg:
            reg.descripcion = nueva_descripcion
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_nivel(id):
        reg = CatNivelEstudios.query.get(id)
        if reg:
            db.session.delete(reg)
            db.session.commit()

    # =======================================================
    # GESTIÓN DE ESTAMENTOS
    # =======================================================
    @staticmethod
    def get_estamentos():
        """Obtiene todos los estamentos municipales."""
        return CatEstamentos.query.all()

    @staticmethod
    def crear_estamento(estamento, g_min, g_max):
        nuevo = CatEstamentos(estamento=estamento, grado_min=g_min, grado_max=g_max)
        db.session.add(nuevo)
        db.session.commit()

    @staticmethod
    def actualizar_estamento(id, estamento, g_min, g_max):
        reg = CatEstamentos.query.get(id)
        if reg:
            reg.estamento = estamento
            reg.grado_min = g_min
            reg.grado_max = g_max
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_estamento(id):
        reg = CatEstamentos.query.get(id)
        if reg:
            db.session.delete(reg)
            db.session.commit()