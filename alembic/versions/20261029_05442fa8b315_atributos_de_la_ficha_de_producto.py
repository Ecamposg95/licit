"""atributos de la ficha de producto

products.attributes: atributos citados de la ficha ({clave: {value, unit, source_text}}). El valor por omisión
"{}" se conserva en el servidor para que las filas existentes y los insert antiguos sigan válidos.

Revision ID: 05442fa8b315
Revises: ab9f8b99ecc6
Create Date: 2026-10-29 10:11:38.616183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05442fa8b315'
down_revision: Union[str, None] = 'ab9f8b99ecc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attributes', sa.JSON(), server_default='{}', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('attributes')
