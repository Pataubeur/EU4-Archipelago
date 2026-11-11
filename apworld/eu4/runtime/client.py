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
from .render import atomic_text, install_mod, mod_root
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

    def install(self, eu4_running: Callable[[], bool] | None = None) -> Path:
        self.validate_user_dir()
        manifest = self.read_manifest()
        lock = ProcessLock(Path(self.user_dir) / "eu4ap_client.lock")
        try:
            if manifest.schema == 1:
                return install_mod(manifest, Path(self.user_dir))
            if eu4_running is None:
                from .process import eu4_running
            if eu4_running():
                raise ValueError("Fermez EU4 avant d'installer le mod : ses définitions ne sont lues qu'au lancement.")
            # Reinstalling keeps every item already received in the inbox.
            path = self.state_path(manifest)
            items, deathlinks, state = [], 0, None
            if path.is_file():
                state = JsonState(path, manifest.token)
                items = state.items()
                deathlinks = int(state.get("deathlinks_in") or 0)
            root = install_mod(manifest, Path(self.user_dir), items, deathlinks)
            if state:
                state.mark_staged({row[0] for row in items})
            return root
        finally:
            lock.close()

    def check_installed(self, manifest: Manifest) -> None:
        installed = mod_root(Path(self.user_dir)) / "eu4ap_manifest.json"
        if not installed.is_file() or Manifest.read(installed) != manifest:
            raise ValueError("Le mod installé ne correspond pas à ce manifeste. Fermez EU4 et cliquez "
                             "sur « Installer le mod » avant de vous connecter.")


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
        manifest = profile.read_manifest()
        if manifest.seed == "OFFLINE-POC":
            raise ValueError("Utilisez le manifeste généré pour le serveur, pas OFFLINE-POC.")
        v2 = manifest.schema == 2
        save = Path(profile.save) if profile.save.strip() else None
        if not v2 and (save is None or not save.is_file()):
            raise ValueError("Sélectionnez une sauvegarde EU4 locale existante.")
        if v2:
            profile.check_installed(manifest)
            if manifest.save_mode == "ironman":
                save = None  # Ironman saves are binary: game.log is the only outbound channel.
            elif save is not None and not save.is_file():
                raise ValueError("La sauvegarde sélectionnée n'existe pas ; laissez le champ vide "
                                 "pour utiliser seulement le journal du jeu.")
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
            user_dir = Path(profile.user_dir)
            sync = Synchronizer(manifest, state, user_dir / "eu4ap_sync.txt",
                                log_path=user_dir / "logs" / "game.log" if v2 else None,
                                user_dir=user_dir if v2 else None)
            await sync.poll_async(save)  # Validate binding (schema 1) or read the log (schema 2).
            if self.stopping:
                return
            ctx = self.context = EU4Context(sync, profile.server.strip(), profile.name.strip(), self.password or None)
            ctx.server_task = asyncio.create_task(server_loop(ctx), name="EU4 server")
            log.info("Suivi de %s ; état persistant : %s", save or "game.log", path)
            previous = None
            while not ctx.exit_event.is_set():
                try:
                    await ctx.tick(save)
                except (OSError, ValueError) as exc:
                    if ctx.sync_error != str(exc):
                        log.error("Synchronisation suspendue : %s", exc)
                    ctx.sync_error = str(exc)
                status = ctx.status()
                if status != previous:
                    report(summary(manifest, sync, ctx) + (f"\n{ctx.sync_error}" if ctx.sync_error else ""))
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


def summary(manifest: Manifest, sync: Synchronizer, ctx) -> str:
    """French status line shown by the Launcher client."""
    connection = "Connecté" if ctx.validated and ctx.slot is not None else "En attente du serveur"
    counts = sync.counts()
    checks = f"Objectifs : {len(sync.state.checks())}/{len(manifest.locations)}"
    if manifest.schema == 1:
        return (f"{connection} · {manifest.country} · {checks}\n"
                f"Objets à appliquer : {counts['pending']} · Confirmés : {counts['confirmed']}")
    codes = sync.pending_codes()
    coded = {code for code, _name in codes}
    with_code = len(sync.codes().keys() & {r[0] for r in sync.state.items() if r[-1] in ("received", "pending")})
    waiting = counts["received"] + counts["pending"] - with_code
    applied = counts["applied"] + counts["confirmed"]
    detected = sync.state.get("detected_mode")
    mode = "Ironman" if manifest.save_mode == "ironman" else "normal"
    if waiting and manifest.save_mode == "ironman":
        hint = " — relancez EU4 pour les recevoir"
    elif waiting:
        hint = " — console : run eu4ap_sync.txt, ou relancez EU4"
    else:
        hint = ""
    shown = ", ".join(f"{code} {name}" for code, name in codes[:6]) + (" …" if len(codes) > 6 else "")
    entry = (f"\nÀ saisir en jeu (décision « réceptionner une livraison ») : {shown}" if coded else "")
    return (f"{connection} · {manifest.country} · mode {mode}"
            + (f" (jeu : {detected})" if detected else "") + f" · {checks}\n"
            f"Objets appliqués : {applied} · codes à saisir : {len(codes)} · sans code, au prochain "
            f"relancement : {waiting}{hint}{entry}")
