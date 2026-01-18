# app/services/historial_service.py
from app.extensions import db
from app.models.personas import HistorialAcademico

class HistorialService:

    @staticmethod
    def create(data):
        # 1. Si el nuevo título viene marcado como PRINCIPAL
        if data.get('es_principal') is True:
            rut = data.get('rut_persona')
            # Buscamos todos los títulos de esa persona que sean principales y los desmarcamos
            titulos_anteriores = HistorialAcademico.query.filter_by(rut_persona=rut, es_principal=True).all()
            for titulo in titulos_anteriores:
                titulo.es_principal = False
            
            # (No necesitamos commit aquí todavía, se hará al final junto con el insert)

        # 2. Crear la nueva instancia
        nuevo_historial = HistorialAcademico(**data)
        
        db.session.add(nuevo_historial)
        db.session.commit()
        return nuevo_historial

    @staticmethod
    def delete(id_historial):
        registro = HistorialAcademico.query.get(id_historial)
        if not registro:
            return False
        
        db.session.delete(registro)
        db.session.commit()
        return True

    @staticmethod
    def set_principal(id_historial):
        """Método específico para cambiar cuál es el título principal"""
        registro = HistorialAcademico.query.get(id_historial)
        if not registro:
            return None
        
        # 1. Desmarcar todos los de esa persona
        titulos = HistorialAcademico.query.filter_by(rut_persona=registro.rut_persona, es_principal=True).all()
        for t in titulos:
            t.es_principal = False
            
        # 2. Marcar el seleccionado
        registro.es_principal = True
        
        db.session.commit()
        # El Trigger de BDD se encargará de actualizar la tabla Personas
        return registro