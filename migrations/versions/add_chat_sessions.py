"""add chat sessions

Revision ID: add_chat_sessions
Revises: initial
Create Date: 2023-03-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'add_chat_sessions'
down_revision = 'initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('interview_id', UUID(as_uuid=True), sa.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False, server_default='New Chat'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create index on interview_id for faster lookups
    op.create_index('ix_chat_sessions_interview_id', 'chat_sessions', ['interview_id'])
    
    # Add chat_session_id to chat_messages table
    op.add_column(
        'chat_messages',
        sa.Column('chat_session_id', UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=True)
    )
    
    # Create index on chat_session_id for faster lookups
    op.create_index('ix_chat_messages_chat_session_id', 'chat_messages', ['chat_session_id'])


def downgrade() -> None:
    # Remove the chat_session_id column from chat_messages
    op.drop_index('ix_chat_messages_chat_session_id', table_name='chat_messages')
    op.drop_column('chat_messages', 'chat_session_id')
    
    # Drop the chat_sessions table
    op.drop_index('ix_chat_sessions_interview_id', table_name='chat_sessions')
    op.drop_table('chat_sessions') 