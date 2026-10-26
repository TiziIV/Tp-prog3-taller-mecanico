-- ==============================================================================
-- Caso C-14: Verificación de Integridad de Sólo Agregado y Claves Foráneas
-- ==============================================================================
-- Demuestra el rechazo de UPDATE y DELETE en las tres tablas append-only mediante
-- el disparador de la base de datos (RN-15), y el rechazo por FK de un estado
-- inexistente en el catálogo (RN-19).
-- ==============================================================================

-- 1. Intentos sobre historial_estado_orden (debe ser rechazado por disparador)
UPDATE historial_estado_orden SET hasta_estado = 'TERMINADA' WHERE id = 1;

DELETE FROM historial_estado_orden WHERE id = 1;

-- 2. Intentos sobre movimiento_stock (debe ser rechazado por disparador)
UPDATE movimiento_stock SET cantidad = 99 WHERE id = 1;

DELETE FROM movimiento_stock WHERE id = 1;

-- 3. Intentos sobre historial_precio_repuesto (debe ser rechazado por disparador)
UPDATE historial_precio_repuesto SET precio_nuevo = 9999 WHERE id = 1;

DELETE FROM historial_precio_repuesto WHERE id = 1;

-- 4. Intento de orden con estado no presente en el catálogo (debe ser rechazado por FK)
UPDATE orden_trabajo SET estado = 'ESTADO_INEXISTENTE' WHERE id = 1;
