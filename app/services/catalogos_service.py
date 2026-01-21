from app.extensions import db
from app.models.catalogos import CatSexo, CatEstamento, CatNivelEstudios, CatUnidad

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
        """Crea un nuevo registro de sexo."""
        nuevo = CatSexo(descripcion=descripcion)
        db.session.add(nuevo)
        db.session.commit()

    @staticmethod
    def actualizar_sexo(id, nueva_descripcion):
        """Actualiza la descripción de un sexo existente."""
        reg = CatSexo.query.get(id)
        if reg:
            reg.descripcion = nueva_descripcion
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_sexo(id):
        """Elimina un registro de sexo por su ID."""
        reg = CatSexo.query.get(id)
        if reg:
            db.session.delete(reg)
            db.session.commit()

    # =======================================================
    # GESTIÓN DE NIVEL DE ESTUDIOS
    # =======================================================
    @staticmethod
    def get_niveles_estudios():
        """Obtiene todos los niveles de estudio."""
        return CatNivelEstudios.query.all()

    @staticmethod
    def crear_nivel(descripcion):
        """Crea un nuevo nivel de estudios."""
        nuevo = CatNivelEstudios(descripcion=descripcion)
        db.session.add(nuevo)
        db.session.commit()

    @staticmethod
    def actualizar_nivel(id, nueva_descripcion):
        """Actualiza un nivel de estudios por su ID."""
        reg = CatNivelEstudios.query.get(id)
        if reg:
            reg.descripcion = nueva_descripcion
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_nivel(id):
        """Elimina un nivel de estudios del sistema."""
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
        return CatEstamento.query.all()

    @staticmethod
    def crear_estamento(estamento, g_min, g_max):
        """Crea un estamento con sus rangos de grados."""
        nuevo = CatEstamento(estamento=estamento, grado_min=g_min, grado_max=g_max)
        db.session.add(nuevo)
        db.session.commit()

    @staticmethod
    def actualizar_estamento(id, estamento, g_min, g_max):
        """Actualiza los datos de un estamento municipal."""
        reg = CatEstamento.query.get(id)
        if reg:
            reg.estamento = estamento
            reg.grado_min = g_min
            reg.grado_max = g_max
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_estamento(id):
        """Elimina un estamento municipal por su ID."""
        reg = CatEstamento.query.get(id)
        if reg:
            db.session.delete(reg)
            db.session.commit()

    # =======================================================
    # GESTIÓN DE UNIDADES ORGANIZACIONALES (ESTRUCTURA)
    # =======================================================
    @staticmethod
    def get_unidades():
        """Obtiene unidades ordenadas por tipo y nombre."""
        return CatUnidad.query.order_by(CatUnidad.tipo, CatUnidad.nombre).all()

    @staticmethod
    def crear_unidad(data):
        """Crea una unidad organizacional (Dirección, Depto, etc.)."""
        nueva = CatUnidad(
            nombre=data.get('nombre').upper(),
            sigla=data.get('sigla').upper() if data.get('sigla') else None,
            tipo=data.get('tipo'),
            padre_id=data.get('padre_id') if data.get('padre_id') else None
        )
        db.session.add(nueva)
        db.session.commit()
        return nueva

    @staticmethod
    def actualizar_unidad(id, data):
        """Actualiza una unidad organizacional existente."""
        reg = CatUnidad.query.get(id)
        if reg:
            reg.nombre = data.get('nombre').upper()
            reg.sigla = data.get('sigla').upper() if data.get('sigla') else None
            reg.tipo = data.get('tipo')
            reg.padre_id = data.get('padre_id') if data.get('padre_id') else None
            db.session.commit()
            return True
        return False

    @staticmethod
    def eliminar_unidad(id):
        """Elimina una unidad del organigrama municipal."""
        reg = CatUnidad.query.get(id)
        if reg:
            db.session.delete(reg)
            db.session.commit()
            return True
        return False