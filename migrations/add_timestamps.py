"""Add timestamps to Pedal model

Revision ID: add_timestamps
Revises: None
Create Date: 2024-12-26 13:47

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_timestamps'
down_revision = None

def upgrade():
    # Add created_at and updated_at columns
    op.add_column('pedal', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('pedal', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Set default values for existing rows
    op.execute("UPDATE pedal SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP")

def downgrade():
    # Remove the columns
    op.drop_column('pedal', 'updated_at')
    op.drop_column('pedal', 'created_at')
