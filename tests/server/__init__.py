from typing import AsyncContextManager, Callable

from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncContextManager[AsyncSession]]
