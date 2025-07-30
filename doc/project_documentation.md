# Proyecto: Sistema de Sincronización SQL Server → PostgreSQL con Redis

**Autor:** Joel Santana H.  
**Fecha inicio:** 15/7/2025  
**Empresa:** Facu Importaciones  
**Propósito:** Sincronización de datos de conduces y planificación para usuarios en NocoDB

---

## 📋 Descripción del Proyecto

Sistema de sincronización en tiempo real que transfiere datos desde SQL Server 2016 hacia PostgreSQL, utilizando Redis como cola intermedia para maximizar rendimiento y confiabilidad.

### 🎯 Objetivo Principal
- Sincronizar vista `VW_VENTAS_SYNC` desde SQL Server a PostgreSQL
- Permitir a usuarios editar campos de planificación en NocoDB
- Separar datos de solo lectura (SQL Server) de datos editables (usuarios)

### 🏗️ Arquitectura Implementada
```
SQL Server 2016 → Redis Queue → PostgreSQL → NocoDB
     ↓              ↓              ↓          ↓
VW_VENTAS_SYNC  change_queue  datos_vista  Interface
                               datos_seguimiento  Usuarios
```

---

## 🚀 Progreso Actual

### ✅ Pasos Completados

#### **Paso 1: Estructura básica** ✅
- Script Python con imports básicos
- Estructura de funciones
- Documentación y comentarios

#### **Paso 2: Sistema de logging** ✅
- Configuración de logging a archivo y consola
- Niveles INFO, WARNING, ERROR
- Formato con timestamp y nivel

#### **Paso 3: Variables de entorno** ✅
- Carga de archivo `.env` 
- Validación de variables requeridas
- Configuración SQL Server, PostgreSQL, Redis
- Función `load_env_file()` para compatibilidad local/Docker

#### **Paso 4: Conexiones a bases de datos** ✅
- Prueba de conexión a SQL Server (pymssql)
- Prueba de conexión a PostgreSQL (psycopg2)
- Prueba de conexión a Redis (redis-py)
- Validación completa antes de iniciar sync

#### **Paso 4.5: Base de datos PostgreSQL** ✅
- Base de datos `syncdb` creada
- Tabla `datos_vista` (solo lectura - datos SQL Server)
- Tabla `datos_trabajo` (CRUD usuarios - campos editables)
- Foreign key entre tablas por `conduce`
- Triggers para `updated_at` automático
- Índices para rendimiento

### 🔄 Paso Actual: **Paso 5 - Lógica de sincronización**

**Estado:** En desarrollo  
**Progreso:** 70% - Arquitectura definida, pendiente implementación Producer-Consumer

---

## 📊 Arquitectura Técnica

### 🗄️ Bases de Datos

#### **SQL Server 2016** (Origen)
- **Host:** 10.0.0.6:1433
- **Base de datos:** g_FACU
- **Usuario:** INV (permisos de solo lectura)
- **Vista:** `VW_VENTAS_SYNC`
- **Campos clave:** `CONDUCE`, `ULTIMA_MODIFICACION`, `FACTURADO`

#### **PostgreSQL** (Destino)
- **Host:** 127.0.0.1:5432 (local) / postgres (Docker)
- **Base de datos:** syncdb
- **Usuario:** sysadmin

**Tablas:**
```sql
-- Datos sincronizados (solo lectura)
datos_vista (
    sync_id, conduce PRIMARY KEY, fecha_emision, 
    facturado, numero_factura, codigo_cliente, 
    cliente, ultima_modificacion, created_at, updated_at
)

-- Datos editables usuarios  
datos_seguimiento (
    id SERIAL PRIMARY KEY, conduce UNIQUE,
    nota, ruta, trabajado, preparador,
    created_at, updated_at,
    FOREIGN KEY (conduce) REFERENCES datos_vista(conduce)
)
```

#### **Redis** (Cola intermedia)
- **Host:** 127.0.0.1:6379
- **Password:** Propose1-Amused-Cotton
- **Estructuras:**
  - `change_queue`: Cola FIFO para registros a sincronizar
  - `last_sync_timestamp`: Último timestamp procesado
  - `client_cache`: Cache para datos frecuentes (futuro)

