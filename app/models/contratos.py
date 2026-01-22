from app.extensions import db
from datetime import datetime

# =======================================================
# TABLAS DE CONFIGURACIÓN (Catálogos)
# =======================================================

class AutoridadFirmante(db.Model):
    """
    Define quién firma los documentos (Alcalde o Secretario).
    Ahora el RUT es una llave foránea vinculada oficialmente a la tabla 'personas'.
    """
    __tablename__ = 'cfg_autoridades_firmantes'
    
    id = db.Column(db.Integer, primary_key=True)
    # Vinculación oficial: Se elimina 'nombre' para evitar duplicidad de datos
    rut = db.Column(db.String(12), db.ForeignKey('personas.rut'), unique=False, nullable=False) 
    cargo = db.Column(db.String(100), nullable=False)
    es_subrogante = db.Column(db.Boolean, default=False)
    decreto_nombramiento = db.Column(db.String(100), nullable=True) 

    # --- CAMPOS DE FIRMA (Estructura para el documento Word) ---
    firma_linea_1 = db.Column(db.String(150), nullable=False) 
    firma_linea_2 = db.Column(db.String(150), nullable=True) 
    firma_linea_3 = db.Column(db.String(150), nullable=True) 
    firma_linea_4 = db.Column(db.String(150), nullable=True) 

    # RELACIÓN: Permite acceder a los datos de la persona (nombres, títulos, etc.) en tiempo real
    persona = db.relationship('Persona', backref='config_firmante')

    def __repr__(self):
        tipo = "(S)" if self.es_subrogante else "(T)"
        # El nombre ahora se obtiene dinámicamente desde la relación 'persona'
        return f'<Autoridad RUT: {self.rut} Cargo: {self.cargo} {tipo}>'

class TipoContratoHonorario(db.Model):
    """
    Define las reglas de negocio y la plantilla Word asociada.
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
    NIVEL 3: Imputación presupuestaria específica por cuota.
    """
    __tablename__ = 'contratos_cuotas_detalle'
    
    id = db.Column(db.Integer, primary_key=True)
    cuota_id = db.Column(db.Integer, db.ForeignKey('contratos_cuotas.id', ondelete='CASCADE'), nullable=False)
    
    codigo_cuenta = db.Column(db.String(50), nullable=False) 
    monto_parcial = db.Column(db.Integer, nullable=False)    

    def __repr__(self):
        return f'<Detalle Cuota {self.cuota_id}: {self.codigo_cuenta} - ${self.monto_parcial}>'

class ContratoCuota(db.Model):
    """
    NIVEL 2: Calendario de pagos individuales.
    """
    __tablename__ = 'contratos_cuotas'

    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos_honorarios.id', ondelete='CASCADE'), nullable=False)
    
    numero_cuota = db.Column(db.Integer, nullable=False) 
    mes = db.Column(db.Integer, nullable=False)          
    anio = db.Column(db.Integer, nullable=False)         
    monto = db.Column(db.Integer, nullable=False)        
    
    estado = db.Column(db.String(20), default='PENDIENTE') 

    detalles_financieros = db.relationship('ContratoCuotaDetalle', backref='cuota', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Cuota {self.numero_cuota} ({self.mes}/{self.anio}): ${self.monto}>'

# =======================================================
# TABLA PRINCIPAL: CONTRATOS (NIVEL 1)
# =======================================================

class ContratoHonorario(db.Model):
    """
    NIVEL 1: Cabecera legal y financiera del contrato.
    """
    __tablename__ = 'contratos_honorarios'

    id = db.Column(db.Integer, primary_key=True)
    
    # Vinculaciones Core
    persona_id = db.Column(db.String(12), db.ForeignKey('personas.rut'), nullable=False)
    programa_id = db.Column(db.Integer, db.ForeignKey('programas.id'), nullable=False)
    tipo_contrato_id = db.Column(db.Integer, db.ForeignKey('cfg_tipos_contrato.id'), nullable=False)
    
    # Gestión Administrativa
    horas_semanales = db.Column(db.Integer, default=44)
    estado = db.Column(db.String(20), default='BORRADOR') 
    archivo_firmado = db.Column(db.String(255), nullable=True)

    # Identificación de Firmantes vinculados al catálogo de roles
    autoridad_id = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)
    secretario_id = db.Column(db.Integer, db.ForeignKey('cfg_autoridades_firmantes.id'), nullable=False)

    # Datos del Decreto / Fechas
    numero_decreto_autoriza = db.Column(db.String(50), nullable=True)
    fecha_decreto = db.Column(db.Date, nullable=True)
    fecha_firma = db.Column(db.Date, nullable=True)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    
    # Resumen Económico
    monto_total = db.Column(db.Integer, nullable=False)
    numero_cuotas = db.Column(db.Integer, default=1) 
    valor_mensual = db.Column(db.Integer, nullable=False) 

    # Estructuras JSON para flexibilidad de informes
    funciones_json = db.Column(db.JSON, nullable=True) 
    horario_json = db.Column(db.JSON, nullable=True)
    distribucion_cuentas_json = db.Column(db.JSON, nullable=False) 

    # Relaciones ORM
    persona = db.relationship('Persona', backref='contratos', foreign_keys=[persona_id])
    programa = db.relationship('Programa')
    tipo = db.relationship('TipoContratoHonorario')

    autoridad = db.relationship('AutoridadFirmante', foreign_keys=[autoridad_id])
    secretario = db.relationship('AutoridadFirmante', foreign_keys=[secretario_id])

    # Vínculo con niveles inferiores (Cuotas)
    cuotas = db.relationship('ContratoCuota', backref='contrato', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Contrato {self.id} - Funcionario RUT: {self.persona_id} ({self.estado})>'