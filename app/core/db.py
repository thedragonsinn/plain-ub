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
        self.SUDO_USERS: AgnosticCollection = self.db.USERS

    def __getattr__(self, attr) -> AgnosticCollection:
        try:
            return self.__dict__[attr]
        except KeyError:
            self.__dict__[attr] = self.db[attr]
            return self.__dict__[attr]


DB = DataBase()
