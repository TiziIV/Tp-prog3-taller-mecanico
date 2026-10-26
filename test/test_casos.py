import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from seed import seed


@pytest.fixture(autouse=True)
async def reset_db():
    async with app.router.lifespan_context(app):
        await seed()
        yield


@pytest.mark.asyncio
async def test_c01_parametro_ruta_no_entero():
    """C-01: Un parámetro de ruta que no es entero, con la sesión iniciada -> 422, sin ejecutar el handler."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Iniciar sesión como ADMIN
        res_login = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        assert res_login.status_code == 200
        cookies = res_login.cookies

        # Parámetro 'abc' en lugar de un int
        res = await client.get("/usuarios/abc/roles", cookies=cookies)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_c02_registro_y_duplicados():
    """C-02: Registro; correo y documento repetidos -> 201; 409 con mensaje propio, y no deja filas sueltas."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Registro exitoso
        res = await client.post(
            "/auth/registro",
            json={
                "email": "nuevo_cliente@example.com",
                "nombre": "Nuevo Cliente",
                "password": "Password123!",
                "documento": "40999888",
                "telefono": "1122334455",
            },
        )
        assert res.status_code == 201

        # Correo repetido -> 409
        res_dup_email = await client.post(
            "/auth/registro",
            json={
                "email": "nuevo_cliente@example.com",
                "nombre": "Otro Cliente",
                "password": "Password123!",
                "documento": "99999999",
                "telefono": "1122334455",
            },
        )
        assert res_dup_email.status_code == 409
        assert "correo" in res_dup_email.json()["detail"].lower()

        # Documento repetido -> 409
        res_dup_doc = await client.post(
            "/auth/registro",
            json={
                "email": "otro_mail@example.com",
                "nombre": "Otro Cliente",
                "password": "Password123!",
                "documento": "40999888",
                "telefono": "1122334455",
            },
        )
        assert res_dup_doc.status_code == 409
        assert "documento" in res_dup_doc.json()["detail"].lower()


@pytest.mark.asyncio
async def test_c03_cookie_login():
    """C-03: Cookie del login HttpOnly, SameSite=Lax, Max-Age; cuerpo sin token; sin cookie o con Authorization -> 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        assert res.status_code == 200
        set_cookie = res.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie
        assert "samesite=lax" in set_cookie.lower()
        assert "max-age" in set_cookie.lower()

        body = res.json()
        assert "access_token" not in body
        assert "token" not in body
        assert body["mensaje"] == "Sesión iniciada"
        token_val = res.cookies.get("access_token")

        # Petición protegida sin cookie -> 401
        client.cookies.clear()
        res_no_cookie = await client.get("/usuarios/1/roles")
        assert res_no_cookie.status_code == 401

        # Petición con Authorization Bearer -> 401 (debe ignorarse la cabecera)
        res_auth_header = await client.get(
            "/usuarios/1/roles",
            headers={"Authorization": f"Bearer {token_val}"},
        )
        assert res_auth_header.status_code == 401


@pytest.mark.asyncio
async def test_c04_timing_y_mismo_mensaje_login():
    """C-04: Correo existente con contraseña mala, y correo inexistente -> 401 con el mismo cuerpo y tiempo parecido."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Existente contraseña mala
        t0 = asyncio.get_event_loop().time()
        res1 = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "WrongPassword!"},
        )
        t1 = asyncio.get_event_loop().time()
        dur1 = t1 - t0

        # Inexistente
        t2 = asyncio.get_event_loop().time()
        res2 = await client.post(
            "/auth/login",
            json={"email": "noexiste@example.com", "password": "WrongPassword!"},
        )
        t3 = asyncio.get_event_loop().time()
        dur2 = t3 - t2

        assert res1.status_code == 401
        assert res2.status_code == 401
        assert res1.json() == res2.json()
        # Ambos tardan un tiempo de magnitud similar (ambos ejecutan bcrypt)
        assert abs(dur1 - dur2) < 0.5


