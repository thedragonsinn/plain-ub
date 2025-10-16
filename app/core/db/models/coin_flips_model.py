from tortoise import fields
from tortoise.models import Model


class CoinFlips(Model):
    """
    Tortoise ORM Model for Coin Flips
    """

    id = fields.IntField(pk=True)
    user_id = fields.BigIntField()
    choice = fields.CharField(max_length=5)

    class Meta:
        table = "coin_flips"