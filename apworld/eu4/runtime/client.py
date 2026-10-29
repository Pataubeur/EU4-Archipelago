"""GUI-independent campaign settings and lifecycle for the launcher client."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .locking import ProcessLock
from .manifest import Manifest
from .json_state import JsonState
from .render import atomic_text, install_mod
from .synchronization import POLL_INTERVAL, Synchronizer

log = logging.getLogger("EU4")


def default_user_dir() -> Path:
    documents = Path.home() / "Documents"
    if os.name == "nt":
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            documents = Path(buffer.value)
    return documents / "Paradox Interactive" / "Europa Universalis IV"


def settings_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "EU4Archipelago" / "client.json"


@dataclass
class Profile:
    manifest: str = ""
    save: str = ""
    user_dir: str = ""
    server: str = ""
    name: str = "EU4Player"

    @classmethod
    def load(cls, path: Path) -> Profile:
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(values, dict):
                raise ValueError("Invalid settings")
            return cls(**{key: value for key, value in values.items()
                          if key in cls.__dataclass_fields__ and isinstance(value, str)})
        except (OSError, ValueError, TypeError):
            return cls(user_dir=str(default_user_dir()))

    def write(self, path: Path) -> None:
        # Passwords are never part of a profile.
        atomic_text(path, json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n")

    def read_manifest(self) -> Manifest:
        if not self.manifest.strip():
            raise ValueError("Sélectionnez le manifeste .apeu4.json de votre partie.")
        manifest = Manifest.read(Path(self.manifest))
        if manifest.seed == "OFFLINE-POC":
            raise ValueError("Le manifeste OFFLINE-POC est une démonstration. Demandez à l'hôte "
                             "le fichier .apeu4.json généré pour votre joueur.")
        return manifest

    def validate_user_dir(self) -> Path:
        path = Path(self.user_dir)
        if not self.user_dir.strip() or not path.is_dir() or not any(
                (path / marker).exists() for marker in ("settings.txt", "save games")):
            raise ValueError("Choisissez le dossier utilisateur Documents/Paradox Interactive/"
                             "Europa Universalis IV (pas le dossier Steam). Lancez EU4 une fois "
                             "pour créer ce dossier, puis sélectionnez-le avec Parcourir.")
        return path

    def state_path(self, manifest: Manifest) -> Path:
        # Stable across save renames and client restarts; separate for every slot/seed.
        return Path(self.user_dir) / "eu4ap" / manifest.token / "campaign.json"

    def install(self) -> Path:
        self.validate_user_dir()
        manifest = self.read_manifest()
        lock = ProcessLock(Path(self.user_dir) / "eu4ap_client.lock")
        try:
            return install_mod(manifest, Path(self.user_dir))
        finally:
            lock.close()


class Session:
    """Owns the AP connection, save watcher, database and single-writer lock."""
    def __init__(self, profile: Profile, password: str = "") -> None:
        self.profile = profile
        self.password = password
        self.context = None
        self.stopping = False

    def stop(self) -> None:
        self.stopping = True
        if self.context:
            self.context.exit_event.set()

    async def run(self, report: Callable[[str], None]) -> None:
        from CommonClient import server_loop
        from .connection import EU4Context

        profile = self.profile
        if not profile.server.strip() or not profile.name.strip():
            raise ValueError("Renseignez le serveur et le nom du joueur Archipelago.")
        profile.validate_user_dir()
        if not profile.save.strip() or not Path(profile.save).is_file():
            raise ValueError("Sélectionnez une sauvegarde EU4 locale existante.")
        manifest = profile.read_manifest()
        if manifest.seed == "OFFLINE-POC":
            raise ValueError("Utilisez le manifeste généré pour le serveur, pas OFFLINE-POC.")
        lock = ProcessLock(Path(profile.user_dir) / "eu4ap_client.lock")
        state = None
        handler = None
        try:
            path = profile.state_path(manifest)
            path.parent.mkdir(parents=True, exist_ok=True)
            state = JsonState(path, manifest.token)
            handler = logging.FileHandler(path.with_suffix(".log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            log.addHandler(handler)
            sync = Synchronizer(manifest, state, Path(profile.user_dir) / "eu4ap_sync.txt")
            await sync.poll_async(Path(profile.save))  # Validate binding before connecting.
            if self.stopping:
                return
            ctx = self.context = EU4Context(sync, profile.server.strip(), profile.name.strip(), self.password or None)
            ctx.server_task = asyncio.create_task(server_loop(ctx), name="EU4 server")
            log.info("Suivi de %s ; état persistant : %s", profile.save, path)
            previous = None
            while not ctx.exit_event.is_set():
                try:
                    await ctx.tick(Path(profile.save))
                except (OSError, ValueError) as exc:
                    if ctx.sync_error != str(exc):
                        log.error("Synchronisation suspendue : %s", exc)
                    ctx.sync_error = str(exc)
                status = ctx.status()
                if status != previous:
                    rows = state.items()
                    pending = sum(row[-1] == "pending" for row in rows)
                    confirmed = sum(row[-1] == "confirmed" for row in rows)
                    connection = "Connecté" if ctx.validated and ctx.slot is not None else "En attente du serveur"
                    report(f"{connection} · {manifest.country} · Objectifs : {len(state.checks())}/{len(manifest.locations)}\n"
                           f"Objets à appliquer : {pending} · Confirmés : {confirmed}"
                           + (f"\n{ctx.sync_error}" if ctx.sync_error else ""))
                    previous = status
                try:
                    await asyncio.wait_for(ctx.exit_event.wait(), timeout=POLL_INTERVAL)
                except asyncio.TimeoutError:
                    pass
            if ctx.blocked:
                raise ValueError(ctx.sync_error)
        finally:
            try:
                if self.context:
                    self.context.exit_event.set()
                    try:
                        await asyncio.wait_for(self.context.shutdown(), timeout=10)
                    except asyncio.TimeoutError:
                        if self.context.server_task:
                            self.context.server_task.cancel()
                            await asyncio.gather(self.context.server_task, return_exceptions=True)
            finally:
                self.context = None
                if handler:
                    log.removeHandler(handler)
                    handler.close()
                try:
                    if state:
                        state.close()
                finally:
                    lock.close()

    def command(self, text: str) -> None:
        if not self.context:
            raise ValueError("Connectez le client avant d'envoyer un message.")
        ctx = self.context
        if ctx.input_requests:
            ctx.input_requests -= 1
            ctx.input_queue.put_nowait(text)
        else:
            ctx.command_processor(ctx)(text)
