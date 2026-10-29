"""EU4 launcher UI; all GUI imports are delayed until the client is opened."""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
import logging
from pathlib import Path
import queue

from .client import Profile, Session, default_user_dir, settings_path
from .version import VERSION


def launch(*argv: str) -> None:
    parser = argparse.ArgumentParser(description="EU4 Archipelago Client")
    parser.add_argument("manifest", nargs="?", help="Manifeste de la partie .apeu4.json")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    # Required before any Kivy imports in frozen Archipelago builds.
    import kvui  # noqa: F401
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.clipboard import Clipboard
    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.filechooser import FileChooserListView
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.textinput import TextInput

    class LogHandler(logging.Handler):
        def __init__(self):
            super().__init__(logging.INFO)
            self.messages = queue.SimpleQueue()
            self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))

        def emit(self, record):
            self.messages.put(self.format(record))

    class EU4App(App):
        title = f"Europa Universalis IV — Archipelago {VERSION}"

        def build(self):
            Window.size = (1060, 820)
            Window.clearcolor = (0.055, 0.065, 0.09, 1)
            self.profile_path = args.profile or settings_path()
            profile = Profile.load(self.profile_path)
            if args.manifest:
                profile.manifest = args.manifest
            if not profile.user_dir:
                profile.user_dir = str(default_user_dir())
            self.session = None
            self.session_task = None
            self.fields = {}
            self.edit_controls = []
            self.lines = deque(maxlen=300)
            root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
            root.add_widget(Label(text="EUROPA UNIVERSALIS IV  ·  ARCHIPELAGO",
                                  font_size=dp(23), size_hint_y=None, height=dp(38)))
            root.add_widget(Label(text="Choisissez votre campagne, puis connectez-vous au multiworld.",
                                  size_hint_y=None, height=dp(25), color=(0.72, 0.77, 0.85, 1)))

            for key, label, filters in (
                ("manifest", "Manifeste de la partie", ["*.apeu4.json"]),
                ("user_dir", "Dossier utilisateur EU4", None),
                ("save", "Sauvegarde EU4", ["*.eu4"]),
                ("server", "Serveur (adresse:port)", False),
                ("name", "Nom du joueur AP", False),
                ("password", "Mot de passe (facultatif)", False),
            ):
                row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
                row.add_widget(Label(text=label, size_hint_x=None, width=dp(215), font_size=dp(14)))
                field = TextInput(text=getattr(profile, key, ""), multiline=False,
                                  password=key == "password", font_size=dp(14),
                                  background_color=(0.12, 0.14, 0.19, 1), foreground_color=(0.95, 0.96, 1, 1))
                self.fields[key] = field
                self.edit_controls.append(field)
                row.add_widget(field)
                if filters is not False:
                    button = Button(text="Parcourir…", size_hint_x=None, width=dp(115))
                    button.bind(on_release=lambda _, k=key, f=filters: self.browse(k, f))
                    self.edit_controls.append(button)
                    row.add_widget(button)
                root.add_widget(row)

            self.summary = Label(text="Prêt. Le manifeste doit correspondre à la partie hébergée.",
                                 size_hint_y=None, height=dp(60), font_size=dp(14))
            root.add_widget(self.summary)
            actions = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
            self.install_button = Button(text="Installer le mod (EU4 fermé)")
            self.install_button.bind(on_release=self.install)
            self.edit_controls.append(self.install_button)
            actions.add_widget(self.install_button)
            self.connect_button = Button(text="Se connecter", background_color=(0.55, 0.3, 0.85, 1))
            self.connect_button.bind(on_release=self.toggle_connection)
            actions.add_widget(self.connect_button)
            root.add_widget(actions)
            hint = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            hint.add_widget(Label(text="Objets reçus : dans la console EU4, exécutez\nrun eu4ap_sync.txt, puis sauvegardez.",
                                  font_size=dp(14)))
            copy_button = Button(text="Copier la commande EU4", size_hint_x=None, width=dp(235))
            copy_button.bind(on_release=lambda _: Clipboard.copy("run eu4ap_sync.txt"))
            hint.add_widget(copy_button)
            root.add_widget(hint)
            self.journal = TextInput(readonly=True, font_size=dp(13),
                                     background_color=(0.075, 0.085, 0.11, 1), foreground_color=(0.85, 0.9, 0.95, 1))
            root.add_widget(self.journal)
            message_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
            self.message = TextInput(multiline=False, hint_text="Message au multiworld ou commande /status")
            self.message.bind(on_text_validate=self.send_message)
            message_row.add_widget(self.message)
            send = Button(text="Envoyer", size_hint_x=None, width=dp(100))
            send.bind(on_release=self.send_message)
            message_row.add_widget(send)
            root.add_widget(message_row)
            self.log_handler = LogHandler()
            self.loggers = [logging.getLogger(name) for name in ("EU4", "Client")]
            self.old_levels = [logger.level for logger in self.loggers]
            for logger in self.loggers:
                logger.setLevel(logging.INFO)
                logger.addHandler(self.log_handler)
            self.log_timer = Clock.schedule_interval(self.drain_logs, 0.2)
            return root

        def on_start(self):
            if args.smoke_test:
                # Opt-in validation of the actual frozen launcher and Kivy UI.
                from .render import atomic_text
                atomic_text(args.smoke_test, "PASS: frozen EU4 client UI built\n")
                def capture(_):
                    import json
                    Window.screenshot(name=str(args.smoke_test.with_suffix(".png")))
                    geometry = [{"text": getattr(w, "text", ""), "size": list(w.size), "pos": list(w.pos)}
                                for w in self.root.walk()]
                    atomic_text(args.smoke_test.with_suffix(".json"), json.dumps(geometry))
                Clock.schedule_once(capture, 2)
                Clock.schedule_once(lambda _: self.stop(), 3)

        def profile(self):
            return Profile(**{key: field.text.strip() for key, field in self.fields.items() if key != "password"})

        def error(self, exc):
            self.summary.text = "Erreur : " + str(exc)
            logging.getLogger("EU4").error("%s", exc)

        def browse(self, key, filters):
            current = Path(self.fields[key].text or self.fields["user_dir"].text or Path.home())
            if key == "save" and not self.fields[key].text:
                current = current / "save games"
            if current.is_file():
                current = current.parent
            while not current.is_dir() and current != current.parent:
                current = current.parent
            chooser = FileChooserListView(path=str(current), dirselect=filters is None,
                                          filters=filters or [], multiselect=False)
            content = BoxLayout(orientation="vertical", spacing=dp(8))
            # Editable path also permits switching Windows drive letters.
            location = TextInput(text=str(current), multiline=False, size_hint_y=None, height=dp(36))
            location.bind(on_text_validate=lambda field: setattr(chooser, "path", field.text))
            chooser.bind(path=lambda _, value: setattr(location, "text", value))
            content.add_widget(location)
            content.add_widget(chooser)
            buttons = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
            choose = Button(text="Sélectionner")
            cancel = Button(text="Annuler")
            buttons.add_widget(cancel)
            buttons.add_widget(choose)
            content.add_widget(buttons)
            popup = Popup(title="Sélection du dossier" if filters is None else "Sélection du fichier",
                          content=content, size_hint=(0.92, 0.9))

            def select(_):
                selected = chooser.selection[0] if chooser.selection else chooser.path if filters is None else None
                if selected:
                    self.fields[key].text = selected
                    popup.dismiss()

            choose.bind(on_release=select)
            cancel.bind(on_release=lambda _: popup.dismiss())
            popup.open()

        def install(self, _):
            try:
                profile = self.profile()
                path = profile.install()
                profile.write(self.profile_path)
                manifest = profile.read_manifest()
                self.summary.text = (f"Mod installé : {manifest.country}, 1444-11-11, sans Ironman.\n"
                                     "Activez-le, prenez la décision de liaison, puis sauvegardez localement.")
                logging.getLogger("EU4").info("Mod installé : %s", path)
            except (OSError, ValueError, TypeError) as exc:
                self.error(exc)

        def toggle_connection(self, _):
            if self.session_task and not self.session_task.done():
                self.connect_button.disabled = True
                self.session.stop()
                return
            self.session_task = asyncio.create_task(self.connect(), name="EU4 campaign")

        async def connect(self):
            for control in self.edit_controls:
                control.disabled = True
            self.connect_button.text = "Déconnecter"
            self.summary.text = "Connexion en cours…"
            try:
                profile = self.profile()
                profile.write(self.profile_path)
                self.session = Session(profile, self.fields["password"].text)
                await self.session.run(lambda text: setattr(self.summary, "text", text))
                self.summary.text = "Déconnecté. La progression est conservée."
            except Exception as exc:
                self.error(exc)
            finally:
                self.session = None
                self.fields["password"].text = ""
                self.connect_button.text = "Se connecter"
                self.connect_button.disabled = False
                for control in self.edit_controls:
                    control.disabled = False

        def send_message(self, _):
            try:
                if not self.session:
                    raise ValueError("Connectez le client avant d'envoyer un message.")
                if self.message.text:
                    self.session.command(self.message.text)
                    self.message.text = ""
            except (OSError, ValueError) as exc:
                self.error(exc)

        def drain_logs(self, _):
            changed = False
            while not self.log_handler.messages.empty():
                self.lines.append(self.log_handler.messages.get_nowait())
                changed = True
            if changed:
                self.journal.text = "\n".join(self.lines)
                self.journal.cursor = (0, len(self.journal._lines) - 1)

        def on_stop(self):
            if self.session:
                self.session.stop()
            self.log_timer.cancel()
            for logger, level in zip(self.loggers, self.old_levels):
                logger.removeHandler(self.log_handler)
                logger.setLevel(level)
            self.log_handler.close()

    async def run():
        app = EU4App()
        try:
            await app.async_run(async_lib="asyncio")
        finally:
            if getattr(app, "session", None):
                app.session.stop()
            if getattr(app, "session_task", None):
                await app.session_task

    asyncio.run(run())
