import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import create_engine, create_session_factory
from app.core.security import get_password_hash
from app.modules.usuarios.models import (
    Usuario,
    AsignacionRol,
    EventoSeguridad,
)
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.repuestos.models import (
    Repuesto,
    MovimientoStock,
    HistorialPrecio,
)
from app.modules.ordenes.models import (
    EstadoOrden,
    OrdenTrabajo,
    ItemOrden,
    HistorialEstadoOrden,
)


async def seed() -> None:
    engine = create_engine()
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        # 1. Truncate all tables and restart identities
        print("Truncating tables...")
        await session.execute(
            text(
                """
                TRUNCATE TABLE 
                    item_orden,
                    movimiento_stock,
                    historial_estado_orden,
                    historial_precio_repuesto,
                    orden_trabajo,
                    vehiculo,
                    cliente,
                    asignacion_rol,
                    intento_acceso,
                    evento_seguridad,
                    repuesto,
                    usuario,
                    estado_orden
                RESTART IDENTITY CASCADE;
                """
            )
        )
        await session.commit()

        now = datetime.now(timezone.utc)
        default_password = "Password123!"
        hashed_pw = await get_password_hash(default_password)

        # 2. Catálogo de estados (se carga primero)
        print("Seeding estado_orden...")
        estados = [
            EstadoOrden(
                codigo="PENDIENTE",
                descripcion="Orden creada pendiente de atención",
                posicion=1,
                es_final=False,
            ),
            EstadoOrden(
                codigo="EN_REPARACION",
                descripcion="Orden en proceso de reparación",
                posicion=2,
                es_final=False,
            ),
            EstadoOrden(
                codigo="TERMINADA",
                descripcion="Orden reparada y finalizada",
                posicion=3,
                es_final=True,
            ),
            EstadoOrden(
                codigo="CANCELADA",
                descripcion="Orden cancelada",
                posicion=4,
                es_final=True,
            ),
        ]
        session.add_all(estados)
        await session.flush()

        # 3. Usuarios
        print("Seeding usuarios...")
        u_admin = Usuario(
            email="admin@example.com",
            nombre="Admin Uno",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=False,
            password_cambiada_en=now,
        )
        u_admin2 = Usuario(
            email="admin2@example.com",
            nombre="Admin Dos",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=False,
            password_cambiada_en=now,
        )
        u_recepcion = Usuario(
            email="recepcion@example.com",
            nombre="Recepción Taller",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=False,
            password_cambiada_en=now,
        )
        u_mecanico = Usuario(
            email="mecanico@example.com",
            nombre="Mecánico Uno",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=False,
            password_cambiada_en=now,
        )
        u_mecanico2 = Usuario(
            email="mecanico2@example.com",
            nombre="Mecánico Dos",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=False,
            password_cambiada_en=now,
        )
        u_cliente = Usuario(
            email="cliente@example.com",
            nombre="Laura Cliente",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=False,
            password_cambiada_en=now,
        )
        u_nuevo = Usuario(
            email="nuevo@example.com",
            nombre="Mecánico Nuevo",
            password_hash=hashed_pw,
            activo=True,
            debe_cambiar_password=True,  # Cambio obligatorio pendiente
            password_cambiada_en=now,
        )
        session.add_all([u_admin, u_admin2, u_recepcion, u_mecanico, u_mecanico2, u_cliente, u_nuevo])
        await session.flush()

        # 4. Asignaciones de rol
        print("Seeding asignacion_rol...")
        roles = [
            AsignacionRol(usuario_id=u_admin.id, rol="ADMIN", desde=now),
            AsignacionRol(usuario_id=u_admin2.id, rol="ADMIN", desde=now),
            AsignacionRol(usuario_id=u_recepcion.id, rol="RECEPCION", desde=now),
            AsignacionRol(usuario_id=u_mecanico.id, rol="MECANICO", desde=now),
            AsignacionRol(usuario_id=u_mecanico2.id, rol="MECANICO", desde=now),
            AsignacionRol(usuario_id=u_cliente.id, rol="CLIENTE", desde=now),
            AsignacionRol(usuario_id=u_nuevo.id, rol="MECANICO", desde=now),
        ]
        session.add_all(roles)
        await session.flush()

        # 5. Clientes y Vehículos
        print("Seeding clientes y vehiculos...")
        c_laura = Cliente(
            usuario_id=u_cliente.id,
            nombre="Laura Cliente",
            documento="30111222",
            telefono="1144556677",
        )
        c_jorge = Cliente(
            usuario_id=None,
            nombre="Jorge Gomez",
            documento="20333444",
            telefono="1188990011",
        )
        session.add_all([c_laura, c_jorge])
        await session.flush()

        v_laura1 = Vehiculo(
            cliente_id=c_laura.id,
            patente="AC456EF",
            marca="Fiat",
            modelo="Cronos",
            anio=2021,
            borrado_en=None,
        )
        v_laura2 = Vehiculo(
            cliente_id=c_laura.id,
            patente="AA123BB",
            marca="Volkswagen",
            modelo="Gol",
            anio=2018,
            borrado_en=None,
        )
        v_jorge = Vehiculo(
            cliente_id=c_jorge.id,
            patente="AF789GH",
            marca="Ford",
            modelo="Focus",
            anio=2019,
            borrado_en=None,
        )
        session.add_all([v_laura1, v_laura2, v_jorge])
        await session.flush()

        # 6. Repuestos y movimientos de stock inicial
        print("Seeding repuestos y movimientos de stock inicial...")
        rep_filtro = Repuesto(
            codigo="FIL-001",
            descripcion="Filtro de aceite",
            precio=Decimal("8500.00"),
            stock=10,
        )
        rep_pastillas = Repuesto(
            codigo="FRE-010",
            descripcion="Pastillas de freno delanteras",
            precio=Decimal("32000.00"),
            stock=4,
        )
        rep_bujia = Repuesto(
            codigo="BUJ-001",
            descripcion="Bujía de encendido",
            precio=Decimal("5000.00"),
            stock=2,
        )
        rep_aceite = Repuesto(
            codigo="ACE-530",
            descripcion="Aceite 5W30 por litro",
            precio=Decimal("12000.00"),
            stock=20,
        )
        session.add_all([rep_filtro, rep_pastillas, rep_bujia, rep_aceite])
        await session.flush()

        # Movimientos de stock inicial
        movs = [
            MovimientoStock(
                repuesto_id=rep_filtro.id,
                orden_id=None,
                usuario_id=u_admin.id,
                cantidad=10,
                motivo="Stock inicial",
                cuando=now,
            ),
            MovimientoStock(
                repuesto_id=rep_pastillas.id,
                orden_id=None,
                usuario_id=u_admin.id,
                cantidad=4,
                motivo="Stock inicial",
                cuando=now,
            ),
            MovimientoStock(
                repuesto_id=rep_bujia.id,
                orden_id=None,
                usuario_id=u_admin.id,
                cantidad=2,
                motivo="Stock inicial",
                cuando=now,
            ),
            MovimientoStock(
                repuesto_id=rep_aceite.id,
                orden_id=None,
                usuario_id=u_admin.id,
                cantidad=20,
                motivo="Stock inicial",
                cuando=now,
            ),
        ]
        session.add_all(movs)
        await session.flush()

        # 7. Historial de precio
        print("Seeding historial_precio_repuesto...")
        hist_precio = HistorialPrecio(
            repuesto_id=rep_filtro.id,
            usuario_id=u_admin.id,
            precio_anterior=Decimal("8000.00"),
            precio_nuevo=Decimal("8500.00"),
            cuando=now,
        )
        session.add(hist_precio)
        await session.flush()

        # 8. Órdenes de trabajo
        print("Seeding ordenes de trabajo...")
        # Orden 1: PENDIENTE, del primer vehículo de Laura
        orden1 = OrdenTrabajo(
            vehiculo_id=v_laura1.id,
            mecanico_id=None,
            estado="PENDIENTE",
            falla="Ruido en tren delantero",
            creada_en=now,
            total=Decimal("32000.00"),
        )
        session.add(orden1)
        await session.flush()

        item_orden1 = ItemOrden(
            orden_id=orden1.id,
            repuesto_id=rep_pastillas.id,
            cantidad=1,
            precio_unitario=Decimal("32000.00"),
        )
        session.add(item_orden1)

        hist1 = HistorialEstadoOrden(
            orden_id=orden1.id,
            desde_estado=None,
            hasta_estado="PENDIENTE",
            usuario_id=u_recepcion.id,
            cuando=now,
        )
        session.add(hist1)
        await session.flush()

        # Orden 2: EN_REPARACION, del vehículo de Jorge, asignada a mecanico@example.com, con 4 bujías cuando hay 2
        orden2 = OrdenTrabajo(
            vehiculo_id=v_jorge.id,
            mecanico_id=u_mecanico.id,
            estado="EN_REPARACION",
            falla="Falla de encendido en cilindro 3",
            creada_en=now,
            total=Decimal("20000.00"),
        )
        session.add(orden2)
        await session.flush()

        item_orden2 = ItemOrden(
            orden_id=orden2.id,
            repuesto_id=rep_bujia.id,
            cantidad=4,  # Requiere 4 bujías pero stock es 2
            precio_unitario=Decimal("5000.00"),
        )
        session.add(item_orden2)

        hist2_1 = HistorialEstadoOrden(
            orden_id=orden2.id,
            desde_estado=None,
            hasta_estado="PENDIENTE",
            usuario_id=u_recepcion.id,
            cuando=now,
        )
        hist2_2 = HistorialEstadoOrden(
            orden_id=orden2.id,
            desde_estado="PENDIENTE",
            hasta_estado="EN_REPARACION",
            usuario_id=u_mecanico.id,
            cuando=now,
        )
        session.add_all([hist2_1, hist2_2])
        await session.flush()

        # 9. Historial de seguridad
        print("Seeding evento_seguridad...")
        ev = EventoSeguridad(
            actor="SISTEMA",
            accion="Carga de los datos iniciales",
            cuando=now,
        )
        session.add(ev)
        await session.flush()

        await session.commit()
        print("Seed completado exitosamente.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
