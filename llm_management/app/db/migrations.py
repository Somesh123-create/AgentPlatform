from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def upgrade_model_access(connection: AsyncConnection) -> None:
    await connection.execute(text(
        """
        ALTER TABLE llm_model_access
        ADD COLUMN IF NOT EXISTS last_test_status VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
        ADD COLUMN IF NOT EXISTS last_tested_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS last_test_error VARCHAR(500)
        """
    ))