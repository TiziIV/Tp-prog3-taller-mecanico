"""triggers_solo_agregado

Revision ID: c0f6fad6c65c
Revises: 7895ba1d1251
Create Date: 2026-10-26 17:07:08.668959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Esta migración fue escrita a mano y revisada minuciosamente antes de aplicarse (RN-15).

# revision identifiers, used by Alembic.
revision: str = 'c0f6fad6c65c'
down_revision: Union[str, Sequence[str], None] = '7895ba1d1251'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Instala la función y disparadores de sólo agregado (RN-15)."""
    op.execute("""
        CREATE OR REPLACE FUNCTION rechazar_modificacion_o_borrado_solo_agregado()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Operación no permitida: la tabla % es de sólo agregado (append-only)', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_solo_agregado_historial_estado_orden
        BEFORE UPDATE OR DELETE ON historial_estado_orden
        FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion_o_borrado_solo_agregado();
    """)

    op.execute("""
        CREATE TRIGGER trg_solo_agregado_movimiento_stock
        BEFORE UPDATE OR DELETE ON movimiento_stock
        FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion_o_borrado_solo_agregado();
    """)

    op.execute("""
        CREATE TRIGGER trg_solo_agregado_historial_precio_repuesto
        BEFORE UPDATE OR DELETE ON historial_precio_repuesto
        FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion_o_borrado_solo_agregado();
    """)


def downgrade() -> None:
    """Downgrade schema: Elimina los disparadores y la función de sólo agregado."""
    op.execute("DROP TRIGGER IF EXISTS trg_solo_agregado_historial_precio_repuesto ON historial_precio_repuesto;")
    op.execute("DROP TRIGGER IF EXISTS trg_solo_agregado_movimiento_stock ON movimiento_stock;")
    op.execute("DROP TRIGGER IF EXISTS trg_solo_agregado_historial_estado_orden ON historial_estado_orden;")
    op.execute("DROP FUNCTION IF EXISTS rechazar_modificacion_o_borrado_solo_agregado();")
