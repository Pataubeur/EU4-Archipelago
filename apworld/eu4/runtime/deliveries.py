"""Live deliveries for Ironman without relaunching EU4.

After fill, the generator knows every item this slot will receive and where it
comes from. Each one gets a random 4-digit code and is rendered into the mod
once, so the mod (and its checksum) never changes during the campaign. When an
item arrives, the client shows its code; the player enters it in game through a
digit-pad event chain and the mod applies the effect, then logs ``CLAIM <code>``.

The game cannot verify that an item was really received (honour system); the
client audits every CLAIM line against the received items. Items absent from the
list (server /send, late additions) still use the inbox at the next relaunch.
"""
from __future__ import annotations

import random
from dataclasses import replace

from .manifest import Manifest

CODE_MIN, CODE_MAX = 1000, 9999
DEATHLINK_CODES = 20
START_INVENTORY = -2  # AP start inventory and server-side items use negative locations.


def attach_deliveries(manifest: Manifest, rows, seed: int) -> Manifest:
    """rows: (item_id, sender_slot, location_id) for every item this slot receives.
    Returns the final manifest with (code, item, sender, location) deliveries."""
    rows = sorted(rows)
    count = len(rows) + (DEATHLINK_CODES if manifest.death_link else 0)
    if count > CODE_MAX - CODE_MIN + 1:
        raise ValueError("Too many deliveries for 4-digit codes")
    codes = random.Random(seed).sample(range(CODE_MIN, CODE_MAX + 1), count)
    deliveries = tuple(sorted((code, item, sender, location)
                              for code, (item, sender, location) in zip(codes, rows)))
    return replace(manifest, deliveries=deliveries, deathlink_codes=tuple(codes[len(rows):]))


def match_deliveries(manifest: Manifest, items) -> dict[int, int]:
    """Received item index -> delivery code. Positive locations match by
    (sender, location); negative ones (start inventory, server) by item ID in
    order. Unmatched items have no code and use the relaunch inbox."""
    by_location = {(sender, location): code for code, _item, sender, location in manifest.deliveries
                   if location >= 0}
    loose: dict[int, list[int]] = {}
    for code, item, _sender, location in manifest.deliveries:
        if location < 0:
            loose.setdefault(item, []).append(code)
    result = {}
    for row in items:
        index, item, location, sender = row[0], row[1], row[2], row[3]
        if location >= 0:
            code = by_location.get((sender, location))
            if code is not None and manifest.delivery_item(code) == item:
                result[index] = code
        elif loose.get(item):
            result[index] = loose[item].pop(0)
    return result


def deathlink_code(manifest: Manifest, index: int) -> int | None:
    return manifest.deathlink_codes[index] if index < len(manifest.deathlink_codes) else None
