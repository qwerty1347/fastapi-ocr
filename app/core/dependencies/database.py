from app.infrastructure.database.session import async_session_factory


async def get_database():
    async with async_session_factory() as session:
        yield session