@pytest.mark.asyncio
async def test_c05_limite_intentos_login():
    """C-05: Seis intentos fallidos seguidos -> El sexto, 429 con Retry-After y en pocos ms; 5 en intento_acceso."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            r = await client.post(
                "/auth/login",
                json={"email": "test_brute@example.com", "password": "WrongPassword!"},
            )
            assert r.status_code == 401

        t0 = asyncio.get_event_loop().time()
        res_sixth = await client.post(
            "/auth/login",
            json={"email": "test_brute@example.com", "password": "WrongPassword!"},
        )
        t1 = asyncio.get_event_loop().time()

        assert res_sixth.status_code == 429
        assert "Retry-After" in res_sixth.headers
        assert (t1 - t0) < 0.1  # Responde en pocos milisegundos sin pasar por bcrypt


@pytest.mark.asyncio
async def test_c06_401_vs_403_y_lo_propio():
    """C-06: Sin rol 403; el cliente ve su orden (200) y no la ajena (403)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login Laura (cliente@example.com)
        res_login = await client.post(
            "/auth/login",
            json={"email": "cliente@example.com", "password": "Password123!"},
        )
        cookies = res_login.cookies

        # Intento de acceso a ruta de ADMIN -> 403
        res_admin_route = await client.get("/eventos", cookies=cookies)
        assert res_admin_route.status_code == 403

        # Orden 1 es de Laura -> 200
        res_orden_propia = await client.get("/ordenes/1", cookies=cookies)
        assert res_orden_propia.status_code == 200

        # Orden 2 es de Jorge -> 403
        res_orden_ajena = await client.get("/ordenes/2", cookies=cookies)
        assert res_orden_ajena.status_code == 403


@pytest.mark.asyncio
async def test_c07_revocar_rol_sesion_abierta_y_vencimientos():
    """C-07: Revocar rol con sesión abierta; vencimientos inválidos."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login recepcion
        res_rec = await client.post(
            "/auth/login",
            json={"email": "recepcion@example.com", "password": "Password123!"},
        )
        cookies_rec = res_rec.cookies

        # Login admin
        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies_adm = res_adm.cookies

        # Recepción puede crear clientes inicialmente
        res_test = await client.post(
            "/clientes",
            json={"nombre": "Test Cli", "documento": "11111111", "telefono": "123"},
            cookies=cookies_rec,
        )
        assert res_test.status_code == 201

        # Admin revoca el rol RECEPCION
        # usuario_id de recepcion es 3
        yo_rec = await client.get("/auth/yo", cookies=cookies_rec)
        rec_id = yo_rec.json()["usuario"]["id"]

        rev_res = await client.delete(f"/usuarios/{rec_id}/roles/RECEPCION", cookies=cookies_adm)
        assert rev_res.status_code == 200

        # En la siguiente petición con la misma cookie, recepcion recibe 403
        res_test2 = await client.post(
            "/clientes",
            json={"nombre": "Test Cli 2", "documento": "22222222", "telefono": "123"},
            cookies=cookies_rec,
        )
        assert res_test2.status_code == 403

        # /auth/yo muestra que en BD ya no lo tiene pero en token sí
        yo_despues = await client.get("/auth/yo", cookies=cookies_rec)
        assert "RECEPCION" not in yo_despues.json()["roles_vigentes"]
        assert "RECEPCION" in yo_despues.json()["roles_token"]

        # Vencimiento en el pasado -> 422
        pasado = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        res_pasado = await client.post(
            f"/usuarios/{rec_id}/roles",
            json={"rol": "RECEPCION", "vence_en": pasado},
            cookies=cookies_adm,
        )
        assert res_pasado.status_code == 422

        # Vencimiento sin zona horaria -> 422
        sin_tz = "2030-01-01T12:00:00"
        res_sin_tz = await client.post(
            f"/usuarios/{rec_id}/roles",
            json={"rol": "RECEPCION", "vence_en": sin_tz},
            cookies=cookies_adm,
        )
        assert res_sin_tz.status_code == 422


@pytest.mark.asyncio
async def test_c08_autoproteccion_admin():
    """C-08: El administrador no se revoca su ADMIN: 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies_adm = res_adm.cookies
        yo = await client.get("/auth/yo", cookies=cookies_adm)
        admin_id = yo.json()["usuario"]["id"]

        # Intento de revocarse a sí mismo -> 409
        res = await client.delete(f"/usuarios/{admin_id}/roles/ADMIN", cookies=cookies_adm)
        assert res.status_code == 409


