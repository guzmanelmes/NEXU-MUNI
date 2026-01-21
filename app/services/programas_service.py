from app.extensions import db
from app.models.programas import Programa, CuentaPresupuestaria
from datetime import datetime

class ProgramasService:
    
    @staticmethod
    def crear_programa(data_programa, lista_cuentas):
        """
        Crea un programa y sus cuentas presupuestarias en una sola transacción.
        
        Args:
            data_programa (dict): Datos del programa {'nombre', 'numero_decreto', ...}
            lista_cuentas (list): Lista de dicts [{'codigo': '215...', 'monto': 100000}]
        """
        try:
            # 1. Parseo de fecha si viene como string
            fecha_dec = data_programa['fecha_decreto']
            if isinstance(fecha_dec, str):
                fecha_dec = datetime.strptime(fecha_dec, '%Y-%m-%d').date()

            # 2. Crear el objeto Programa (Master)
            nuevo_prog = Programa(
                nombre=data_programa['nombre'],
                numero_decreto=data_programa['numero_decreto'],
                fecha_decreto=fecha_dec
                # archivo_adjunto se manejaría aquí si subieras archivos
            )
            
            # Agregamos a la sesión pero NO hacemos commit aún
            db.session.add(nuevo_prog)
            db.session.flush() # Esto genera el ID del programa sin cerrar la transacción

            # 3. Crear las Cuentas asociadas (Details)
            for c in lista_cuentas:
                nueva_cuenta = CuentaPresupuestaria(
                    programa_id=nuevo_prog.id,
                    codigo=c['codigo'],
                    monto_inicial=int(c['monto']),
                    saldo_actual=int(c['monto']) # Al inicio, el saldo es igual al inicial
                )
                db.session.add(nueva_cuenta)
            
            # 4. Si todo salió bien, guardamos todo junto
            db.session.commit()
            return nuevo_prog
            
        except Exception as e:
            # Si algo falla, deshacemos todo
            db.session.rollback()
            raise e

    @staticmethod
    def calcular_distribucion_automatica(programa_id, monto_total_contrato):
        """
        Distribuye el costo total de un contrato entre las cuentas del programa
        proporcionalmente al saldo que tiene cada una.
        """
        programa = Programa.query.get(programa_id)
        if not programa or not programa.cuentas:
            raise ValueError("El programa seleccionado no tiene cuentas presupuestarias.")

        # 1. Filtramos SOLO las cuentas que tienen dinero (evita división por cero)
        cuentas_validas = [c for c in programa.cuentas if c.saldo_actual > 0]
        
        if not cuentas_validas:
             raise ValueError("El programa no tiene ninguna cuenta con saldo disponible.")

        # 2. Calcular saldo total disponible real
        saldo_global = sum(c.saldo_actual for c in cuentas_validas)
        
        if saldo_global < monto_total_contrato:
            raise ValueError(f"Saldo insuficiente en el programa. (Disponible: ${saldo_global:,.0f} | Requerido: ${monto_total_contrato:,.0f})")

        distribucion = []
        monto_acumulado = 0
        total_cuentas = len(cuentas_validas)
        
        # 3. Distribuir proporcionalmente (Regla de Tres)
        for i, cuenta in enumerate(cuentas_validas):
            
            # Si es la última cuenta de la lista válida, le asignamos la diferencia exacta
            # Esto corrige cualquier error de redondeo de los anteriores
            if i == total_cuentas - 1:
                monto_asignado = monto_total_contrato - monto_acumulado
            else:
                # Cálculo: (SaldoCuenta / SaldoTotal) * CostoContrato
                peso = cuenta.saldo_actual / saldo_global
                monto_asignado = int(monto_total_contrato * peso)
            
            # Solo agregamos si hay monto (por seguridad)
            if monto_asignado > 0:
                distribucion.append({
                    'cuenta_id': cuenta.id,
                    'codigo': cuenta.codigo,
                    'monto': monto_asignado
                })
                monto_acumulado += monto_asignado

        return distribucion

    @staticmethod
    def rebajar_saldo(distribucion_json):
        """
        Descuenta el dinero de las cuentas una vez que el contrato se aprueba/guarda.
        Recibe el JSON de distribución generado arriba.
        """
        try:
            for item in distribucion_json:
                cuenta = CuentaPresupuestaria.query.get(item['cuenta_id'])
                if cuenta:
                    monto_a_descontar = int(item['monto'])
                    
                    # Verificación de seguridad final
                    if cuenta.saldo_actual < monto_a_descontar:
                        raise ValueError(f"La cuenta {cuenta.codigo} no tiene saldo suficiente para completar la operación.")
                    
                    cuenta.saldo_actual -= monto_a_descontar
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e