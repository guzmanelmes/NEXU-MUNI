from app.extensions import db
from datetime import datetime

# =======================================================
# TABLAS DE CONFIGURACIÓN (Catálogos)
# =======================================================

class AutoridadFirmante(db.Model):
    """
    Define quién firma los documentos.
    Se usa tanto para el Alcalde/Jefe (Autoridad) como para el Secretario Municipal (Ministro de Fe).
    Incluye las líneas de firma explícitas para generar el Word perfecto.
    """
    __tablename__ = 'cfg_autoridades_firmantes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(100), nullable=False)
    es_subrogante = db.Column(db.Boolean, default=False)
    decreto_nombramiento = db.Column(db.String(100), nullable=True) 

    # --- CAMPOS DE FIRMA (Soportan hasta 4 líneas) ---
    firma_linea_1 = db.Column(db.String(150), nullable=False) 
    firma_linea_2 = db.Column(db.String(150), nullable=True) 
    firma_linea_3 = db.Column(db.String(150), nullable=True) 
    firma_linea_4 = db.Column(db.String(150), nullable=True) 

    def __repr__(self):
        tipo = "(S)" if self.es_subrogante else "(T)"
        return f'<Autoridad {self.nombre} {tipo}>'

class TipoContratoHonorario(db.Model):
    """
    Define las reglas de negocio del contrato.
    Ej: "Experto (Jornada Completa)", "Monitor (Por hora)"
    """
    __tablename__ = 'cfg_tipos_contrato'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    es_jornada_completa = db.Column(db.Boolean, default=False) 
    usa_asistencia = db.Column(db.Boolean, default=True)       
    plantilla_word = db.Column(db.String(100), default='honorario_estandar.docx') 

    def __repr__(self):
        return f'<Tipo {self.nombre}>'

# =======================================================
# TABLAS DE GESTIÓN FINANCIERA (NIVELES 2 y 3)
# =======================================================

class ContratoCuotaDetalle(db.Model):
    """
    NIVEL 3: Detalle financiero de una cuota específica.
    Si una cuota es de $100.000, aquí se dice:
    - $50.000 de la cuenta 215...001
    - $50.000 de la cuenta 215...002
    """
    __tablename__ = 'contratos_cuotas_detalle'
    
    id = db.Column(db.Integer, primary_key=True)
    cuota_id = db.Column(db.Integer, db.ForeignKey('contratos_cuotas.id', ondelete='CASCADE'), nullable=False)
    
    codigo_cuenta = db.Column(db.String(50), nullable=False) # El código presupuestario
    monto_parcial = db.Column(db.Integer, nullable=False)    # Cuánto aporta esta cuenta a la cuota

    def __repr__(self):
        return f'<Detalle Cuota {self.cuota_id}: {self.codigo_cuenta} - ${self.monto_parcial}>'

class ContratoCuota(db.Model):
    """
    NIVEL 2: Calendario de pagos.
    Cada fila representa un mes que se debe pagar al funcionario.
    """
    __tablename__ = 'contratos_cuotas'

    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos_honorarios.id', ondelete='CASCADE'), nullable=False)
    
    numero_cuota = db.Column(db.Integer, nullable=False) # 1, 2, 3...
    mes = db.Column(db.Integer, nullable=False)          # 1 a 12
    anio = db.Column(db.Integer, nullable=False)         # 2026
    monto = db.Column(db.Integer, nullable=False)        # Monto específico de este mes
    
    estado = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, TRAMITADA, PAGADA, ANULADA

    # Relación con Nivel 3 (Detalles)
    detalles_financieros = db.relationship('ContratoCuotaDetalle', backref='cuota', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Cuota {self.numero_cuota} ({self.mes}/{self.anio}): ${self.monto}>'

# =======================================================
# TABLA PRINCIPAL: CONTRATOS (NIVEL 1)
# =======================================================

class ContratoHonorario(db.Model):
    __tablename__ = 'contratos_honorarios'

    id = db.Column(db.Integer, primary_key=True)
    
    # 1. VINCULACIONES
    persona_id = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    programa_id = db.Column(db.Integer, db.ForeignKey('programas.id'), nullable=False)
    tipo_contrato_id = db.Column(db.Integer, db.ForeignKey('cfg_tipos_contrato.id'), nullable=False)
    
    # NUEVO: Horas semanales
    horas_semanales = db.Column(db.Integer, default=44)
    
    # ESTADO: Control de ciclo de vida
    estado = db.Column(db.String(20), default='BORRADOR') 
    
    # ARCHIVO FIRMADO: Nombre del PDF subido (ej: contrato_100_firmado.pdf)
    archivo_firmado = db.Column(db.String(255), nullable=True)

    # AUTORIDADES
    autoridad_id = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)
    secretario_id = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)

    # 2. DATOS DEL CONTRATO / DECRETO
    numero_decreto_autoriza = db.Column(db.String(50), nullable=True)
    fecha_decreto = db.Column(db.Date, nullable=True)
    fecha_firma = db.Column(db.Date, nullable=True)
    
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    
    # DATOS ECONÓMICOS GLOBALES
    monto_total = db.Column(db.Integer, nullable=False)
    numero_cuotas = db.Column(db.Integer, default=1) # Cantidad de pagos pactados
    valor_mensual = db.Column(db.Integer, nullable=False) # Referencial

    # 3. CAMPOS JSON
    funciones_json = db.Column(db.JSON, nullable=True) 
    horario_json = db.Column(db.JSON, nullable=True)
    distribucion_cuentas_json = db.Column(db.JSON, nullable=False) # Resumen global para consultas rápidas

    # 4. RELACIONES ORM
    persona = db.relationship('Persona', backref='contratos')
    programa = db.relationship('Programa')
    tipo = db.relationship('TipoContratoHonorario')

    autoridad = db.relationship('AutoridadFirmante', foreign_keys=[autoridad_id])
    secretario = db.relationship('AutoridadFirmante', foreign_keys=[secretario_id])

    # Relación con Nivel 2 (Cuotas)
    cuotas = db.relationship('ContratoCuota', backref='contrato', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Contrato {self.id} - Dec: {self.numero_decreto_autoriza} ({self.estado})>'