# app/services/remuneraciones_service.py
from datetime import datetime, timedelta
from app.extensions import db
from app.models.remuneraciones import EscalaRemuneraciones, EscalaRemuneracionesDetalle, ConfigTipoHaberes, haber_estamento
from app.models.catalogos import CatEstamentos
from sqlalchemy import desc

class RemuneracionesService:
    
    # --- HABERES ---
    @staticmethod
    def get_haberes():
        return ConfigTipoHaberes.query.all()

    # --- ESCALAS (LISTADO GENERAL) ---
    @staticmethod
    def get_escalas_recientes():
        # Trae las escalas ordenadas por fecha (las más nuevas primero)
        return EscalaRemuneraciones.query.order_by(desc(EscalaRemuneraciones.fecha_vigencia)).all()

    @staticmethod
    def crear_escala(data_header, lista_montos):
        """
        data_header: Diccionario con estamento_id, grado, fecha
        lista_montos: Lista de diccionarios [{'haber_id': 1, 'monto': 50000}, ...]
        """
        try:
            # 1. Cerrar vigencia anterior automáticamente
            RemuneracionesService.cerrar_vigencia_anterior(data_header['fecha_vigencia'])

            # 2. Crear la Cabecera
            nueva_escala = EscalaRemuneraciones(
                fecha_vigencia=data_header['fecha_vigencia'],
                estamento_id=data_header['estamento_id'],
                grado=data_header['grado'],
                sueldo_base=data_header.get('sueldo_base', 0),
                fecha_fin=None # Nace abierta
            )
            db.session.add(nueva_escala)
            db.session.flush() # Esto genera el ID de la escala antes de hacer commit

            # 3. Crear los Detalles (Montos)
            for item in lista_montos:
                monto = int(item['monto'])
                if monto > 0: # Solo guardamos si hay monto
                    detalle = EscalaRemuneracionesDetalle(
                        escala_id=nueva_escala.id,
                        haber_id=item['haber_id'],
                        monto=monto
                    )
                    db.session.add(detalle)
            
            db.session.commit()
            return nueva_escala
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_detalle_escala(escala_id):
        return EscalaRemuneraciones.query.get(escala_id)

    # =======================================================
    # LÓGICA DE CICLO DE VIDA (NUEVO)
    # =======================================================

    @staticmethod
    def cerrar_vigencia_anterior(fecha_nueva_str):
        """
        Busca escalas vigentes anteriores a la nueva fecha 
        y les pone fecha_fin = (fecha_nueva - 1 día).
        """
        try:
            # Convertir string a objeto date si es necesario
            if isinstance(fecha_nueva_str, str):
                fecha_nueva = datetime.strptime(fecha_nueva_str, '%Y-%m-%d').date()
            else:
                fecha_nueva = fecha_nueva_str

            # Calcular fecha de cierre (1 día antes de la nueva vigencia)
            fecha_cierre = fecha_nueva - timedelta(days=1)

            # Buscar todas las escalas que iniciaron ANTES y que NO tienen fecha de fin (están abiertas)
            escalas_abiertas = EscalaRemuneraciones.query.filter(
                EscalaRemuneraciones.fecha_vigencia < fecha_nueva,
                EscalaRemuneraciones.fecha_fin == None
            ).all()

            count = 0
            for esc in escalas_abiertas:
                esc.fecha_fin = fecha_cierre
                count += 1
            
            # No hacemos commit aquí, dejamos que el método padre (crear/clonar) lo haga
            return count

        except Exception as e:
            raise e

    # =======================================================
    # LÓGICA ANTIGUA (POR ESTAMENTO - Legacy)
    # =======================================================

    @staticmethod
    def obtener_matriz(fecha_vigencia, estamento_id):
        haberes_cols = ConfigTipoHaberes.query.filter(
            ConfigTipoHaberes.es_manual == True,
            ConfigTipoHaberes.codigo != 'SUELDO_BASE'
        ).all()
        
        escalas = EscalaRemuneraciones.query.filter_by(
            fecha_vigencia=fecha_vigencia,
            estamento_id=estamento_id
        ).order_by(EscalaRemuneraciones.grado).all()

        filas = []
        for esc in escalas:
            fila = {
                'escala_id': esc.id,
                'grado': esc.grado,
                'sueldo_base': esc.sueldo_base,
                'haberes': {} 
            }
            for detalle in esc.detalles:
                fila['haberes'][detalle.haber_id] = detalle.monto
            filas.append(fila)

        return haberes_cols, filas

    @staticmethod
    def guardar_matriz(form_data):
        try:
            for key, valor in form_data.items():
                if not valor: continue
                try:
                    valor_int = int(valor)
                except ValueError:
                    continue

                if key.startswith('sueldo_base_'):
                    escala_id = key.split('_')[-1]
                    escala = EscalaRemuneraciones.query.get(escala_id)
                    if escala:
                        escala.sueldo_base = valor_int

                elif key.startswith('haber_'):
                    partes = key.split('_')
                    if len(partes) == 3:
                        escala_id = partes[1]
                        haber_id = partes[2]
                        detalle = EscalaRemuneracionesDetalle.query.filter_by(escala_id=escala_id, haber_id=haber_id).first()
                        if detalle:
                            detalle.monto = valor_int
                        else:
                            nuevo_detalle = EscalaRemuneracionesDetalle(escala_id=escala_id, haber_id=haber_id, monto=valor_int)
                            db.session.add(nuevo_detalle)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    # =======================================================
    # LÓGICA UNIFICADA Y MOTOR DE CÁLCULO (NUEVO)
    # =======================================================

    @staticmethod
    def obtener_matriz_unificada(fecha_vigencia):
        """
        Trae TODOS los grados de esa fecha, sin duplicar por estamento.
        Consolida la información visualmente por Grado.
        EJECUTA EL MOTOR DE CÁLCULO (Fórmulas).
        FILTRA COLUMNAS SEGÚN 'es_visible_matriz' para la vista.
        """
        # 1. Traer TODOS los haberes (Necesarios para el motor de cálculo interno)
        todos_haberes = ConfigTipoHaberes.query.all()
        
        # 2. Traer datos guardados (Escalas)
        escalas = EscalaRemuneraciones.query.filter_by(fecha_vigencia=fecha_vigencia).all()
        
        # 3. Agrupar por Grado (Base de datos bruta)
        filas_dict = {}

        for esc in escalas:
            g = esc.grado
            if g not in filas_dict:
                filas_dict[g] = {
                    'grado': g,
                    'sueldo_base': esc.sueldo_base, # Tomamos el base del primer estamento encontrado
                    'haberes': {} 
                }
            
            # Mezclamos los haberes de todos los estamentos de este grado
            for detalle in esc.detalles:
                if detalle.monto > 0:
                    filas_dict[g]['haberes'][detalle.haber_id] = detalle.monto

        # -----------------------------------------------------------
        # 4. MOTOR DE CÁLCULO DINÁMICO (INTERPRETE DE FÓRMULAS)
        # -----------------------------------------------------------
        for grado, datos in filas_dict.items():
            
            # A) Crear mapa de variables: CODIGO -> MONTO
            variables = {
                'SUELDO_BASE': datos['sueldo_base'] or 0
            }
            
            # Llenar variables con los montos manuales existentes
            for h in todos_haberes:
                if h.es_manual:
                    monto = datos['haberes'].get(h.id, 0)
                    variables[h.codigo] = monto

            # B) Ejecutar fórmulas para haberes calculados
            # Filtramos solo los que NO son manuales
            haberes_calculados = [h for h in todos_haberes if not h.es_manual]
            
            for h_calc in haberes_calculados:
                formula = h_calc.formula 
                
                if formula:
                    try:
                        # Evaluamos la expresión matemática
                        resultado = eval(formula, {"__builtins__": None}, variables)
                        
                        # Redondear y guardar como entero
                        resultado_final = int(round(resultado))
                        
                        # Guardamos en la fila para mostrarlo en la tabla
                        datos['haberes'][h_calc.id] = resultado_final
                        
                        # Guardamos en variables por si otra fórmula depende de este resultado
                        variables[h_calc.codigo] = resultado_final

                    except Exception as e:
                        # Si falla el cálculo, mostramos 0
                        datos['haberes'][h_calc.id] = 0

        # 5. FILTRAR COLUMNAS PARA LA VISTA
        # Solo enviamos al HTML las columnas marcadas como 'es_visible_matriz'
        manuales_visibles = [h for h in todos_haberes if h.es_manual and h.codigo != 'SUELDO_BASE' and h.es_visible_matriz]
        calculados_visibles = [h for h in todos_haberes if not h.es_manual and h.es_visible_matriz]
        
        cols_display = manuales_visibles + calculados_visibles
        filas_ordenadas = sorted(filas_dict.values(), key=lambda x: x['grado'])
        
        return cols_display, filas_ordenadas

    @staticmethod
    def guardar_matriz_unificada(fecha_vigencia, form_data):
        """
        Guarda basándose en FECHA y GRADO.
        Actualiza TODOS los registros (estamentos) que coincidan con ese grado.
        """
        try:
            for key, valor in form_data.items():
                if not valor: continue
                try:
                    valor_int = int(valor)
                except ValueError:
                    continue

                # CASO 1: SUELDO BASE
                if key.startswith('sueldo_base_grado_'):
                    grado = int(key.split('_')[-1])
                    
                    escalas = EscalaRemuneraciones.query.filter_by(
                        fecha_vigencia=fecha_vigencia, 
                        grado=grado
                    ).all()
                    
                    for esc in escalas:
                        esc.sueldo_base = valor_int

                # CASO 2: HABER
                elif key.startswith('haber_grado_'):
                    parts = key.split('_')
                    if len(parts) == 5:
                        grado = int(parts[2])
                        haber_id = int(parts[4])

                        escalas = EscalaRemuneraciones.query.filter_by(
                            fecha_vigencia=fecha_vigencia, 
                            grado=grado
                        ).all()

                        for esc in escalas:
                            detalle = EscalaRemuneracionesDetalle.query.filter_by(
                                escala_id=esc.id,
                                haber_id=haber_id
                            ).first()

                            if detalle:
                                detalle.monto = valor_int
                            else:
                                if valor_int > 0:
                                    nuevo = EscalaRemuneracionesDetalle(
                                        escala_id=esc.id,
                                        haber_id=haber_id,
                                        monto=valor_int
                                    )
                                    db.session.add(nuevo)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    # =======================================================
    # AUTOMATIZACIÓN Y CLONACIÓN (DASHBOARD)
    # =======================================================

    @staticmethod
    def generar_plantilla_vacia(fecha, estamento_id):
        from app.models.catalogos import CatEstamentos 
        
        # 1. CERRAR VIGENCIA ANTERIOR AUTOMÁTICAMENTE
        RemuneracionesService.cerrar_vigencia_anterior(fecha)

        estamento = CatEstamentos.query.get(estamento_id)
        if not estamento:
            raise Exception("Estamento no encontrado")

        count = 0
        for g in range(estamento.grado_min, estamento.grado_max + 1):
            existe = EscalaRemuneraciones.query.filter_by(
                fecha_vigencia=fecha,
                estamento_id=estamento_id,
                grado=g
            ).first()

            if not existe:
                nueva = EscalaRemuneraciones(
                    fecha_vigencia=fecha,
                    estamento_id=estamento_id,
                    grado=g,
                    sueldo_base=0,
                    fecha_fin=None # Nace abierta
                )
                db.session.add(nueva)
                count += 1
        
        db.session.commit()
        return count

    @staticmethod
    def clonar_periodo(fecha_origen, fecha_destino, porcentaje_reajuste=0, grado_min=1, grado_max=99):
        """
        Clona TODA la escala. 
        El % de reajuste SOLO se aplica si el grado está dentro del rango.
        """
        porcentaje = float(porcentaje_reajuste)
        if porcentaje < 0:
            porcentaje = 0.0
        
        escalas_origen = EscalaRemuneraciones.query.filter_by(fecha_vigencia=fecha_origen).all()
        
        if not escalas_origen:
            raise Exception("No hay datos en la fecha de origen seleccionada.")

        # 1. CERRAR VIGENCIA ANTERIOR AUTOMÁTICAMENTE
        RemuneracionesService.cerrar_vigencia_anterior(fecha_destino)

        factor_aumento = 1 + (porcentaje / 100.0)
        contador = 0

        for esc_old in escalas_origen:
            existe = EscalaRemuneraciones.query.filter_by(
                fecha_vigencia=fecha_destino,
                estamento_id=esc_old.estamento_id,
                grado=esc_old.grado
            ).first()

            if existe:
                continue 

            # REAJUSTE DIFERENCIADO
            if grado_min <= esc_old.grado <= grado_max:
                factor_actual = factor_aumento
            else:
                factor_actual = 1.0

            nuevo_base = int(esc_old.sueldo_base * factor_actual)
            
            esc_new = EscalaRemuneraciones(
                fecha_vigencia=fecha_destino,
                estamento_id=esc_old.estamento_id,
                grado=esc_old.grado,
                sueldo_base=nuevo_base,
                fecha_fin=None # Nace abierta
            )
            db.session.add(esc_new)
            db.session.flush()

            for det_old in esc_old.detalles:
                nuevo_monto = int(det_old.monto * factor_actual)
                det_new = EscalaRemuneracionesDetalle(
                    escala_id=esc_new.id,
                    haber_id=det_old.haber_id,
                    monto=nuevo_monto
                )
                db.session.add(det_new)
            
            contador += 1

        db.session.commit()
        return contador
    
    @staticmethod
    def get_fechas_disponibles():
        """
        Retorna una lista de tuplas: (fecha_vigencia, fecha_fin)
        Agrupando para mostrar en el Dashboard.
        """
        query = db.session.query(
            EscalaRemuneraciones.fecha_vigencia,
            EscalaRemuneraciones.fecha_fin
        ).distinct().order_by(desc(EscalaRemuneraciones.fecha_vigencia))
        return query.all()

    @staticmethod
    def eliminar_periodo(fecha_vigencia):
        try:
            registros = EscalaRemuneraciones.query.filter_by(fecha_vigencia=fecha_vigencia).all()
            count = len(registros)
            for reg in registros:
                db.session.delete(reg)
            
            db.session.commit()
            return count
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def aplicar_reajuste_diferenciado(fecha_vigencia, porcentaje, grado_min, grado_max):
        """
        Aplica reajuste (%) solo a:
        1. Sueldo Base.
        2. Haberes que sean MANUALES y VISIBLES EN MATRIZ.
        Ignora automáticos (se recalculan solos) y fijos de ley (ocultos).
        """
        try:
            pct = float(porcentaje)
            if pct < 0:
                pct = 0.0

            escalas = EscalaRemuneraciones.query.filter(
                EscalaRemuneraciones.fecha_vigencia == fecha_vigencia,
                EscalaRemuneraciones.grado >= grado_min,
                EscalaRemuneraciones.grado <= grado_max
            ).all()

            if not escalas:
                return 0

            factor = 1 + (pct / 100.0)
            count = 0

            for esc in escalas:
                # 1. Sueldo Base siempre se reajusta
                esc.sueldo_base = int(esc.sueldo_base * factor)
                
                # 2. Detalles: Solo Manuales y Visibles
                for detalle in esc.detalles:
                    config = detalle.haber
                    if config.es_manual and config.es_visible_matriz:
                        if detalle.monto > 0:
                            detalle.monto = int(detalle.monto * factor)
                count += 1

            db.session.commit()
            return count 

        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def actualizar_fecha_masiva(fecha_anterior, fecha_nueva, nueva_fecha_fin=None):
        """
        Actualiza la fecha de vigencia de TODOS los registros de una escala.
        """
        try:
            # 1. Verificar que no exista ya data en la fecha nueva (para evitar mezclas)
            # Solo validar si la fecha de inicio ha cambiado
            if fecha_anterior != fecha_nueva:
                existe_destino = EscalaRemuneraciones.query.filter_by(fecha_vigencia=fecha_nueva).first()
                if existe_destino:
                    raise Exception(f"Ya existen datos en la fecha destino ({fecha_nueva}). Elimínelos antes de mover esta escala.")

            # 2. Buscar todos los registros de la fecha vieja
            registros = EscalaRemuneraciones.query.filter_by(fecha_vigencia=fecha_anterior).all()
            
            if not registros:
                raise Exception("No se encontraron registros para la fecha seleccionada.")

            # 3. Procesar fecha fin (convertir cadena vacía a None para la BD)
            fecha_fin_val = nueva_fecha_fin if nueva_fecha_fin else None

            count = 0
            for reg in registros:
                reg.fecha_vigencia = fecha_nueva
                reg.fecha_fin = fecha_fin_val
                count += 1
            
            db.session.commit()
            return count

        except Exception as e:
            db.session.rollback()
            raise e

    # =======================================================
    # SIMULADOR DE SUELDOS (API DINÁMICA - VERSIÓN FINAL)
    # =======================================================

    @staticmethod
    def obtener_datos_simulacion(fecha_vigencia, grado, estamento_id):
        """
        1. Valida el rango de grados.
        2. Obtiene SUELDO BASE REAL desde cabecera.
        3. Obtiene valores de Matriz FILTRADOS por Estamento (Solo lo contractual permitido).
        4. Retorna catálogo de Ocasionales FILTRADO por Estamento.
        """
        # --- A) VALIDACIÓN Y CARGA DE ESTAMENTO ---
        from app.models.catalogos import CatEstamentos
        from app.models.remuneraciones import haber_estamento
        
        estamento = CatEstamentos.query.get(estamento_id)
        if not estamento:
            return {'error': 'Estamento no encontrado'}
            
        g = int(grado)
        if g < estamento.grado_min or g > estamento.grado_max:
            return {
                'error': f'El Grado {g} no es válido para {estamento.estamento}.'
            }

        ids_permitidos = {h.id for h in estamento.haberes_disponibles}

        # --- B) DATOS DE MATRIZ Y SUELDO BASE REAL ---
        escala_real = EscalaRemuneraciones.query.filter_by(
            fecha_vigencia=fecha_vigencia,
            estamento_id=estamento_id,
            grado=g
        ).first()
        sueldo_base_real = escala_real.sueldo_base if escala_real else 0

        # NOTA: Aquí usamos el servicio para obtener los cálculos, PERO ignoramos el filtrado visual
        # porque el simulador necesita ver todo lo que suma, aunque esté oculto en la matriz.
        # Por eso volvemos a consultar los haberes completos para el mapeo.
        _, filas = RemuneracionesService.obtener_matriz_unificada(fecha_vigencia)
        datos_grado = next((f for f in filas if f['grado'] == g), None)
        
        valores_matriz = {'SUELDO_BASE': sueldo_base_real}
        lista_fijos = []
        
        # Mapeo de TODOS los haberes (visibles y ocultos)
        all_haberes = ConfigTipoHaberes.query.all()
        map_id_codigo = {h.id: h.codigo for h in all_haberes}
        map_id_nombre = {h.id: h.nombre for h in all_haberes}
        map_id_perm   = {h.id: h.es_permanente for h in all_haberes}
        
        # --- LOGICA DE HORAS EXTRAS ---
        permite_he = False
        codigos_he = ['HE_25', 'HE_50']
        haberes_he = [h for h in all_haberes if h.codigo in codigos_he]
        
        for h_he in haberes_he:
            if h_he.id in ids_permitidos:
                permite_he = True
                break

        # --- PROCESAR VALORES ---
        if datos_grado:
            for haber_id, monto in datos_grado['haberes'].items():
                codigo = map_id_codigo.get(haber_id)
                es_permanente = map_id_perm.get(haber_id, True)

                if codigo:
                    valores_matriz[codigo] = monto

                    # Lista Fija: Solo permitidos por estamento y permanentes
                    if haber_id in ids_permitidos and es_permanente and codigo not in codigos_he:
                        lista_fijos.append({
                            'codigo': codigo,
                            'nombre': map_id_nombre.get(haber_id),
                            'monto': monto,
                            'tipo': 'FIJO'
                        })
        
        # --- PARCHE DE SEGURIDAD PARA HE ---
        if permite_he and sueldo_base_real > 0:
            if valores_matriz.get('HE_25', 0) == 0:
                valor_hora = sueldo_base_real / 190.0
                valores_matriz['HE_25'] = int(valor_hora * 1.25)
            
            if valores_matriz.get('HE_50', 0) == 0:
                valor_hora = sueldo_base_real / 190.0
                valores_matriz['HE_50'] = int(valor_hora * 1.50)

        # --- C) CATÁLOGO ADICIONALES ---
        codigos_excluidos = ['SUELDO_BASE'] + codigos_he

        query_filtrada = ConfigTipoHaberes.query \
            .join(ConfigTipoHaberes.estamentos_habilitados) \
            .filter(CatEstamentos.id == estamento_id) \
            .filter(ConfigTipoHaberes.es_permanente == False) \
            .filter(~ConfigTipoHaberes.codigo.in_(codigos_excluidos)) \
            .order_by(ConfigTipoHaberes.nombre) \
            .all()
        
        catalogo_adicionales = [
            {'codigo': h.codigo, 'nombre': h.nombre, 'es_manual': h.es_manual} 
            for h in query_filtrada
        ]

        return {
            'valores': valores_matriz,    
            'haberes_fijos': lista_fijos, 
            'catalogo_adicionales': catalogo_adicionales,
            'permite_horas_extras': permite_he 
        }