### 🔄 Flujo de Datos

#### **Producer Process**
1. Lee `last_sync_timestamp` desde Redis
2. Query incremental: `WHERE ULTIMA_MODIFICACION > last_sync`
3. Por cada registro: `LPUSH change_queue JSON(record)`
4. Actualiza `last_sync_timestamp` en Redis
5. Repeat cada 10 segundos

#### **Consumer Process**
1. `BRPOP change_queue` (bloqueo hasta datos)
2. Procesa batch de registros
3. UPSERT en `datos_vista`: `INSERT ON CONFLICT DO UPDATE`
4. Confirma procesamiento
5. Repeat continuamente

---

## ⚙️ Configuración

### 📝 Variables de Entorno (.env)
```bash
# SQL Server 2016
MSSQL_HOST=10.0.0.6
MSSQL_PORT=1433
MSSQL_DATABASE=g_FACU
MSSQL_USER=INV
MSSQL_PASSWORD=F4cu@db01
MSSQL_VIEW=VW_VENTAS_SYNC

# PostgreSQL (contenedor separado)
PG_HOST=127.0.0.1           # local testing
PG_PORT=5432
PG_DATABASE=syncdb
PG_USER=sysadmin
PG_PASSWORD=Tux-Plural-Retype3
PG_TABLE_VISTA=datos_vista
PG_TABLE_SEGUIMIENTO=datos_seguimiento

# Redis (contenedor separado)
REDIS_HOST=127.0.0.1          # Docker container name
REDIS_PORT=6379
REDIS_PASSWORD=Propose1-Amused-Cotton
REDIS_DB=0

# Sync Settings
SYNC_INTERVAL=60            # Producer frequency (seconds)
BATCH_SIZE=50               # Consumer batch size
```

### 🐳 **Configuración Multi-Contenedor**
- **Redis**: Contenedor separado `redis` 
- **PostgreSQL**: Contenedor separado `postgres`
- **Sync Service**: Nuevo contenedor que se conecta a ambos

### 📦 Dependencias Python
```txt
pymssql==2.2.11      # SQL Server connector
psycopg2-binary      # PostgreSQL connector  
redis==4.5.4         # Redis client
python-dateutil      # Date parsing (mejor compatibilidad)
```

**Instalación:**
```bash
# Opción 1: apt (recomendado para Ubuntu)
sudo apt install python3-pymssql python3-psycopg2 python3-redis python3-dateutil

# Opción 2: pip (si no funciona apt)
pip3 install pymssql psycopg2-binary redis python-dateutil
```

---

## 📁 Estructura de Archivos

```
/home/sysadmin/docker/sync-service/
├── sync_script.py          # Script principal (en desarrollo)
├── .env                    # Variables de entorno
├── requirements.txt        # Dependencias Python (futuro)
├── Dockerfile             # Imagen Docker (futuro)
├── docker-compose.yml     # Orquestación (futuro)
├── entrypoint.sh          # Script inicio (futuro)
└── logs/
    └── sync.log           # Logs de ejecución
```

### 🗄️ PostgreSQL
```
/scripts/create_syncdb.sql  # Script creación base de datos
```

---

## 🎯 Próximos Pasos

### **Paso 5: Implementar Producer-Consumer** (En progreso)

#### **5.1 Producer Process** 🟨
- [ ] Función `producer_process(config, logger)`
- [ ] Loop cada 10 segundos
- [ ] Query incremental SQL Server
- [ ] Push a Redis queue
- [ ] Actualizar timestamp

#### **5.2 Consumer Process** 🟨  
- [ ] Función `consumer_process(config, logger)`
- [ ] BRPOP desde Redis queue
- [ ] Batch processing
- [ ] UPSERT PostgreSQL
- [ ] Confirmar procesado

#### **5.3 Threading y Control** 🟨
- [ ] Threads separados para Producer/Consumer
- [ ] Graceful shutdown (Ctrl+C)
- [ ] Manejo de errores robusto
- [ ] Health checks

### **Paso 6: Loop principal y timing** ⏸️
- [ ] Coordinación entre procesos
- [ ] Métricas de rendimiento
- [ ] Logging avanzado

