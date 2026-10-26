import asyncio
from decimal import Decimal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import event
from app.core.config import settings
from app.core.database import create_engine, create_session_factory
from app.modules.ordenes.models import ItemOrden, OrdenTrabajo
from app.modules.ordenes.repository import OrdenTrabajoRepository
from seed import seed


async def test_c15():
    await seed()

    engine = create_engine()
    session_factory = create_session_factory(engine)

    # Crear una orden con 2 ítems y otra con 4 ítems
    async with session_factory() as session:
        datetime_now = datetime_now_helper()
        # Orden con 2 items (id=101)
        o1 = OrdenTrabajo(
            vehiculo_id=1,
            mecanico_id=4,
            estado="PENDIENTE",
            falla="Orden con 2 items",
            creada_en=datetime_now,
            total=Decimal("40500.00"),
        )
        session.add(o1)
        await session.flush()

        session.add_all([
            ItemOrden(orden_id=o1.id, repuesto_id=1, cantidad=1, precio_unitario=Decimal("8500.00")),
            ItemOrden(orden_id=o1.id, repuesto_id=2, cantidad=1, precio_unitario=Decimal("32000.00")),
        ])

        # Orden con 4 items (id=102)
        o2 = OrdenTrabajo(
            vehiculo_id=1,
            mecanico_id=4,
            estado="PENDIENTE",
            falla="Orden con 4 items",
            creada_en=datetime_now,
            total=Decimal("69500.00"),
        )
        session.add(o2)
        await session.flush()

        session.add_all([
            ItemOrden(orden_id=o2.id, repuesto_id=1, cantidad=1, precio_unitario=Decimal("8500.00")),
            ItemOrden(orden_id=o2.id, repuesto_id=2, cantidad=1, precio_unitario=Decimal("32000.00")),
            ItemOrden(orden_id=o2.id, repuesto_id=3, cantidad=1, precio_unitario=Decimal("5000.00")),
            ItemOrden(orden_id=o2.id, repuesto_id=4, cantidad=2, precio_unitario=Decimal("12000.00")),
        ])
        await session.commit()
        id_orden_2 = o1.id
        id_orden_4 = o2.id

    # Listener para contar consultas
    queries_log = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        queries_log.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)

    # 1. Medir consultas para orden con 2 ítems
    queries_log.clear()
    async with session_factory() as session:
        repo = OrdenTrabajoRepository(session)
        det_2 = await repo.get_detalle_by_id(id_orden_2)
        # Acceder a propiedades para verificar que no hay lazy loading diferido
        _ = det_2.vehiculo.patente
        _ = det_2.vehiculo.cliente.nombre
        _ = [(it.repuesto.codigo, it.subtotal if hasattr(it, 'subtotal') else it.cantidad) for it in det_2.items]
        _ = [h.hasta_estado for h in det_2.historial]

    count_2_items = len(queries_log)
    queries_2 = list(queries_log)

    # 2. Medir consultas para orden con 4 ítems
    queries_log.clear()
    async with session_factory() as session:
        repo = OrdenTrabajoRepository(session)
        det_4 = await repo.get_detalle_by_id(id_orden_4)
        _ = det_4.vehiculo.patente
        _ = det_4.vehiculo.cliente.nombre
        _ = [(it.repuesto.codigo, it.subtotal if hasattr(it, 'subtotal') else it.cantidad) for it in det_4.items]
        _ = [h.hasta_estado for h in det_4.historial]

    count_4_items = len(queries_log)
    queries_4 = list(queries_log)

    print("\n" + "=" * 60)
    print(f"CONSULTAS EJECUTADAS PARA ORDEN CON 2 ITEMS: {count_2_items}")
    for i, q in enumerate(queries_2, 1):
        print(f"[{i}] {q.strip().splitlines()[0]}...")

    print("\n" + "=" * 60)
    print(f"CONSULTAS EJECUTADAS PARA ORDEN CON 4 ITEMS: {count_4_items}")
    for i, q in enumerate(queries_4, 1):
        print(f"[{i}] {q.strip().splitlines()[0]}...")
    print("=" * 60)

    assert count_2_items == count_4_items, f"Error N+1 detectado: {count_2_items} != {count_4_items}"
    print(f"\n¡VERIFICACIÓN EXITOSA! Ambas órdenes ejecutaron exactamente {count_2_items} consultas SQL (N+1 evitado).")
    await engine.dispose()


def datetime_now_helper():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


if __name__ == "__main__":
    asyncio.run(test_c15())
