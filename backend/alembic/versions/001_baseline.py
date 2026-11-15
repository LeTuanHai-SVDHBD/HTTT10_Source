from pathlib import Path
from alembic import op
revision='001_baseline'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    root=Path(__file__).resolve().parents[2]/'db'
    for name in ['001_schema.sql','002_reference_seed.sql']:
        lines=[line for line in (root/name).read_text().splitlines() if not line.lstrip().startswith('--') and not line.startswith('CREATE DATABASE ') and not line.startswith('USE ')]
        for statement in '\n'.join(lines).split(';'):
            if statement.strip():op.get_bind().exec_driver_sql(statement)
def downgrade():raise RuntimeError('Baseline contains history; destructive downgrade is disabled')