### **Paso 7: Containerización** ⏸️
- [ ] requirements.txt
- [ ] Dockerfile optimizado
- [ ] docker-compose.yml con Redis
- [ ] entrypoint.sh

### **Paso 8: Testing y deployment** ⏸️
- [ ] Pruebas de carga
- [ ] Validación de datos
- [ ] Monitoreo y alertas
- [ ] Documentación final

### **Paso 9: NocoDB Integration** ⏸️
- [ ] Conexión a PostgreSQL
- [ ] Configuración de tablas
- [ ] Permisos de usuario
- [ ] Interface final

---

## 🔧 Comandos Útiles

### **Desarrollo Local**
```bash
# Ejecutar script
cd /home/sysadmin/docker/sync-service/
python3 sync_script.py

# Ver logs
tail -f logs/sync.log

# Monitorear Redis
redis-cli -h 127.0.0.1 -p 6379 -a "Propose1-Amused-Cotton"
> LLEN change_queue
> GET last_sync_timestamp
```

### **PostgreSQL**
```bash
# Conectar a syncdb
psql -h 127.0.0.1 -U sysadmin -d syncdb

# Ver tablas
\dt

# Contar registros
SELECT COUNT(*) FROM datos_vista;
SELECT COUNT(*) FROM datos_trabajo;
```

---

## 📈 Métricas de Rendimiento Esperadas

### **Rendimiento objetivo:**
- **Latencia:** < 30 segundos para cambios nuevos
- **Throughput:** 1000+ registros/minuto
- **Disponibilidad:** 99.9%
- **Error rate:** < 0.1%

### **Optimizaciones implementadas:**
- ✅ **Consultas incrementales** (timestamp-based)
- ✅ **UPSERT** en lugar de SELECT + INSERT/UPDATE
- ✅ **Batch processing** para transacciones
- ✅ **Redis queue** para desacoplamiento
- ✅ **Índices** en campos consultados frecuentemente

---

## 🚨 Problemas Conocidos y Soluciones

### **1. Conexión SQL Server**
**Problema:** Error de conexión a 10.0.0.6  
**Solución:** Verificar red, firewall, y credenciales usuario INV

### **2. PostgreSQL local vs Docker**
**Problema:** Host diferente según entorno  
**Solución:** Variable PG_HOST en .env (127.0.0.1 local, postgres Docker)

### **3. Redis password**
**Problema:** Autenticación Redis  
**Solución:** Variable REDIS_PASSWORD configurada correctamente

### **4. Timestamp sync**
**Problema:** Primer sync trae todos los datos  
**Solución:** Implementado fallback a 2000-01-01 para primera ejecución

---

## 🎯 Decisiones de Diseño Importantes

### **1. ¿Por qué Redis Queue?**
- **Desacoplamiento:** Producer y Consumer independientes
- **Rendimiento:** Memoria > Disco para cola
- **Confiabilidad:** Persistencia y retry automático
- **Escalabilidad:** Fácil agregar múltiples consumers

### **2. ¿Por qué dos tablas separadas?**
- **datos_vista:** Solo lectura, datos "puros" de SQL Server
- **datos_trabajo:** CRUD usuarios, campos editables
- **Integridad:** Foreign key garantiza consistencia
- **Seguridad:** Permisos granulares por tabla

### **3. ¿Por qué UPSERT?**
- **Eficiencia:** Una query vs SELECT + INSERT/UPDATE
- **Atomicidad:** Operación transaccional
- **Simplicidad:** Menos código, menos errores

### **4. ¿Por qué timestamp en Redis?**
- **Velocidad:** Redis >> PostgreSQL para operaciones simples
- **Disponibilidad:** Acceso rápido para Producer
- **Backup:** Tabla sync_control como fallback

---

## 📞 Contacto y Notas

**Desarrollador:** Joel Santana H.  
**Empresa:** Facu Importaciones  
**Ubicación:** Santo Domingo Este, RD

**Notas importantes:**
- Proyecto enfocado en **rendimiento y confiabilidad**
- **Sin dashboard** - solo funcionalidad core
- Trabajo por **pasos incrementales**
- Documentación **paso a paso** para facilitar debugging

---

*Último update: 16/7/2025 - Paso 5 en progreso*