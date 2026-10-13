"""Repository for DataSource model operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import DataSource
from app.repositories.base import BaseRepository


def _as_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class DataSourceRepository(BaseRepository[DataSource]):
    """Repository managing DataSource configurations and synchronization state."""

    def __init__(self, session: AsyncSession):
        super().__init__(DataSource, session)

    async def get_by_id_and_user(self, ds_id: UUID | str, user_id: UUID | str) -> DataSource | None:
        ds_uuid = _as_uuid(ds_id)
        user_uuid = _as_uuid(user_id)
        stmt = select(DataSource).where(
            DataSource.id == ds_uuid,
            DataSource.user_id == user_uuid,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(
        self,
        user_id: UUID | str,
        source_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DataSource], int]:
        user_uuid = _as_uuid(user_id)
        count_stmt = select(func.count(DataSource.id)).where(DataSource.user_id == user_uuid)
        if source_type:
            count_stmt = count_stmt.where(DataSource.source_type == source_type)

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = select(DataSource).where(DataSource.user_id == user_uuid)
        if source_type:
            stmt = stmt.where(DataSource.source_type == source_type)

        stmt = stmt.order_by(DataSource.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
