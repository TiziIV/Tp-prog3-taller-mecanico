# Trabajo Práctico: Taller Mecánico — Del Objeto a la Transacción

**Materia:** Programación III (UTN - Tecnicatura Universitaria en Programación)  
**Stack:** FastAPI (>= 0.111), SQLModel (>= 0.0.24), SQLAlchemy 2.0 (asincrónico con asyncpg), PostgreSQL 16, Alembic (>= 1.13 async), Pydantic Settings (>= 2.0), PyJWT, Bcrypt.

---

## 1. Arquitectura y Estructura en Capas

El proyecto implementa una arquitectura desacoplada y asincrónica en 6 capas funcionales:
`Router` → `Service` → `Unit of Work` → `Repository` → `Model`

```
CAP1A6/
├── app/
│   ├── core/
│   │   ├── config.py           # Settings leídas con pydantic-settings y @computed_field
│   │   ├── database.py         # Motor async, sesión y fábrica en app.state, get_session
│   │   ├── security.py         # Bcrypt off-thread con semáforo y gestión de JWT
│   │   ├── dependencies.py     # Autenticación por cookie, verificación de roles vigentes y cambio obligatorio
│   │   ├── repository.py       # BaseRepository[T] y SoftDeleteRepository[T]
│   │   ├── paginacion.py       # Envoltorio {items, total, page, size, pages}
│   │   └── unit_of_work.py     # Unit of Work base como context manager asincrónico
│   └── modules/
│       ├── health/             # Endpoints /health/live y /health/ready
│       ├── usuarios/           # Usuario, AsignacionRol, IntentoAcceso, EventoSeguridad
│       ├── clientes/           # Cliente, Vehiculo
│       ├── repuestos/          # Repuesto, MovimientoStock, HistorialPrecio
│       └── ordenes/            # EstadoOrden, OrdenTrabajo, ItemOrden, HistorialEstadoOrden
├── migrations/                 # Migraciones de Alembic (plantilla async)
│   └── versions/
│       ├── ..._crear_tablas_iniciales.py   # Migración 1 autogenerada
│       └── ..._triggers_solo_agregado.py    # Migración 2 manual para tablas append-only
├── test/
│   ├── test_casos.py           # Suite de pruebas automatizadas (C-01 a C-19)
│   ├── verificar_c15_n_plus_1.py # Script de verificación de consultas SQL C-15
│   ├── solo_agregado.sql       # Script SQL para verificación de C-14 en psql
│   └── casos_prueba.http       # Archivo REST Client con todos los casos de prueba
├── alembic.ini                 # Configuración de migraciones (sin credenciales hardcodeadas)
├── env.example                 # Plantilla de variables de entorno (sin secretos)
├── requirements.txt            # Dependencias del proyecto
├── seed.py                     # Carga de catálogo, usuarios y datos iniciales
└── main.py                     # Lifespan, grupos de rutas y manejadores de error
```

---

## 2. Requisitos Previos

- Python 3.12 o superior.
- PostgreSQL 16 instalado y en ejecución en el puerto 5432.
- Una base de datos creada en PostgreSQL (por ejemplo `taller_mecanico`).

---

## 3. Puesta en Marcha Paso a Paso

### Paso 1: Clonar el repositorio y entrar al directorio
```bash
cd "e:\Tiziano Facultad\2DO SEMESTRE\PROGRAMACION\PROFE ESPEJO\CAP1A6"
```

### Paso 2: Crear y activar el entorno virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Paso 3: Instalar dependencias
```powershell
pip install -r requirements.txt
```

### Paso 4: Configurar variables de entorno (`.env`)
Crear el archivo `.env` a partir de `env.example`:
```powershell
Copy-Item env.example .env
```

Generar una clave segura para la firma de tokens JWT ejecutando en Python:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
Copiar la cadena generada y asignarla a `JWT_SECRET_KEY` dentro del archivo `.env`, completando también la contraseña de PostgreSQL (`POSTGRES_PASSWORD`).

Ejemplo de archivo `.env`:
```ini
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=taller_mecanico
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
SQL_ECHO=false

BCRYPT_ROUNDS=12
JWT_SECRET_KEY=b9c75491644e93306b9d12955cab7ee422730559869c0621f3bc5ca5b8c57313
JWT_ALGORITHM=HS256
JWT_EXPIRATION_SECONDS=1800
COOKIE_SECURE=false
```

### Paso 5: Aplicar migraciones con Alembic
```powershell
alembic upgrade head
```

### Paso 6: Poblar la base de datos inicial con `seed.py`
```powershell
python seed.py
```

### Paso 7: Iniciar el servidor de desarrollo
```powershell
uvicorn main:app --reload --port 8000
```
La documentación interactiva OpenAPI estará disponible en: `http://localhost:8000/docs`.

---

## 4. Ejecución de Pruebas Automatizadas

Para correr la suite de pruebas completa:
```powershell
pytest -v test/test_casos.py
```

---

## 5. Evidencias de Evaluación

### Evidencia del Caso C-14: Integridad de Sólo Agregado y Clave Foránea

