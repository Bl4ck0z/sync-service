-- Script para crear syncdb
-- Autor: Joel Santana H.
-- Fecha: 16/7/2025

-- =====================================================
-- CREAR BASE DE DATOS
-- =====================================================

CREATE DATABASE syncdb;
\c syncdb;

-- =====================================================
-- TABLA datos_vista (solo lectura)
-- =====================================================

DROP TABLE IF EXISTS datos_vista CASCADE;

CREATE TABLE datos_vista (
    sync_id VARCHAR(50),
    conduce VARCHAR(50) PRIMARY KEY,
    fecha_emision TIMESTAMP,
    facturado BOOLEAN DEFAULT FALSE,
    numero_factura VARCHAR(50),
    codigo_cliente VARCHAR(20),
    cliente VARCHAR(500),
    ultima_modificacion TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_datos_vista_fecha ON datos_vista(fecha_emision);
CREATE INDEX idx_datos_vista_cliente ON datos_vista(codigo_cliente);
CREATE INDEX idx_datos_vista_facturado ON datos_vista(facturado);

-- =====================================================
-- TABLA datos_trabajo (CRUD usuarios)
-- =====================================================

CREATE TABLE datos_trabajo (
    id SERIAL PRIMARY KEY,
    conduce VARCHAR(50) NOT NULL,
    nota TEXT,
    ruta VARCHAR(100),
    trabajado BOOLEAN DEFAULT FALSE,
    preparador VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_datos_trabajo_conduce UNIQUE (conduce),
    CONSTRAINT fk_datos_trabajo_conduce 
        FOREIGN KEY (conduce) 
        REFERENCES datos_vista(conduce) 
        ON DELETE CASCADE
);

CREATE INDEX idx_datos_trabajo_conduce ON datos_trabajo(conduce);
CREATE INDEX idx_datos_trabajo_trabajado ON datos_trabajo(trabajado);
CREATE INDEX idx_datos_trabajo_ruta ON datos_trabajo(ruta);
CREATE INDEX idx_datos_trabajo_preparador ON datos_trabajo(preparador);

-- =====================================================
-- TRIGGERS para updated_at
-- =====================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$ LANGUAGE 'plpgsql';

CREATE TRIGGER update_datos_vista_updated_at 
    BEFORE UPDATE ON datos_vista 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_datos_trabajo_updated_at 
    BEFORE UPDATE ON datos_trabajo 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- VERIFICAR CREACIÓN
-- =====================================================

\dt
SELECT 'syncdb creado exitosamente' AS resultado;