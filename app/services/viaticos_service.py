from app.extensions import db
from app.models.viaticos import EscalaViaticos
from datetime import datetime, timedelta
from sqlalchemy import or_

class ViaticosService:

    @staticmethod
    def get_todas_escalas():
        """Retorna las escalas ordenadas por fecha (más reciente primero) y luego por grado."""
        return EscalaViaticos.query.order_by(
            EscalaViaticos.fecha_inicio.desc(),
            EscalaViaticos.grado_min.asc()
        ).all()

    @staticmethod
    def crear_escala(data):
        """
        Crea una nueva escala y CIERRA AUTOMÁTICAMENTE la anterior si se solapan.
        Soporta fecha_fin como NULL (vigencia indefinida).
        """
        # 1. Obtener y procesar datos
        try:
            g_min = int(data.get('grado_min'))
            g_max = int(data.get('grado_max'))
            f_ini = datetime.strptime(data.get('fecha_inicio'), '%Y-%m-%d').date()
            
            # Lógica para Fecha Fin: Si viene vacía, es NULL (Vigente indefinidamente)
            fecha_fin_input = data.get('fecha_fin')
            f_fin = None
            if fecha_fin_input:
                f_fin = datetime.strptime(fecha_fin_input, '%Y-%m-%d').date()
                
        except (ValueError, TypeError):
            raise ValueError("Datos numéricos o de fecha inválidos.")

        if g_min > g_max:
            raise ValueError("El Grado Mínimo no puede ser mayor que el Grado Máximo.")

        # ==============================================================================
        # LÓGICA DE CIERRE INTELIGENTE (Soporte NULL)
        # ==============================================================================
        # Buscamos si ya existe una escala para estos mismos grados que:
        # 1. Tenga fecha_fin NULL (es decir, está vigente por siempre).
        # 2. O su fecha_fin sea posterior o igual al inicio de la nueva.
        
        escala_anterior = EscalaViaticos.query.filter(
            EscalaViaticos.grado_min == g_min,
            EscalaViaticos.grado_max == g_max,
            or_(
                EscalaViaticos.fecha_fin == None,       # Está vigente indefinidamente
                EscalaViaticos.fecha_fin >= f_ini       # O termina después de que empieza la nueva
            )
        ).first()

        if escala_anterior:
            # Calculamos el día anterior a la nueva vigencia
            nuevo_fin_anterior = f_ini - timedelta(days=1)
            
            # Validación de seguridad: no podemos cerrar una escala antes de que empiece
            if nuevo_fin_anterior < escala_anterior.fecha_inicio:
                raise ValueError(f"La nueva escala comienza antes de que inicie la anterior vigente ({escala_anterior.fecha_inicio}).")

            # Actualizamos la fecha de fin de la escala vieja
            escala_anterior.fecha_fin = nuevo_fin_anterior
            db.session.add(escala_anterior) # Marcamos para guardar el cambio

        # ==============================================================================
        # INSERTAR LA NUEVA
        # ==============================================================================
        nueva = EscalaViaticos(
            grado_min=g_min,
            grado_max=g_max,
            monto_100=int(data.get('monto_100')),
            monto_40=int(data.get('monto_40')),
            monto_20=int(data.get('monto_20')),
            fecha_inicio=f_ini,
            fecha_fin=f_fin # Puede ser None (NULL en BD)
        )

        db.session.add(nueva)
        db.session.commit()
        return nueva

    @staticmethod
    def eliminar_escala(id):
        """
        Elimina una escala y RESTAURA la vigencia de la anterior si estaban conectadas.
        Evita dejar 'huecos' cronológicos en los viáticos.
        """
        # 1. Obtenemos la escala que vamos a borrar
        escala_a_borrar = EscalaViaticos.query.get(id)
        if not escala_a_borrar:
            return False

        try:
            # Guardamos sus fechas antes de borrarla
            inicio_borrada = escala_a_borrar.fecha_inicio
            fin_borrada = escala_a_borrar.fecha_fin # Puede ser None
            grados_min = escala_a_borrar.grado_min
            grados_max = escala_a_borrar.grado_max

            # 2. Buscamos si existe una escala "inmediatamente anterior"
            # (Aquella que termina exactamente un día antes de que esta empezara)
            dia_anterior = inicio_borrada - timedelta(days=1)
            
            escala_anterior = EscalaViaticos.query.filter(
                EscalaViaticos.grado_min == grados_min,
                EscalaViaticos.grado_max == grados_max,
                EscalaViaticos.fecha_fin == dia_anterior
            ).first()

            # 3. Si existe la anterior, la extendemos para cubrir el periodo de la borrada
            if escala_anterior:
                # Si borramos la nueva, la anterior recupera la fecha fin de la borrada
                # (esto funciona incluso si fin_borrada es None/Vigente)
                escala_anterior.fecha_fin = fin_borrada
                db.session.add(escala_anterior)

            # 4. Finalmente borramos la escala nueva
            db.session.delete(escala_a_borrar)
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            raise e