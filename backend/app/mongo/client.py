from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

_client = AsyncIOMotorClient(settings.mongo_url)
mongo_db = _client[settings.mongo_db]
