import dns.resolver
from motor.core import AgnosticClient, AgnosticCollection, AgnosticDatabase
from motor.motor_asyncio import AsyncIOMotorClient

from app import Config

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8"]


class DataBase:
    def __init__(self):
        self._client: AgnosticClient = AsyncIOMotorClient(Config.DB_URL)
        self.db: AgnosticDatabase = self._client["plain_ub"]
        self.FED_LIST: AgnosticCollection = self.db.FED_LIST
        self.SUDO: AgnosticCollection = self.db.SUDO
        self.SUDO_USERS: AgnosticCollection = self.db.SUDO_USERS
        self.SUDO_CMD_LIST: AgnosticCollection = self.db.SUDO_CMD_LIST

    def __getattr__(self, attr) -> AgnosticCollection:
        try:
            collection: AgnosticCollection = self.__dict__[attr]
            return collection
        except KeyError:
            self.__dict__[attr] = self.db[attr]
            collection: AgnosticCollection = self.__dict__[attr]
            return collection

    @staticmethod
    async def add_data(
        collection: AgnosticCollection, id: int | str, data: dict
    ) -> None:
        found = await collection.find_one({"_id": id})
        if not found:
            await collection.insert_one({"_id": id, **data})
        else:
            await collection.update_one({"_id": id}, {"$set": data})

    @staticmethod
    async def delete_data(collection: AgnosticCollection, id: int | str) -> bool | None:
        found = await collection.find_one({"_id": id})
        if found:
            await collection.delete_one({"_id": id})
            return True

    def close(self):
        self._client.close()


DB: DataBase = DataBase()
