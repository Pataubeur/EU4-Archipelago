"""Register a client that also runs inside the frozen Archipelago launcher."""
from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, launch_subprocess

from .runtime.data import GAME


def launch_client(*args: str) -> None:
    # Import the UI only in the child: kvui must initialize Kivy's frozen paths.
    from .runtime.gui import launch
    launch_subprocess(launch, name="EU4 Client", args=args)


components.append(Component(
    "EU4 Client", func=launch_client, component_type=Type.CLIENT,
    game_name=GAME, file_identifier=SuffixIdentifier(".apeu4.json"),
    description="Connect Europa Universalis IV saves to an Archipelago multiworld.",
))
