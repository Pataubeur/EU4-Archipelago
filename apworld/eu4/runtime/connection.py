"""AP transport adapter. Import only inside an installed Archipelago runtime."""
from __future__ import annotations

import asyncio
import logging

from CommonClient import ClientCommandProcessor, CommonContext

from .catalog import ITEM_DEF_BY_ID
from .data import GAME
from .manifest import Manifest
from .persistence import ItemGapError
from .render import atomic_text
from .synchronization import Synchronizer

log = logging.getLogger("EU4")


class EU4Commands(ClientCommandProcessor):
    def _cmd_status(self) -> bool:
        """Show connection, seed, country, item states and latest synchronization error."""
        self.output(self.ctx.status())
        return True


class EU4Context(CommonContext):
    game = GAME
    items_handling = 0b111
    command_processor = EU4Commands

    def __init__(self, sync: Synchronizer, server: str, name: str, password: str | None = None) -> None:
        super().__init__(server, password)
        self.sync = sync
        self.seed_name = sync.manifest.seed
        self.username = self.auth = name
        self.validated = False
        self.blocked = False
        self.stream_ready = True
        self.sync_error = ""
        self.last_check = "none"
        self.last_item = "none"
        self._last_messages = None
        self._last_send = 0.0

    async def server_auth(self, password_requested: bool = False) -> None:
        await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    async def connection_closed(self) -> None:
        self.validated = False
        self._last_messages = None
        await super().connection_closed()

    def fail(self, message: str) -> None:
        self.blocked = True
        self.validated = False
        self.sync_error = message
        atomic_text(self.sync.output, "# Export blocked: incompatible AP connection or item stream.\n")
        log.error("protocol_error: %s", message)
        self.exit_event.set()

    def on_package(self, cmd: str, args: dict) -> None:
        try:
            if cmd == "RoomInfo" and args["seed_name"] != self.sync.manifest.seed:
                raise ValueError("AP server seed does not match the manifest")
            if cmd == "Connected":
                self.validated = False
                m = self.sync.manifest
                if (Manifest.from_dict(args["slot_data"]["manifest"]) != m
                        or args["slot"] != m.slot or args["team"] != m.team):
                    raise ValueError("Server slot data / slot / team differs from the manifest")
                server_locations = set(args["missing_locations"]) | set(args["checked_locations"])
                if server_locations != set(m.locations):
                    raise ValueError("Server location set differs from the generated mod")
                self.validated = True
                self._last_messages = None
                log.info("connected: seed=%s slot=%s country=%s", m.seed, m.slot, m.country)
                if m.death_link and hasattr(self, "update_death_link"):
                    asyncio.create_task(self.update_death_link(True), name="EU4 DeathLink")
            elif cmd == "ReceivedItems":
                if not self.validated or self.blocked:
                    raise ValueError("ReceivedItems before slot validation")
                values = [tuple(v) for v in args["items"]]
                if any(len(v) != 4 or v[0] not in ITEM_DEF_BY_ID for v in values):
                    raise ValueError("Unknown or malformed EU4 item")
                known = len(self.sync.state.items())
                self.sync.state.receive(args["index"], values)
                self.stream_ready = True
                if self.sync.v2:
                    codes = self.sync.codes()
                    for index in range(max(known, args["index"]), args["index"] + len(values)):
                        item, _location, sender, _flags = values[index - args["index"]]
                        name = ITEM_DEF_BY_ID[item].name
                        source = getattr(self, "player_names", {}).get(sender, f"joueur {sender}")
                        if index in codes:
                            log.info("Livraison reçue de %s : %s — code %s (décision « réceptionner une "
                                     "livraison »)", source, name, codes[index])
                        else:
                            log.info("Objet reçu de %s : %s — appliqué au prochain lancement d'EU4", source, name)
                if values:
                    self.last_item = ITEM_DEF_BY_ID[values[-1][0]].name
                    log.info("items_received: index=%s count=%s last=%s", args["index"], len(values), self.last_item)
        except ItemGapError as exc:
            self.stream_ready = False
            self.sync_error = str(exc)
            atomic_text(self.sync.output, "# Item stream gap: awaiting server replay.\n")
            log.warning("item_stream_gap: %s", exc)
        except (KeyError, TypeError, ValueError) as exc:
            self.fail(str(exc))

    def on_deathlink(self, data: dict) -> None:
        parent = getattr(super(), "on_deathlink", None)
        if parent:
            parent(data)
        if self.sync.manifest.death_link:
            self.sync.receive_deathlink()
            log.info("deathlink_received: source=%s", data.get("source", "?"))

    async def tick(self, save_path) -> None:
        if self.blocked or not self.stream_ready:
            return
        if not await self.sync.poll_async(save_path, lambda: not self.blocked and self.stream_ready):
            return
        self.sync_error = self.sync.status_warning()
        for year in self.sync.take_deaths():
            if self.sync.manifest.death_link and hasattr(self, "send_death"):
                await self.send_death(f"Le souverain de {self.username} est mort ({year}).")
                log.info("deathlink_sent: year=%s", year)
        if self.validated and self.slot is not None:
            messages = self.sync.messages(set(self.checked_locations))
            now = asyncio.get_running_loop().time()
            # Retry unacknowledged checks, but avoid flooding a disconnected server.
            if messages and (messages != self._last_messages or now - self._last_send >= 10):
                await self.send_msgs(messages)
                for message in messages:
                    if message["cmd"] == "LocationChecks":
                        self.last_check = str(message["locations"][-1])
                        log.info("checks_sent: locations=%s", message["locations"])
                self._last_messages, self._last_send = messages, now

    def status(self) -> str:
        m = self.sync.manifest
        counts = self.sync.counts()
        return (f"connected={self.validated and self.slot is not None} slot={m.slot} "
                f"schema={m.schema} mode={m.save_mode} "
                f"seed={m.seed} country={m.country} checks={len(self.sync.state.checks())}/{len(m.locations)} "
                f"items={counts} last_check={self.last_check} last_item={self.last_item} "
                f"sync_error={self.sync_error or 'none'}")
