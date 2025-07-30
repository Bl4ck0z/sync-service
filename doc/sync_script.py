#!/usr/bin/env python3
"""
Script de sincronización SQL Server -> PostgreSQL con Redis Queue
Autor: Joel Santana H.
Fecha: 30/7/2025
Versión: 1.3 - Docker
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from datetime import datetime
import pymssql
import psycopg2
import redis
from dateutil.parser import isoparse

# ============================================================================
# CONSTANTES
# ============================================================================

VERSION = "1.3"
DEFAULT_TIMESTAMP = datetime(2000, 1, 1)
REDIS_QUEUE_NAME = 'sync_queue'
REDIS_TIMESTAMP_KEY = 'last_sync_timestamp'

shutdown_event = threading.Event()

# ============================================================================
# CLASES
# ============================================================================

class SyncMetrics:
    """metricas del sistema de sincronizacion"""
    def __init__(self):
        self.start_time = datetime.now()
        
        # producer
        self.producer_cycles = 0
        self.producer_records_found = 0
        self.producer_records_queued = 0
        self.producer_queries_time = 0.0
        self.producer_errors = 0
        
        # consumer
        self.consumer_batches = 0
        self.consumer_records_processed = 0
        self.consumer_batch_time = 0.0
        self.consumer_errors = 0
        
        # general
        self.postgresql_upserts = 0
        self.postgresql_errors = 0
        self.redis_operations = 0
        
    def get_uptime_seconds(self):
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_uptime_formatted(self):
        uptime = self.get_uptime_seconds()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        if hours > 0:
            return f"{hours}h{minutes}m"
        else:
            return f"{minutes}m"
    
    def get_producer_rate(self):
        uptime = self.get_uptime_seconds()
        return self.producer_records_queued / uptime if uptime > 0 else 0
    
    def get_consumer_rate(self):
        uptime = self.get_uptime_seconds()
        return self.consumer_records_processed / uptime if uptime > 0 else 0
        
    def get_avg_producer_query_time(self):
        return self.producer_queries_time / self.producer_cycles if self.producer_cycles > 0 else 0
        
    def get_avg_consumer_batch_time(self):
        return self.consumer_batch_time / self.consumer_batches if self.consumer_batches > 0 else 0

    def get_total_errors(self):
        return self.producer_errors + self.consumer_errors + self.postgresql_errors

metrics = SyncMetrics()

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def signal_handler(signum, frame):
    print("\nDeteniendo servicio...")
    shutdown_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ============================================================================
# CONFIGURACION
# ============================================================================

def setup_logging():
    """logging dual: archivo detallado + consola limpia para docker"""
    file_logger = logging.getLogger('file_logger')
    file_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('/app/logs/sync.log')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    file_logger.addHandler(file_handler)
    
    console_logger = logging.getLogger('console_logger')
    console_logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    console_logger.addHandler(console_handler)
    
    file_logger.info(f"sistema de logging configurado - sync-service v{VERSION}")
    return file_logger, console_logger

def load_config(file_logger, console_logger):
    """cargar configuración desde variables de entorno docker"""
    file_logger.info("cargando configuración desde variables de entorno...")

    sql_config = {
        'host': os.getenv('MSSQL_HOST'),
        'port': int(os.getenv('MSSQL_PORT', 1433)),
        'database': os.getenv('MSSQL_DATABASE'),
        'user': os.getenv('MSSQL_USER'),
        'password': os.getenv('MSSQL_PASSWORD'),
        'view': os.getenv('MSSQL_VIEW')
    }

    pg_config = {
        'host': os.getenv('PG_HOST'),
        'port': int(os.getenv('PG_PORT', 5432)),
        'database': os.getenv('PG_DATABASE'),
        'user': os.getenv('PG_USER'),
        'password': os.getenv('PG_PASSWORD'),
        'table_vista': os.getenv('PG_TABLE_VISTA', 'datos_vista')
    }
    
    redis_config = {
        'host': os.getenv('REDIS_HOST', 'redis'),
        'port': int(os.getenv('REDIS_PORT', 6379)),
        'password': os.getenv('REDIS_PASSWORD'),
        'db': int(os.getenv('REDIS_DB', 0))
    }
    
    sync_config = {
        'interval': int(os.getenv('SYNC_INTERVAL', 60)),
        'batch_size': int(os.getenv('BATCH_SIZE', 50)),
        'stats_interval': int(os.getenv('STATS_INTERVAL', 300))
    }

    if not _validate_config(sql_config, pg_config, redis_config, console_logger, file_logger):
        return None

    file_logger.info("configuracion cargada y validada exitosamente")
    return {
        'sql': sql_config,
        'pg': pg_config,
        'redis': redis_config,
        'sync': sync_config
    }

def _validate_config(sql_config, pg_config, redis_config, console_logger, file_logger):
    """validacion"""
    required_vars = [
        ('MSSQL_HOST', sql_config['host']),
        ('MSSQL_DATABASE', sql_config['database']),
        ('MSSQL_USER', sql_config['user']),
        ('MSSQL_PASSWORD', sql_config['password']),
        ('MSSQL_VIEW', sql_config['view']),
        ('PG_HOST', pg_config['host']),
        ('PG_DATABASE', pg_config['database']),
        ('PG_USER', pg_config['user']),
        ('PG_PASSWORD', pg_config['password'])
    ]
    
    for var_name, var_value in required_vars:
        if not var_value:
            error_msg = f"variable requerida faltante: {var_name}"
            console_logger.error(f"Error: {error_msg}")
            file_logger.error(error_msg)
            return False
    
    return True

# ============================================================================
# CONEXIONES
# ============================================================================

def test_sql_server_connection(config, file_logger):
    file_logger.info("probando conexion a SQL Server...")
    try:
        connection = pymssql.connect(
            server=config['sql']['host'], 
            port=config['sql']['port'],
            database=config['sql']['database'], 
            user=config['sql']['user'],
            password=config['sql']['password'], 
            timeout=10
        )
        cursor = connection.cursor()
        cursor.execute("SELECT 1 as test")
        cursor.fetchone()
        cursor.close()
        connection.close()
        file_logger.info("conexion SQL Server exitosa")
        return True
    except Exception as error:
        file_logger.error(f"error conectando a SQL Server: {error}")
        return False

def test_postgresql_connection(config, file_logger):
    file_logger.info("probando conexión a PostgreSQL...")
    try:
        connection = psycopg2.connect(
            host=config['pg']['host'], 
            port=config['pg']['port'],
            database=config['pg']['database'], 
            user=config['pg']['user'],
            password=config['pg']['password'], 
            connect_timeout=10
        )
        cursor = connection.cursor()
        cursor.execute("SELECT 1 as test")
        cursor.fetchone()
        cursor.close()
        connection.close()
        file_logger.info("conexion PostgreSQL exitosa")
        return True
    except Exception as error:
        file_logger.error(f"error conectando a PostgreSQL: {error}")
        return False

def test_redis_connection(config, file_logger):
    file_logger.info("probando conexion a Redis...")
    try:
        client = redis.Redis(
            host=config['redis']['host'], 
            port=config['redis']['port'],
            password=config['redis']['password'], 
            db=config['redis']['db'],
            decode_responses=True
        )
        client.ping()
        file_logger.info("conexion Redis exitosa")
        return True
    except Exception as error:
        file_logger.error(f"error conectando a Redis: {error}")
        return False

def test_all_connections(config, file_logger):
    file_logger.info("verificando conexiones a todas las bases de datos...")
    
    sql_ok = test_sql_server_connection(config, file_logger)
    pg_ok = test_postgresql_connection(config, file_logger)
    redis_ok = test_redis_connection(config, file_logger)
    
    all_ok = sql_ok and pg_ok and redis_ok
    
    if all_ok:
        file_logger.info("todas las conexiones exitosas")
    else:
        file_logger.error("fallo al menos una conexion")
    
    return all_ok

def get_redis_client(config):
    return redis.Redis(
        host=config['redis']['host'],
        port=config['redis']['port'],
        password=config['redis']['password'],
        db=config['redis']['db'],
        decode_responses=True
    )

# ============================================================================
# PRODUCER Y CONSUMER
# ============================================================================

def producer_process(config, file_logger, console_logger):
    """producer: SQL Server -> Redis queue"""
    file_logger.info("producer process iniciado")
    redis_client = get_redis_client(config)
    interval = config['sync']['interval']
    
    while not shutdown_event.is_set():
        cycle_start = time.time()
        
        try:
            metrics.producer_cycles += 1
            
            last_sync = _get_last_sync_timestamp(redis_client, file_logger)
            data = _query_sql_server_incremental(config, last_sync, file_logger)
            
            if data:
                _enqueue_records_to_redis(data, redis_client, file_logger, console_logger)
            else:
                file_logger.info("producer: sin cambios nuevos")
                
        except Exception as error:
            console_logger.error(f"error en producer: {error}")
            file_logger.error(f"error detallado en producer: {error}")
            metrics.producer_errors += 1
        
        _wait_for_next_cycle(cycle_start, interval)
    
    file_logger.info("producer process terminado")

def consumer_process(config, file_logger, console_logger):
    """consumer: Redis queue -> PostgreSQL"""
    file_logger.info("consumer process iniciado")
    redis_client = get_redis_client(config)
    batch_size = config['sync']['batch_size']
    
    while not shutdown_event.is_set():
        try:
            batch = _build_batch_from_redis(redis_client, batch_size)
            
            if batch:
                success = _process_batch_to_postgresql(batch, config, file_logger)
                
                if success:
                    _handle_successful_batch(batch, redis_client, file_logger, console_logger)
                else:
                    _handle_failed_batch(batch, console_logger, file_logger)
                    
        except Exception as error:
            console_logger.error(f"error en consumer: {error}")
            file_logger.error(f"error detallado en consumer: {error}")
            metrics.consumer_errors += 1
            time.sleep(1)
    
    file_logger.info("consumer process terminado")

# ============================================================================
# FUNCIONES AUXILIARES PRODUCER
# ============================================================================

def _get_last_sync_timestamp(redis_client, file_logger):
    try:
        metrics.redis_operations += 1
        last_sync_str = redis_client.get(REDIS_TIMESTAMP_KEY)
        
        if last_sync_str:
            last_sync = isoparse(last_sync_str)
            file_logger.info(f"ultimo sync desde Redis: {last_sync}")
            return last_sync
        else:
            file_logger.info("no hay timestamp en Redis, usando por defecto")
            file_logger.info(f"usando timestamp por defecto: {DEFAULT_TIMESTAMP}")
            return DEFAULT_TIMESTAMP
            
    except Exception as error:
        file_logger.error(f"error obteniendo timestamp: {error}")
        metrics.producer_errors += 1
        return DEFAULT_TIMESTAMP

def _query_sql_server_incremental(config, last_sync, file_logger):
    query_start = time.time()
    
    connection = pymssql.connect(
        server=config['sql']['host'], 
        port=config['sql']['port'],
        database=config['sql']['database'], 
        user=config['sql']['user'],
        password=config['sql']['password'], 
        timeout=30
    )
    
    cursor = connection.cursor(as_dict=True)
    query = f"""
        SELECT * FROM {config['sql']['view']} 
        WHERE ULTIMA_MODIFICACION > %s 
        ORDER BY ULTIMA_MODIFICACION ASC
    """
    cursor.execute(query, last_sync)
    data = cursor.fetchall()
    cursor.close()
    connection.close()
    
    query_time = time.time() - query_start
    metrics.producer_queries_time += query_time
    
    if data:
        file_logger.info(f"producer: {len(data)} registros encontrados (query: {query_time:.3f}s)")
    
    return data

def _enqueue_records_to_redis(data, redis_client, file_logger, console_logger):
    console_logger.info(f"producer: {len(data)} nuevos registros encontrados")
    metrics.producer_records_found += len(data)
    
    for record in data:
        record_json = {}
        for key, value in record.items():
            if isinstance(value, datetime):
                record_json[key] = value.isoformat()
            else:
                record_json[key] = value
        
        redis_client.lpush(REDIS_QUEUE_NAME, json.dumps(record_json))
        metrics.redis_operations += 1
    
    metrics.producer_records_queued += len(data)
    file_logger.info(f"producer: {len(data)} registros enviados a cola")

def _wait_for_next_cycle(cycle_start, interval):
    cycle_time = time.time() - cycle_start
    remaining_time = max(0, interval - cycle_time)
    shutdown_event.wait(remaining_time)

# ============================================================================
# FUNCIONES AUXILIARES CONSUMER
# ============================================================================

def _build_batch_from_redis(redis_client, batch_size):
    batch = []
    batch_start = time.time()
    
    for _ in range(batch_size):
        if shutdown_event.is_set():
            break
        
        metrics.redis_operations += 1
        result = redis_client.brpop(REDIS_QUEUE_NAME, timeout=1)
        
        if result:
            queue_name, record_json = result
            record = json.loads(record_json)
            
            for key, value in record.items():
                if isinstance(value, str) and 'T' in value:
                    try:
                        record[key] = isoparse(value)
                    except:
                        pass
            
            batch.append(record)
        else:
            break
    
    if batch:
        batch_time = time.time() - batch_start
        metrics.consumer_batches += 1
        metrics.consumer_batch_time += batch_time
    
    return batch

def _process_batch_to_postgresql(batch, config, file_logger):
    try:
        connection = psycopg2.connect(
            host=config['pg']['host'], 
            port=config['pg']['port'],
            database=config['pg']['database'], 
            user=config['pg']['user'],
            password=config['pg']['password'], 
            connect_timeout=30
        )
        
        cursor = connection.cursor()
        table_name = config['pg']['table_vista']
        
        sample_record = batch[0]
        columns = list(sample_record.keys())
        
        columns_str = ', '.join([f'"{col.lower()}"' for col in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        
        update_columns = [col for col in columns if col.upper() != 'CONDUCE']
        update_set = ', '.join([f'"{col.lower()}" = EXCLUDED."{col.lower()}"' for col in update_columns])
        
        upsert_query = f"""
            INSERT INTO {table_name} ({columns_str}) 
            VALUES ({placeholders})
            ON CONFLICT (conduce) 
            DO UPDATE SET {update_set}, updated_at = CURRENT_TIMESTAMP
        """
        
        for record in batch:
            values = [record[col] for col in columns]
            cursor.execute(upsert_query, values)
            metrics.postgresql_upserts += 1
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as error:
        file_logger.error(f"error en batch PostgreSQL: {error}")
        metrics.postgresql_errors += 1
        try:
            connection.rollback()
            connection.close()
        except:
            pass
        return False

def _handle_successful_batch(batch, redis_client, file_logger, console_logger):
    metrics.consumer_records_processed += len(batch)
    
    console_logger.info(f"consumer: {len(batch)} registros procesados exitosamente")
    file_logger.info(f"consumer: Batch de {len(batch)} procesado exitosamente")
    
    valid_records = [record for record in batch if 'ULTIMA_MODIFICACION' in record]
    if valid_records:
        latest_timestamp = max(record['ULTIMA_MODIFICACION'] for record in valid_records)
        _update_last_sync_timestamp(redis_client, latest_timestamp, file_logger)

def _handle_failed_batch(batch, console_logger, file_logger):
    console_logger.error(f"Error procesando batch de {len(batch)} registros")
    file_logger.error("Error detallado procesando batch")
    metrics.consumer_errors += 1

def _update_last_sync_timestamp(redis_client, timestamp, file_logger):
    try:
        metrics.redis_operations += 1
        timestamp_str = timestamp.isoformat()
        redis_client.set(REDIS_TIMESTAMP_KEY, timestamp_str)
        file_logger.info(f"timestamp actualizado en Redis: {timestamp}")
        return True
    except Exception as error:
        file_logger.error(f"error actualizando timestamp: {error}")
        metrics.producer_errors += 1
        return False

# ============================================================================
# ESTADISTICAS
# ============================================================================

def log_compact_stats(redis_client, console_logger, file_logger):
    try:
        queue_size = redis_client.llen(REDIS_QUEUE_NAME)
        total_errors = metrics.get_total_errors()
        
        if metrics.consumer_records_processed > 0 or total_errors > 0:
            console_logger.info(f"[STATS] Uptime: {metrics.get_uptime_formatted()} | "
                              f"Procesados: {metrics.consumer_records_processed} | "
                              f"Cola: {queue_size} | "
                              f"Velocidad: {metrics.get_consumer_rate():.1f}/sec | "
                              f"Errores: {total_errors}")
        else:
            console_logger.info(f"[STATS] Uptime: {metrics.get_uptime_formatted()} | sistema activo | sin errores")
        
        file_logger.info(f"stats detalladas - producer cycles: {metrics.producer_cycles}, "
                        f"Records found: {metrics.producer_records_found}, "
                        f"Batches: {metrics.consumer_batches}, "
                        f"Redis ops: {metrics.redis_operations}")
        
    except Exception as error:
        file_logger.error(f"error mostrando stats: {error}")

def stats_reporter_process(config, file_logger, console_logger):
    file_logger.info("stats Reporter process iniciado")
    redis_client = get_redis_client(config)
    stats_interval = config['sync']['stats_interval']
    
    while not shutdown_event.is_set():
        shutdown_event.wait(stats_interval)
        if not shutdown_event.is_set():
            log_compact_stats(redis_client, console_logger, file_logger)
    
    file_logger.info("stats reporter process terminado")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print(f"sync-service v{VERSION} - iniciando...")
    
    file_logger, console_logger = setup_logging()
    
    config = load_config(file_logger, console_logger)
    if not config:
        console_logger.error("error en configuracion")
        sys.exit(1)

    _log_configuration_summary(config, file_logger)
    
    if not test_all_connections(config, file_logger):
        console_logger.error("error de conexion a bases de datos")
        sys.exit(1)
    
    console_logger.info("sync service iniciado - todas las conexiones OK")
    
    threads = _create_worker_threads(config, file_logger, console_logger)
    _start_all_threads(threads, file_logger)
    
    initial_stats_timer = threading.Timer(30.0, 
        lambda: log_compact_stats(get_redis_client(config), console_logger, file_logger))
    initial_stats_timer.start()
    
    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(1)
    except KeyboardInterrupt:
        console_logger.info("deteniendo servicio...")
    
    _shutdown_gracefully(threads, config, console_logger, file_logger)

def _log_configuration_summary(config, file_logger):
    file_logger.info(f"SQL Server: {config['sql']['host']}:{config['sql']['port']}")
    file_logger.info(f"PostgreSQL: {config['pg']['host']}:{config['pg']['port']}")
    file_logger.info(f"Redis: {config['redis']['host']}:{config['redis']['port']}")
    file_logger.info(f"Configuración: intervalo={config['sync']['interval']}s, "
                    f"batch={config['sync']['batch_size']}, "
                    f"stats={config['sync']['stats_interval']}s")

def _create_worker_threads(config, file_logger, console_logger):
    return {
        'producer': threading.Thread(
            target=producer_process, 
            args=(config, file_logger, console_logger), 
            name="producer", 
            daemon=True
        ),
        'consumer': threading.Thread(
            target=consumer_process, 
            args=(config, file_logger, console_logger), 
            name="consumer", 
            daemon=True
        ),
        'stats': threading.Thread(
            target=stats_reporter_process,
            args=(config, file_logger, console_logger),
            name="StatsReporter", 
            daemon=True
        )
    }

def _start_all_threads(threads, file_logger):
    for name, thread in threads.items():
        thread.start()
        file_logger.info(f"Thread {name} iniciado")
    
    file_logger.info("todos los procesos iniciados exitosamente")

def _shutdown_gracefully(threads, config, console_logger, file_logger):
    shutdown_event.set()
    
    log_compact_stats(get_redis_client(config), console_logger, file_logger)
    
    for name, thread in threads.items():
        thread.join(timeout=5)
        file_logger.info(f"Thread {name} terminado")
    
    console_logger.info("Servicio detenido correctamente")
    file_logger.info("Sistema detenido limpiamente")

if __name__ == "__main__":
    main()