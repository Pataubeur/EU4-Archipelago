from BaseClasses import Item, ItemClassification

from .runtime.data import GAME, ITEMS


class EU4Item(Item):
    game = GAME


def create_item(name: str, player: int) -> EU4Item:
    code, _effect, _amount, classification = ITEMS[name]
    return EU4Item(name, getattr(ItemClassification, classification), code, player)
