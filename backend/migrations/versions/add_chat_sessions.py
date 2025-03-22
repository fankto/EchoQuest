"""add chat sessions

Revision ID: c33f2e78d21a
Revises: 
Create Date: 2023-10-19 14:25:44.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'c33f2e78d21a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('interview_id', UUID(as_uuid=True), sa.ForeignKey('interviews.id'), nullable=False),
        sa.Column('title', sa.String(), nullable=False, server_default='New Chat'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, onupdate=sa.text('now()')),
    )
    
    # Add chat_session_id to chat_messages
    op.add_column(
        'chat_messages',
        sa.Column('chat_session_id', UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id'), nullable=True)
    )
    
    # Create index for faster lookups
    op.create_index('ix_chat_sessions_interview_id', 'chat_sessions', ['interview_id'])
    op.create_index('ix_chat_messages_chat_session_id', 'chat_messages', ['chat_session_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_chat_messages_chat_session_id')
    op.drop_index('ix_chat_sessions_interview_id')
    
    # Drop chat_session_id from chat_messages
    op.drop_column('chat_messages', 'chat_session_id')
    
    # Drop chat_sessions table
    op.drop_table('chat_sessions') 