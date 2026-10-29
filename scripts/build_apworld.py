"""Build public player artifacts, with optional separately stored developer tools."""
from __future__ import annotations

import hashlib
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld/eu4"))
from runtime.version import VERSION, AP_VERSION, EU4_VERSION


def archive(output: Path, entries: list[tuple[Path | bytes, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for path, name in sorted(entries, key=lambda p: p[1]):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            target.writestr(info, path if isinstance(path, bytes) else path.read_bytes())


def source_files(root: Path):
    return [p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts
            and p.suffix in (".py", ".json", ".md", ".txt", ".mod", ".yml")]


def build(output: Path) -> list[Path]:
    world = ROOT / "apworld" / "eu4"
    output.mkdir(parents=True, exist_ok=True)
    artifacts = [output / "eu4.apworld", output / "example.yaml", output / "RELEASE.json",
                 output / f"eu4-player-kit-{VERSION}.zip"]
    # APContainer format used by AP 0.6.7. Keep container fields out of the
    # source-world manifest, as Archipelago's own APWorld builder does.
    metadata = json.loads((world / "archipelago.json").read_text(encoding="utf-8"))
    if metadata["world_version"] != VERSION or metadata["minimum_ap_version"] != AP_VERSION:
        raise ValueError("World metadata and runtime release versions disagree")
    metadata.update(version=7, compatible_version=7)
    manifest_bytes = (json.dumps(metadata, indent=2) + "\n").encode("utf-8")
    archive(artifacts[0], [(p, "eu4/" + p.relative_to(world).as_posix()) for p in source_files(world)]
            + [(ROOT / "LICENSE", "eu4/LICENSE"), (manifest_bytes, "archipelago.json")])
    artifacts[1].write_bytes((ROOT / "config/example.yaml").read_bytes())
    release = {"version": VERSION, "archipelago_test_target": AP_VERSION,
               "eu4_test_target": EU4_VERSION, "status": "candidate; EU4 acceptance pending",
               "dependencies": "Archipelago Windows installation; no extra Python packages",
               "artifacts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts[:2]}}
    artifacts[2].write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    docs = [(ROOT / name, name) for name in ("README.md", "LICENSE")]
    docs += [(p, "docs/" + p.relative_to(ROOT / "docs").as_posix()) for p in source_files(ROOT / "docs")]
    archive(artifacts[3], [(p, p.name) for p in artifacts[:3]] + docs)
    checksums(output, artifacts)
    return artifacts


def checksums(output: Path, artifacts: list[Path]) -> None:
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts)
    (output / "SHA256SUMS").write_text(sums, encoding="ascii")


def build_tools(output: Path) -> list[Path]:
    world = ROOT / "apworld/eu4"
    client = [(p, "eu4_client/" + p.relative_to(world / "runtime").as_posix())
              for p in source_files(world / "runtime")]
    artifacts = [output / "eu4-client-source.zip"]
    archive(artifacts[0], client + [(ROOT / "LICENSE", "LICENSE"),
                                  (ROOT / "docs/development.md", "DEVELOPMENT.md")])
    checksums(output, artifacts)
    return artifacts


def build_demo(output: Path) -> list[Path]:
    # Render from source rather than packaging potentially stale checked-in PoC.
    import tempfile
    from runtime.data import select_objectives
    from runtime.manifest import Manifest
    from runtime.render import atomic_text, install_mod
    artifacts = [output / "OFFLINE-ONLY-eu4-mod.zip"]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        manifest = Manifest("OFFLINE-POC", 1, 0, "FRA", tuple(o.id for o in select_objectives(12, True, True)))
        mod = install_mod(manifest, root)
        descriptor = (mod / "descriptor.mod").read_text(encoding="utf-8")
        atomic_text(root / "mod/eu4_archipelago.mod", descriptor + 'path="mod/eu4_archipelago"\n')
        archive(artifacts[0], [(p, p.relative_to(root / "mod").as_posix()) for p in source_files(root / "mod")]
                + [(b"OFFLINE DEMONSTRATION ONLY. Not a generated multiworld seed.\n", "OFFLINE-ONLY.txt")])
    checksums(output, artifacts)
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / "dist/release")
    parser.add_argument("--include-tools", action="store_true", help="Also build dist/tools (requires Python to use)")
    parser.add_argument("--include-demos", action="store_true", help="Also render dist/demos (never use online)")
    args = parser.parse_args()
    artifacts = build(args.output)
    if args.include_tools:
        artifacts += build_tools(args.output.parent / "tools")
    if args.include_demos:
        artifacts += build_demo(args.output.parent / "demos")
    for artifact in artifacts:
        print(artifact)