Comando ejecutado contra PostgreSQL:
```powershell
psql -U postgres -h localhost -p 5432 -d taller_mecanico -f test/solo_agregado.sql
```

**Salida obtenida en consola:**
```text
psql:test/solo_agregado.sql:10: ERROR:  Operación no permitida: la tabla historial_estado_orden es de sólo agregado (append-only)
CONTEXTO:  función PL/pgSQL rechazar_modificacion_o_borrado_solo_agregado() en la línea 3 en RAISE
psql:test/solo_agregado.sql:12: ERROR:  Operación no permitida: la tabla historial_estado_orden es de sólo agregado (append-only)
CONTEXTO:  función PL/pgSQL rechazar_modificacion_o_borrado_solo_agregado() en la línea 3 en RAISE
psql:test/solo_agregado.sql:15: ERROR:  Operación no permitida: la tabla movimiento_stock es de sólo agregado (append-only)
CONTEXTO:  función PL/pgSQL rechazar_modificacion_o_borrado_solo_agregado() en la línea 3 en RAISE
psql:test/solo_agregado.sql:17: ERROR:  Operación no permitida: la tabla movimiento_stock es de sólo agregado (append-only)
CONTEXTO:  función PL/pgSQL rechazar_modificacion_o_borrado_solo_agregado() en la línea 3 en RAISE
psql:test/solo_agregado.sql:20: ERROR:  Operación no permitida: la tabla historial_precio_repuesto es de sólo agregado (append-only)
CONTEXTO:  función PL/pgSQL rechazar_modificacion_o_borrado_solo_agregado() en la línea 3 en RAISE
psql:test/solo_agregado.sql:22: ERROR:  Operación no permitida: la tabla historial_precio_repuesto es de sólo agregado (append-only)
CONTEXTO:  función PL/pgSQL rechazar_modificacion_o_borrado_solo_agregado() en la línea 3 en RAISE
psql:test/solo_agregado.sql:25: ERROR:  inserción o actualización en la tabla «orden_trabajo» viola la llave foránea «orden_trabajo_estado_fkey»
DETALLE:  La llave (estado)=(ESTADO_INEXISTENTE) no está presente en la tabla «estado_orden».
```

---

### Evidencia del Caso C-15: Prevención del Problema N+1 en Lecturas

Comando ejecutado:
```powershell
python test/verificar_c15_n_plus_1.py
```

**Fragmento de la consola demostrando número fijo de consultas SQL:**
```text
============================================================
CONSULTAS EJECUTADAS PARA ORDEN CON 2 ITEMS: 6
[1] SELECT orden_trabajo.id, orden_trabajo.vehiculo_id, orden_trabajo.mecanico_id, orden_trabajo.estado, orden_trabajo.falla, orden_trabajo.creada_en, orden_trabajo.total ...
[2] SELECT historial_estado_orden.orden_id, historial_estado_orden.id, historial_estado_orden.desde_estado, historial_estado_orden.hasta_estado, historial_estado_orden.usuario_id, historial_estado_orden.cuando ...
[3] SELECT vehiculo.id, vehiculo.cliente_id, vehiculo.patente, vehiculo.marca, vehiculo.modelo, vehiculo.anio, vehiculo.borrado_en ...
[4] SELECT item_orden.orden_id, item_orden.id, item_orden.repuesto_id, item_orden.cantidad, item_orden.precio_unitario ...
[5] SELECT cliente.id, cliente.usuario_id, cliente.nombre, cliente.documento, cliente.telefono ...
[6] SELECT repuesto.id, repuesto.codigo, repuesto.descripcion, repuesto.precio, repuesto.stock, repuesto.borrado_en ...

============================================================
CONSULTAS EJECUTADAS PARA ORDEN CON 4 ITEMS: 6
[1] SELECT orden_trabajo.id, orden_trabajo.vehiculo_id, orden_trabajo.mecanico_id, orden_trabajo.estado, orden_trabajo.falla, orden_trabajo.creada_en, orden_trabajo.total ...
[2] SELECT historial_estado_orden.orden_id, historial_estado_orden.id, historial_estado_orden.desde_estado, historial_estado_orden.hasta_estado, historial_estado_orden.usuario_id, historial_estado_orden.cuando ...
[3] SELECT vehiculo.id, vehiculo.cliente_id, vehiculo.patente, vehiculo.marca, vehiculo.modelo, vehiculo.anio, vehiculo.borrado_en ...
[4] SELECT item_orden.orden_id, item_orden.id, item_orden.repuesto_id, item_orden.cantidad, item_orden.precio_unitario ...
[5] SELECT cliente.id, cliente.usuario_id, cliente.nombre, cliente.documento, cliente.telefono ...
[6] SELECT repuesto.id, repuesto.codigo, repuesto.descripcion, repuesto.precio, repuesto.stock, repuesto.borrado_en ...
============================================================

¡VERIFICACIÓN EXITOSA! Ambas órdenes ejecutaron exactamente 6 consultas SQL (N+1 evitado).
```
