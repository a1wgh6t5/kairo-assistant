"""Bounded, staged source repair. A model never edits the running installation.

Only selected non-security modules can be patched. Candidate code runs under
Linux bubblewrap when available; on other platforms an explicit trusted-run
flag is required. Promotion always needs --approve and a verified candidate.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from secrets import token_hex

from .audit import recent
from .config import data_dir, model_paths, read_config
from .models import verify_models
from .providers import QwenLocal


class RepairError(RuntimeError):
    pass


PATCHABLE = {"kairo/voice.py", "kairo/providers.py", "kairo/ui.py"}
ROOT = Path(__file__).resolve().parent.parent


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _store() -> Path:
    location = data_dir() / "repairs"
    location.mkdir(mode=0o700, parents=True, exist_ok=True)
    return location


def _metadata(candidate: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[0-9a-f]{12}", candidate):
        raise RepairError("Invalid candidate ID")
    path = _store() / candidate
    if not (path / "metadata.json").is_file():
        raise RepairError("Unknown candidate")
    return path, json.loads((path / "metadata.json").read_text(encoding="utf-8"))


def _save(path: Path, metadata: dict) -> None:
    target = path / "metadata.json"
    target.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o600)


def diagnose() -> dict:
    models = verify_models()
    errors = [event for event in recent() if not event.get("success")][-10:]
    suggestions = []
    for model, result in models.items():
        if not result["installed"]:
            suggestions.append(f"Install the local {model} model before using it")
        elif not result["verified"]:
            suggestions.append(f"Verify or reinstall the {model} model weights")
    if errors:
        suggestions.append(f"Most recent failure: {errors[-1]['component']}/{errors[-1]['action']} ({errors[-1]['error_type']})")
    return {"models": models, "recent_failures": errors, "suggestions": suggestions}


def _patch_paths(patch: str) -> list[str]:
    before = []
    after = []
    diffs = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" ")
            if len(parts) != 4 or parts[1] != "a/" + parts[2].removeprefix("b/"):
                raise RepairError("Patch contains a malformed diff header")
            diffs.append(parts[1][2:])
        elif line.startswith("--- "):
            before.append(line[4:].split("\t", 1)[0])
        elif line.startswith("+++ "):
            after.append(line[4:].split("\t", 1)[0])
    if not before or len(before) != len(after):
        raise RepairError("Patch needs matching --- and +++ file headers")
    paths = []
    for old, new in zip(before, after):
        if not old.startswith("a/") or not new.startswith("b/") or old[2:] != new[2:]:
            raise RepairError("Creating, deleting, or renaming files is not supported")
        name = old[2:]
        if name not in PATCHABLE or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise RepairError(f"Protected or unsupported patch target: {name}")
        paths.append(name)
    if diffs and diffs != paths:
        raise RepairError("Diff headers disagree with file headers")
    return paths


def stage(patch: str, *, source: str = "supplied") -> dict:
    if len(patch.encode("utf-8")) > 100_000:
        raise RepairError("Patch exceeds the 100 KB limit")
    paths = _patch_paths(patch)
    if not shutil.which("git"):
        raise RepairError("git is required to stage a unified diff")
    ident = token_hex(6)
    folder = _store() / ident
    folder.mkdir(mode=0o700)
    tree = folder / "tree"
    shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns("__pycache__", ".venv", ".git", "*.pyc", "*.gguf"))
    patch_file = folder / "proposal.patch"
    patch_file.write_text(patch, encoding="utf-8")
    if os.name != "nt":
        patch_file.chmod(0o600)
    baseline = {name: _hash(ROOT / name) for name in paths}
    try:
        for flag in ("--check", "--apply"):
            command = ["git", "apply", "--whitespace=error"]
            if flag == "--check":
                command.append("--check")
            command.append(str(patch_file))
            result = subprocess.run(command, cwd=tree, text=True, capture_output=True, timeout=15)
            if result.returncode:
                raise RepairError("Patch rejected by git: " + result.stderr[:500])
        # Inspect all source files, not only the headers: guard against a diff
        # that changes paths outside the allowed set through unusual syntax.
        original = {str(p.relative_to(ROOT)): _hash(p) for p in ROOT.rglob("*")
                    if p.is_file() and not any(part in {"__pycache__", ".venv", ".git"} for part in p.parts)
                    and p.suffix != ".pyc"}
        changed = {name for name, old in original.items() if not (tree / name).is_file() or _hash(tree / name) != old}
        new_files = {str(p.relative_to(tree)) for p in tree.rglob("*") if p.is_file() and
                     not any(part in {"__pycache__", ".venv", ".git"} for part in p.parts) and
                     p.suffix != ".pyc" and str(p.relative_to(tree)) not in original}
        if changed != set(paths) or new_files:
            raise RepairError("Candidate changed files outside the declared patch targets")
        for name in changed:
            ast.parse((tree / name).read_text(encoding="utf-8"), filename=name)
    except Exception:
        shutil.rmtree(folder)
        raise
    metadata = {"id": ident, "source": source, "paths": sorted(set(paths)), "baseline": baseline,
                "candidate": {name: _hash(tree / name) for name in paths}, "verification": "pending"}
    _save(folder, metadata)
    return metadata


def _test_command(tree: Path) -> list[str] | None:
    if sys.platform != "linux" or not shutil.which("bwrap"):
        return None
    commands = [shutil.which("bwrap"), "--die-with-parent", "--unshare-all", "--new-session", "--clearenv"]
    for root in ("/usr", "/bin", "/lib", "/lib64", "/opt", "/etc"):
        if Path(root).exists():
            commands += ["--ro-bind", root, root]
    commands += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/work",
                 "--bind", str(tree), "/work", "--chdir", "/work",
                 "--setenv", "HOME", "/tmp", "--setenv", "PYTHONPATH", "/work",
                 "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                 sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    return commands


def verify(candidate: str, *, trusted_run: bool = False) -> dict:
    folder, metadata = _metadata(candidate)
    tree = folder / "tree"
    for name in metadata["paths"]:
        if _hash(tree / name) != metadata["candidate"][name]:
            raise RepairError("Candidate changed after staging")
        ast.parse((tree / name).read_text(encoding="utf-8"), filename=name)
    cmd = _test_command(tree)
    method = "isolated Linux sandbox"
    if trusted_run:
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
        method = "explicit trusted local run"
    if cmd is None:
        metadata["verification"] = "sandbox unavailable"
        _save(folder, metadata)
        return {"id": candidate, "status": "sandbox unavailable", "tests": "not run"}
    try:
        result = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, timeout=60,
                                env={"PATH": os.environ.get("PATH", ""), "HOME": str(folder),
                                     "PYTHONPATH": str(tree), "PYTHONDONTWRITEBYTECODE": "1"})
        passed = result.returncode == 0
        message = (result.stdout + result.stderr)[-2500:]
        unavailable = not trusted_run and not passed and any(marker in message.lower() for marker in (
            "operation not permitted", "failed to create", "user namespace", "bwrap:"
        ))
    except subprocess.TimeoutExpired:
        passed, unavailable, message = False, False, "Candidate tests timed out after 60 seconds"
    metadata["verification"] = "passed" if passed else "sandbox unavailable" if unavailable else "failed"
    metadata["method"] = method
    _save(folder, metadata)
    return {"id": candidate, "status": metadata["verification"], "method": method, "test_output": message}


def apply(candidate: str, *, approve: bool = False) -> dict:
    if not approve:
        raise RepairError("Explicit --approve is required to install a candidate")
    folder, metadata = _metadata(candidate)
    if metadata["verification"] != "passed":
        raise RepairError("Candidate tests must pass before installation")
    for name in metadata["paths"]:
        if _hash(ROOT / name) != metadata["baseline"][name]:
            raise RepairError("Source changed since staging; create a new candidate")
        if _hash(folder / "tree" / name) != metadata["candidate"][name]:
            raise RepairError("Candidate changed since verification")
    backup = folder / "backup"
    backup.mkdir()
    replaced = []
    try:
        for name in metadata["paths"]:
            target = ROOT / name
            original = backup / name
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, original)
            temp = target.with_suffix(".repair-tmp")
            shutil.copy2(folder / "tree" / name, temp)
            os.replace(temp, target)
            replaced.append(name)
    except Exception:
        for name in replaced:
            shutil.copy2(backup / name, ROOT / name)
        raise
    metadata["applied"] = True
    _save(folder, metadata)
    (_store() / "last-good.json").write_text(json.dumps({"id": candidate}) + "\n", encoding="utf-8")
    return {"status": "applied", "id": candidate, "files": metadata["paths"]}


def rollback() -> dict:
    record = _store() / "last-good.json"
    if not record.is_file():
        raise RepairError("No earlier applied candidate is available")
    candidate = json.loads(record.read_text())["id"]
    folder, metadata = _metadata(candidate)
    if not metadata.get("applied"):
        raise RepairError("Candidate is not active")
    for name in metadata["paths"]:
        if _hash(ROOT / name) != metadata["candidate"][name]:
            raise RepairError("Source changed after installation; automatic rollback would overwrite newer work")
    for name in metadata["paths"]:
        target = ROOT / name
        temp = target.with_suffix(".repair-tmp")
        shutil.copy2(folder / "backup" / name, temp)
        os.replace(temp, target)
    metadata["applied"] = False
    _save(folder, metadata)
    record.unlink()
    return {"status": "rolled back", "id": candidate}


def propose(error: str, target: str, *, attempts: int = 3) -> dict:
    """Ask local Qwen for a diff, retrying only syntax and staging failures."""
    if target not in PATCHABLE:
        raise RepairError("Select a patchable file: " + ", ".join(sorted(PATCHABLE)))
    if len(error) > 2000 or not 1 <= attempts <= 3:
        raise RepairError("Error must be short; automatic attempts are limited to three")
    cfg = read_config()
    _, model = model_paths(cfg)
    qwen = QwenLocal(model, binary=cfg.get("llama_server", "llama-server"), port=cfg.get("qwen_port", 18080))
    feedback = ""
    try:
        source = (ROOT / target).read_text(encoding="utf-8")[:12_000]
        for attempt in range(1, attempts + 1):
            prompt = (f"Write a minimal git unified diff fixing this error in {target}. "
                      f"Only modify {target}; output diff text, no Markdown. Error: {error}. {feedback}")
            response = qwen.chat(prompt, source)
            patch = re.sub(r"^```(?:diff)?\s*|\s*```$", "", response.strip(), flags=re.I)
            try:
                return stage(patch, source=f"local Qwen attempt {attempt}")
            except (RepairError, SyntaxError) as exc:
                feedback = f"Previous diff was rejected: {str(exc)[:200]}."
        raise RepairError(f"Qwen could not stage a valid patch in {attempts} attempts")
    finally:
        qwen.close()
