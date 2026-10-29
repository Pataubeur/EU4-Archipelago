"""Check a prepared source runtime, or a fresh copy of a Windows installation."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "eu4"))
from runtime.manifest import Manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ap-root", type=Path, required=True)
    parser.add_argument("--frozen", action="store_true", help="Test a Windows installation in a fresh copy")
    parser.add_argument("--work-dir", type=Path, help="New directory for the frozen runtime copy and evidence")
    args = parser.parse_args()
    ap = args.ap_root.resolve()
    if args.frozen:
        if not args.work_dir:
            parser.error("--frozen requires --work-dir (a new directory; keeps evidence)")
        return check_frozen(ap, args.work_dir.resolve())
    if not (ap / "Generate.py").is_file():
        parser.error("Archipelago source runtime with dependencies is required")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        players = root / "players"
        players.mkdir()
        (players / "eu4.yaml").write_bytes((ROOT / "config/example.yaml").read_bytes())
        subprocess.run([sys.executable, str(ap / "Generate.py"), "--player_files_path", str(players),
                        "--outputpath", str(root / "output"), "--seed", "12345", "--multi", "1", "--spoiler", "1"],
                       cwd=ap, check=True)
        found = []
        for path in (root / "output").rglob("*.apeu4.json"):
            found.append(Manifest.read(path))
        for path in (root / "output").rglob("*.zip"):
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith(".apeu4.json"):
                        target = root / "manifest.json"
                        target.write_bytes(archive.read(name))
                        found.append(Manifest.read(target))
        if not found or not all(m.country == "FRA" and len(m.locations) == 16 for m in found):
            raise RuntimeError("Generation did not emit the expected valid EU4 manifest")
        print("PASS: real AP YAML generation and manifest validation. EU4 and server not tested.")
    return 0


def check_frozen(ap: Path, work: Path) -> int:
    """Use only official installed executables; never change the source installation."""
    for exe in ("ArchipelagoLauncher.exe", "ArchipelagoGenerate.exe"):
        if not (ap / exe).is_file():
            raise ValueError(f"Missing standard Archipelago executable: {ap / exe}")
    if work.exists():
        raise ValueError("Work directory must not exist; choose a new directory to preserve existing data")
    if ap == work or ap in work.parents:
        raise ValueError("Work directory must be outside the source installation")
    package = ROOT / "dist/release/eu4.apworld"
    if not package.is_file():
        raise ValueError("Build first: python scripts/build_apworld.py")
    shutil.copytree(ap, work, ignore=shutil.ignore_patterns(
        "custom_worlds", "Players", "players", "output", "logs", "integration", "__pycache__",
        "_persistent_storage.yaml", "host.yaml", "*.log", "*.apsave"))
    (work / "custom_worlds").mkdir(exist_ok=True)
    shutil.copyfile(package, work / "custom_worlds/eu4.apworld")
    evidence = work / "eu4-validation"
    evidence.mkdir()
    players = evidence / "players"
    players.mkdir()
    shutil.copyfile(ROOT / "config/example.yaml", players / "eu4.yaml")

    def run(exe: str, *arguments: str) -> None:
        with (evidence / f"{exe}-{len(list(evidence.glob('*.log')))}.log").open("w", encoding="utf-8") as log:
            subprocess.run([str(work / exe), *arguments], cwd=work, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=180)

    run("ArchipelagoLauncher.exe", "Generate Template Options", "--", "--skip_open_folder")
    templates = list((work / "Players/Templates").glob("*Europa Universalis IV*.yaml"))
    if len(templates) != 1:
        raise RuntimeError("Official Launcher did not export the EU4 YAML template")
    run("ArchipelagoGenerate.exe", "--player_files_path", str(players), "--outputpath", str(evidence / "output"),
        "--seed", "12345", "--multi", "1", "--spoiler", "1")
    manifests = []
    for path in (evidence / "output").glob("*.zip"):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith(".apeu4.json"):
                    target = evidence / Path(name).name
                    target.write_bytes(archive.read(name))
                    manifests.append(Manifest.read(target))
    if len(manifests) != 1 or manifests[0].seed == "OFFLINE-POC" or len(manifests[0].locations) != 16:
        raise RuntimeError("Generation did not emit one real 16-location manifest")
    marker = evidence / "gui-smoke.txt"
    run("ArchipelagoLauncher.exe", "EU4 Client", "--", "--profile", str(evidence / "client.json"),
        "--smoke-test", str(marker))
    deadline = time.monotonic() + 30
    while not marker.is_file() and time.monotonic() < deadline:
        time.sleep(0.2)
    if not marker.is_file() or not marker.read_text().startswith("PASS:"):
        raise RuntimeError("Frozen Launcher did not build the EU4 client UI; inspect logs")
    result = {"package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
              "yaml_template": str(templates[0]), "manifest": manifests[0].token,
              "passed": ["custom_worlds load", "YAML template", "seed generation", "manifest", "Launcher UI startup"],
              "not_tested": ["EU4", "server transport", "manual GUI interactions"]}
    (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: frozen runtime checks; evidence: {evidence}. EU4 and server not tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
