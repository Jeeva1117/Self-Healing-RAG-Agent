"""User database repository implementing persistence operations for User entity."""

from collections.abc import Sequence
from datetime import UTC, datetime

from app.infrastructure.database.models import User, UserRole
from app.repositories.base import BaseRepository
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository(BaseRepository[User]):
    """Repository handling database queries for User entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Fetches a user by normalized lowercase email address."""
        stmt = select(User).where(func.lower(User.email) == func.lower(email.strip()))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_user(
        self,
        email: str,
        name: str,
        password_hash: str,
        role: str = UserRole.USER.value,
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        """Instantiates and commits a new User record."""
        user = User(
            email=email.strip().lower(),
            name=name.strip(),
            password_hash=password_hash,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
        )
        return await self.create(user)

    async def update_last_login(self, user: User) -> None:
        """Updates user's last_login_at timestamp."""
        user.last_login_at = datetime.now(UTC)
        self.session.add(user)
        await self.session.flush()

    async def update_password(self, user: User, password_hash: str) -> None:
        """Updates user's password_hash."""
        user.password_hash = password_hash
        user.updated_at = datetime.now(UTC)
        self.session.add(user)
        await self.session.flush()

    async def count_users(self) -> int:
        """Returns total user count."""
        stmt = select(func.count(User.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_paginated(self, skip: int = 0, limit: int = 50) -> tuple[Sequence[User], int]:
        """Returns paginated user list and total count."""
        total = await self.count_users()
        stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        users = result.scalars().all()
        return users, total