@pytest.mark.asyncio
async def test_c09_cambio_obligatorio_password():
    """C-09: Bloqueado (403) salvo /auth; tras cambio cookie nueva vale y anterior 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login nuevo@example.com (tiene debe_cambiar_password=True)
        res_login = await client.post(
            "/auth/login",
            json={"email": "nuevo@example.com", "password": "Password123!"},
        )
        assert res_login.status_code == 200
        assert res_login.json()["debe_cambiar_password"] is True
        old_cookies = res_login.cookies

        # Rutas protegidas dan 403
        res_rep = await client.get("/repuestos", cookies=old_cookies)
        assert res_rep.status_code == 403

        # /auth/yo funciona (está en grupo abierto)
        res_yo = await client.get("/auth/yo", cookies=old_cookies)
        assert res_yo.status_code == 200

        # Cambiar contraseña
        res_cambio = await client.post(
            "/auth/cambiar-password",
            json={
                "password_actual": "Password123!",
                "password_nueva": "NewSecurePassword456!",
            },
            cookies=old_cookies,
        )
        assert res_cambio.status_code == 200
        new_cookies = res_cambio.cookies

        # La cookie nueva permite acceder al grupo protegido
        res_rep_ok = await client.get("/repuestos", cookies=new_cookies)
        assert res_rep_ok.status_code == 200

        # La cookie anterior da 401
        res_rep_old = await client.get("/repuestos", cookies=old_cookies)
        assert res_rep_old.status_code == 401


@pytest.mark.asyncio
async def test_c10_alta_orden():
    """C-10: 201 con precios copiados, total e historial; con repuesto inexistente 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/auth/login",
            json={"email": "recepcion@example.com", "password": "Password123!"},
        )
        cookies = res_login.cookies

        # Alta con 2 ítems
        payload = {
            "vehiculo_id": 2,
            "falla": "Ruido al frenar",
            "items": [
                {"repuesto_id": 2, "cantidad": 1},
                {"repuesto_id": 4, "cantidad": 3},
            ],
        }
        res = await client.post("/ordenes", json=payload, cookies=cookies)
        assert res.status_code == 201
        data = res.json()
        assert data["estado"] == "PENDIENTE"
        assert Decimal(str(data["total"])) == Decimal("68000.00")
        assert len(data["items"]) == 2
        assert len(data["historial"]) == 1
        assert data["historial"][0]["hasta_estado"] == "PENDIENTE"

        # Repuesto inexistente -> 409
        payload_bad = {
            "vehiculo_id": 2,
            "falla": "Falla prueba",
            "items": [{"repuesto_id": 99999, "cantidad": 1}],
        }
        res_bad = await client.post("/ordenes", json=payload_bad, cookies=cookies)
        assert res_bad.status_code == 409


@pytest.mark.asyncio
async def test_c11_terminar_orden_sin_stock():
    """C-11: Terminar orden 2 pidiendo más bujías de las disponibles -> 409 y estado intacto."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_login = await client.post(
            "/auth/login",
            json={"email": "mecanico@example.com", "password": "Password123!"},
        )
        cookies = res_login.cookies

        # Orden 2 está asignada a mecanico@example.com
        res = await client.post("/ordenes/2/terminar", cookies=cookies)
        assert res.status_code == 409
        assert "stock" in res.json()["detail"].lower()

        # Verificar que sigue en EN_REPARACION
        res_orden = await client.get("/ordenes/2", cookies=cookies)
        assert res_orden.json()["estado"] == "EN_REPARACION"


@pytest.mark.asyncio
async def test_c12_reponer_y_terminar_orden():
    """C-12: Reponer y terminar la orden 2 -> 200, baja stock, movimientos e historial."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Admin repone 10 bujías (repuesto id=3)
        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies_adm = res_adm.cookies

        res_rep = await client.post(
            "/repuestos/3/reponer",
            json={"cantidad": 10, "motivo": "Reposición de prueba"},
            cookies=cookies_adm,
        )
        assert res_rep.status_code == 200
        assert res_rep.json()["stock"] == 12  # 2 iniciales + 10

        # Mecánico termina orden 2
        res_mec = await client.post(
            "/auth/login",
            json={"email": "mecanico@example.com", "password": "Password123!"},
        )
        cookies_mec = res_mec.cookies

        res_term = await client.post("/ordenes/2/terminar", cookies=cookies_mec)
        assert res_term.status_code == 200
        assert res_term.json()["estado"] == "TERMINADA"

        # Verificar stock actualizado: 12 - 4 = 8
        res_bujia = await client.get("/repuestos/3", cookies=cookies_adm)
        assert res_bujia.json()["stock"] == 8


