from BaseClasses import Item, ItemClassification

from .runtime.catalog import ITEM_DEFS
from .runtime.data import GAME


class EU4Item(Item):
    game = GAME


def create_item(name: str, player: int) -> EU4Item:
    item = ITEM_DEFS[name]
    return EU4Item(name, getattr(ItemClassification, item.classification), item.id, player)
