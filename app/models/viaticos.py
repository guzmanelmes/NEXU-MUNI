from app.extensions import db
from datetime import datetime

# =======================================================
# 1. ESCALA DE VIÁTICOS (Catálogo de Valores)
# =======================================================
class EscalaViaticos(db.Model):
    __tablename__ = 'escala_viaticos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Vigencia de la Escala
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=True) 
    
    # Rango de Grados (Ej: del 1 al 5)
    grado_min = db.Column(db.Integer, nullable=False)
    grado_max = db.Column(db.Integer, nullable=False)
    
    # Valores monetarios según porcentaje
    monto_100 = db.Column(db.Integer, default=0, nullable=False)
    monto_40 = db.Column(db.Integer, default=0, nullable=False)
    monto_20 = db.Column(db.Integer, default=0, nullable=False)
    
    def __repr__(self):
        estado = "Vigente" if self.fecha_fin is None else f"hasta {self.fecha_fin}"
        return f'<EscalaViaticos {self.fecha_inicio} (G{self.grado_min}-{self.grado_max}): {estado}>'

# =======================================================
# 2. DECRETOS DE VIÁTICOS (Transaccional)
# =======================================================
class ViaticoDecreto(db.Model):
    __tablename__ = 'viaticos_decretos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # --- A. DATOS ADMINISTRATIVOS ---
    numero_decreto = db.Column(db.String(50), nullable=True)
    fecha_decreto = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(20), default='BORRADOR') # BORRADOR, PENDIENTE, APROBADO, ANULADO
    
    # --- B. FUNCIONARIO (Snapshot del momento del viaje) ---
    # Vinculamos al RUT, pero guardamos grado y estamento históricos
    rut_funcionario = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    estamento_al_viajar = db.Column(db.String(100), nullable=False)
    grado_al_viajar = db.Column(db.Integer, nullable=False)
    
    # --- C. DETALLE DEL VIAJE ---
    motivo_viaje = db.Column(db.Text, nullable=False)
    lugar_destino = db.Column(db.String(150), nullable=False)
    
    fecha_salida = db.Column(db.Date, nullable=False)
    hora_salida = db.Column(db.Time, nullable=False)
    
    fecha_regreso = db.Column(db.Date, nullable=True)
    hora_regreso = db.Column(db.Time, nullable=True)
    
    # --- D. LOGÍSTICA Y TRANSPORTE ---
    usa_vehiculo = db.Column(db.Boolean, default=False)
    # Tipos: MUNICIPAL, PARTICULAR, LOCOMOCION_PUBLICA, AEREO
    tipo_vehiculo = db.Column(db.String(50), default='LOCOMOCION_PUBLICA') 
    placa_patente = db.Column(db.String(20), nullable=True)
    
    # --- E. CÁLCULO MONETARIO (Desglose) ---
    dias_al_100 = db.Column(db.Float, default=0.0) # Con pernoctación
    dias_al_40 = db.Column(db.Float, default=0.0)  # Sin pernoctación
    dias_al_20 = db.Column(db.Float, default=0.0)  # Otros
    monto_total_calculado = db.Column(db.Integer, default=0)
    archivo_firmado = db.Column(db.String(255), nullable=True)
    
    # --- F. FIRMANTES (Roles específicos para el Decreto) ---
    # Usamos la tabla de configuración de firmantes que ya tienes
    admin_municipal_id = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)
    secretario_municipal_id = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)
    
    # CORRECCIÓN: Mapeamos el atributo 'fecha_solicitud' a la columna existente 'created_at'
    fecha_solicitud = db.Column('created_at', db.DateTime, default=datetime.now)

    # --- RELACIONES ORM ---
    funcionario = db.relationship('Persona', backref=db.backref('viaticos', lazy=True))
    
    # Relaciones con firmantes (usando foreign_keys para diferenciar los dos roles)
    admin_municipal = db.relationship('AutoridadFirmante', foreign_keys=[admin_municipal_id])
    secretario = db.relationship('AutoridadFirmante', foreign_keys=[secretario_municipal_id])

    def calcular_monto_total(self, escala):
        """
        Recalcula el total basado en los días y la escala proporcionada.
        """
        if not escala:
            return 0
        
        total = (self.dias_al_100 * escala.monto_100) + \
                (self.dias_al_40 * escala.monto_40) + \
                (self.dias_al_20 * escala.monto_20)
        
        self.monto_total_calculado = int(total)
        return self.monto_total_calculado

    def __repr__(self):
        return f'<ViaticoDecreto {self.id} - RUT: {self.rut_funcionario} - Destino: {self.lugar_destino}>'