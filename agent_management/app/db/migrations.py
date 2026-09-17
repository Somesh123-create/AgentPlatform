from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def upgrade_agent_drafts(connection: AsyncConnection) -> None:
    """Add columns introduced after the initial agent_drafts table creation."""
    await connection.execute(text(
        """
        ALTER TABLE agent_drafts
        ADD COLUMN IF NOT EXISTS llm_model_id INTEGER,
        ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(80),
        ADD COLUMN IF NOT EXISTS llm_model_name VARCHAR(150),
        ADD COLUMN IF NOT EXISTS temperature DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS max_output_tokens INTEGER,
        ADD COLUMN IF NOT EXISTS project_directory VARCHAR(500) NOT NULL DEFAULT '',
        ADD COLUMN IF NOT EXISTS mcp_connections JSON NOT NULL DEFAULT '[]',
        ADD COLUMN IF NOT EXISTS project_revision INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS default_build_id INTEGER
        """
    ))
    statements = [
        """CREATE TABLE IF NOT EXISTS agent_conversations (id SERIAL PRIMARY KEY, agent_id INTEGER NOT NULL REFERENCES agent_drafts(id) ON DELETE CASCADE, owner_id INTEGER NOT NULL, title TEXT NOT NULL DEFAULT 'New conversation', created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW())""",
        "CREATE INDEX IF NOT EXISTS ix_agent_conversations_agent_id ON agent_conversations(agent_id)",
        "CREATE INDEX IF NOT EXISTS ix_agent_conversations_owner_id ON agent_conversations(owner_id)",
        """CREATE TABLE IF NOT EXISTS agent_messages (id SERIAL PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE, role VARCHAR(20) NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW())""",
        "CREATE INDEX IF NOT EXISTS ix_agent_messages_conversation_id ON agent_messages(conversation_id)",
    ]
    for statement in statements:
        await connection.execute(text(statement))