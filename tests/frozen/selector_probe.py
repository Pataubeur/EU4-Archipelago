"""Executed only from a validation APWorld in an isolated frozen AP installation.

Drive the official Options Creator, check its real widgets and export through its
normal YAML action with the OS save dialog redirected to the evidence directory.
"""
import sys
from pathlib import Path

if Path(sys.executable).name == "ArchipelagoOptionsCreator.exe":
    import json
    import traceback
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window

    evidence = Path(sys.executable).parent / "eu4-validation"
    result = {}

    def fail():
        (evidence / "options-probe-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        if App.get_running_app():
            App.get_running_app().stop()

    def exported(_):
        try:
            target = evidence / "ui-export.yaml"
            if not target.exists():
                return True
            import yaml
            data = yaml.safe_load(target.read_text())
            assert data["Europa Universalis IV"]["starting_country"] == "mng", data
            result["exported"] = data["Europa Universalis IV"]
            (evidence / "options-probe-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            App.get_running_app().stop()
        except Exception:
            fail()
        return False

    def choose(_):
        try:
            app = App.get_running_app()
            menu = next(w for w in Window.children if w.__class__.__name__ == "MDDropdownMenu")
            labels = [item["text"] for item in menu.items]
            result["labels"] = labels
            assert labels[-1] == "Other country (advanced tag)", labels
            assert labels[:-1] == sorted(labels[:-1], key=str.casefold), labels
            next(item for item in menu.items if item["text"] == "Ming (MNG)")["on_release"]()
            assert app.options["starting_country"] == "mng", app.options
            assert result.pop("selector").text.text == "Ming (MNG)"
            app.name_input.text = "EU4UIProbe"
            import Utils
            Utils.save_filename = lambda *a, **kw: str(evidence / "ui-export.yaml")
            app.export_options(None)
            Clock.schedule_interval(exported, 0.2)
        except Exception:
            fail()

    def inspect(_):
        try:
            app = App.get_running_app()
            if not app or not hasattr(app, "scrollbox"):
                return True
            if not getattr(app, "eu4_probe_ready", False):
                button = next(w for w in app.scrollbox.layout.children
                              if getattr(getattr(w, "world_cls", None), "game", None) == "Europa Universalis IV")
                app.create_options_panel(button)
                app.eu4_probe_ready = True
                for panel in app.option_layout.walk():
                    if panel.__class__.__name__ == "MDExpansionPanel":
                        panel.open()
                return True
            widgets = list(app.option_layout.walk())
            selector = next(w for w in widgets if getattr(w, "name", None) == "starting_country"
                            and w.__class__.__name__ == "VisualChoice")
            assert not any(w.__class__.__name__ == "VisualTextChoice" for w in widgets)
            assert selector.text.text == "France (FRA)", selector.text.text
            custom = next(w for w in widgets if getattr(w, "name", None) == "custom_starting_country")
            assert custom.text == "FRA", custom.text
            result.update(default=selector.text.text, custom_default=custom.text, selector=selector)
            Clock.schedule_once(lambda _: Window.screenshot(name=str(evidence / "options-default.png")), 0.8)
            Clock.schedule_once(lambda _: selector.dispatch("on_release"), 1.4)
            Clock.schedule_once(choose, 2.0)
        except Exception:
            fail()
        return False

    Clock.schedule_interval(inspect, 0.2)