@pytest.mark.asyncio
async def test_c13_cancelar_orden():
    """C-13: El dueño cancela orden pendiente (200); ajena 403; terminada 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Laura es dueña de orden 1
        res_laura = await client.post(
            "/auth/login",
            json={"email": "cliente@example.com", "password": "Password123!"},
        )
        cookies_laura = res_laura.cookies

        # Dueño cancela orden pendiente -> 200
        res_canc = await client.post("/ordenes/1/cancelar", cookies=cookies_laura)
        assert res_canc.status_code == 200
        assert res_canc.json()["estado"] == "CANCELADA"

        # Orden ajena (orden 2 de Jorge) -> 403
        res_ajena = await client.post("/ordenes/2/cancelar", cookies=cookies_laura)
        assert res_ajena.status_code == 403


@pytest.mark.asyncio
async def test_c16_busqueda_y_paginacion_repuestos():
    """C-16: Búsqueda con sql injection, paginación, filtros y validación extra=forbid."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies = res_adm.cookies

        # Inyección SQL devuelve lista vacía y total 0 (parámetros ligados)
        res_inj = await client.get("/repuestos?q=' OR '1'='1", cookies=cookies)
        assert res_inj.status_code == 200
        assert res_inj.json()["total"] == 0
        assert res_inj.json()["items"] == []

        # q=freno&size=1 -> total 1, pages 1
        res_q = await client.get("/repuestos?q=freno&size=1", cookies=cookies)
        assert res_q.status_code == 200
        assert res_q.json()["total"] == 1
        assert res_q.json()["pages"] == 1

        # page=2 cuando hay 1 página -> 422
        res_page2 = await client.get("/repuestos?q=freno&size=1&page=2", cookies=cookies)
        assert res_page2.status_code == 422

        # size=500 -> 422
        res_size500 = await client.get("/repuestos?size=500", cookies=cookies)
        assert res_size500.status_code == 422

        # PATCH intentando modificar stock -> 422 (extra="forbid")
        res_patch_stock = await client.patch(
            "/repuestos/1",
            json={"stock": 999},
            cookies=cookies,
        )
        assert res_patch_stock.status_code == 422


@pytest.mark.asyncio
async def test_c17_catalogo_estados_y_filtro_invalido():
    """C-17: Catálogo de estados; filtrar órdenes por estado no declarado -> 422; sin sesión -> 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Sin sesión -> 401
        res_no_auth = await client.get("/estados-orden")
        assert res_no_auth.status_code == 401

        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies = res_adm.cookies

        # Catálogo ordenado por posición
        res_cat = await client.get("/estados-orden", cookies=cookies)
        assert res_cat.status_code == 200
        estados = res_cat.json()
        assert len(estados) == 4
        assert estados[0]["codigo"] == "PENDIENTE"
        assert estados[1]["codigo"] == "EN_REPARACION"
        assert estados[2]["codigo"] == "TERMINADA" and estados[2]["es_final"] is True
        assert estados[3]["codigo"] == "CANCELADA" and estados[3]["es_final"] is True

        # Filtrar órdenes por un estado no declarado en el contrato -> 422
        res_filtro_bad = await client.get("/ordenes?estado=INVENTADO", cookies=cookies)
        assert res_filtro_bad.status_code == 422


@pytest.mark.asyncio
async def test_c18_cambio_precio_e_historial():
    """C-18: Cambiar precio y luego sólo descripción en repuesto."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies = res_adm.cookies

        # Cambiar precio de filtro de aceite (id=1, precio inicial 8500.00)
        res_patch1 = await client.patch(
            "/repuestos/1",
            json={"precio": "9000.00"},
            cookies=cookies,
        )
        assert res_patch1.status_code == 200

        # Ver historial de precios -> ahora tiene 2 líneas (la de seed y la nueva)
        res_hist1 = await client.get("/repuestos/1/precios", cookies=cookies)
        assert len(res_hist1.json()) == 2
        assert Decimal(str(res_hist1.json()[0]["precio_nuevo"])) == Decimal("9000.00")

        # Segundo PATCH cambiando sólo descripción
        res_patch2 = await client.patch(
            "/repuestos/1",
            json={"descripcion": "Filtro de aceite premium"},
            cookies=cookies,
        )
        assert res_patch2.status_code == 200

        # Historial de precios NO debe agregar ninguna fila
        res_hist2 = await client.get("/repuestos/1/precios", cookies=cookies)
        assert len(res_hist2.json()) == 2


@pytest.mark.asyncio
async def test_c19_baja_vehiculo_y_reutilizacion_patente():
    """C-19: Dar de baja vehículo sin órdenes (204) y registrarlo con la misma patente para otro cliente (201)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_adm = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "Password123!"},
        )
        cookies = res_adm.cookies

        # Vehículo 2 de Laura (id=2, patente AA123BB) no tiene órdenes
        res_baja = await client.delete("/vehiculos/2", cookies=cookies)
        assert res_baja.status_code == 204

        # Registrar la misma patente para Jorge (cliente_id=2) -> 201
        res_reg = await client.post(
            "/clientes/2/vehiculos",
            json={
                "patente": "AA123BB",
                "marca": "Volkswagen",
                "modelo": "Gol",
                "anio": 2018,
            },
            cookies=cookies,
        )
        assert res_reg.status_code == 201

        # Registrar otra vez la misma patente mientras está activa -> 409
        res_reg_dup = await client.post(
            "/clientes/1/vehiculos",
            json={
                "patente": "AA123BB",
                "marca": "Volkswagen",
                "modelo": "Gol",
                "anio": 2018,
            },
            cookies=cookies,
        )
        assert res_reg_dup.status_code == 409
