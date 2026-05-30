"""Add multi-tenancy support via Organization model and organization_id

Revision ID: d36ff9f8d7a9
Revises: bfe7c9524fb5
Create Date: 2026-05-15 01:42:39.429646

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd36ff9f8d7a9'
down_revision = 'bfe7c9524fb5'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create organizations table
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('primary_color', sa.String(length=7), nullable=True),
        sa.Column('logo_url', sa.String(length=512), nullable=True),
        sa.Column('custom_domain', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('custom_domain'),
        sa.UniqueConstraint('slug')
    )

    # 2. Insert default organization
    op.execute("INSERT INTO organizations (id, name, slug, created_at, updated_at) VALUES (1, '3EK LMS', '3ek-lms', now(), now())")

    # 3. Tables to migrate
    tables = [
        'certificates', 'learners', 'otp_tokens', 'shadow_clients', 
        'shadow_contacts', 'shadow_staff_users', 'shadow_trainers', 
        'workshop_email_logs', 'workshop_registrations', 'workshops'
    ]

    for table in tables:
        # Add column as nullable
        op.add_column(table, sa.Column('organization_id', sa.Integer(), nullable=True))
        
        # Update existing rows
        op.execute(f"UPDATE {table} SET organization_id = 1")
        
        # Set to NOT NULL
        op.alter_column(table, 'organization_id', nullable=False)
        
        # Create index and FK
        op.create_index(op.f(f'ix_{table}_organization_id'), table, ['organization_id'], unique=False)
        op.create_foreign_key(f'fk_{table}_organization_id', table, 'organizations', ['organization_id'], ['id'])

    # 4. Handle other changes detected by autogenerate
    with op.batch_alter_table('certificates', schema=None) as batch_op:
        # Fix the missing FK to assessment_assignments if it was indeed missing
        try:
            batch_op.create_foreign_key('fk_certificates_assessment_assignment', 'assessment_assignments', ['assessment_assignment_id'], ['id'])
        except Exception:
            pass


def downgrade():
    tables = [
        'certificates', 'learners', 'otp_tokens', 'shadow_clients', 
        'shadow_contacts', 'shadow_staff_users', 'shadow_trainers', 
        'workshop_email_logs', 'workshop_registrations', 'workshops'
    ]

    for table in tables:
        op.drop_constraint(f'fk_{table}_organization_id', table, type_='foreignkey')
        op.drop_index(op.f(f'ix_{table}_organization_id'), table_name=table)
        op.drop_column(table, 'organization_id')

    op.drop_table('organizations')
