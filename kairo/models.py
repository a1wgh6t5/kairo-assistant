"""Explicit one-time downloads. Inference uses on-disk files and no network."""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

from .config import data_dir


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_laya() -> dict:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install the edge extra: pip install '.[edge]'") from exc
    repository = "convaiinnovations/laya"
    revision = HfApi().repo_info(repository).sha
    target = data_dir() / "models" / "laya"
    snapshot_download(repo_id=repository, revision=revision, local_dir=target, allow_patterns=[
        "model.safetensors", "rl_agent_config.json", "rl_agent_api.py", "rl_common.py", "encoder/*", "tokenizer/*"
    ])
    weights = target / "model.safetensors"
    if not weights.is_file():
        raise RuntimeError("Laya checkpoint is incomplete")
    manifest = {"repository": repository, "revision": revision, "weights_sha256": _sha256(weights)}
    (target / "kairo-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def install_qwen() -> dict:
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:
        raise RuntimeError("Install the edge extra: pip install '.[edge]'") from exc
    repository, filename = "Qwen/Qwen3-0.6B-GGUF", "Qwen3-0.6B-Q8_0.gguf"
    revision = HfApi().repo_info(repository).sha
    source = Path(hf_hub_download(repo_id=repository, filename=filename, revision=revision))
    target = data_dir() / "models" / "qwen.gguf"
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)
    manifest = {"repository": repository, "revision": revision, "weights_sha256": _sha256(target)}
    (target.parent / "qwen-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def install_voice() -> dict:
    """Fetch the official small English Vosk model for offline Pi speech."""
    source = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    target = data_dir() / "models" / "vosk-model-small-en-us-0.15"
    if target.exists():
        raise RuntimeError("Voice model already exists; keep the installed revision or remove it manually")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix="voice-download-") as tmp:
        zipped = Path(tmp) / "model.zip"
        with urlopen(source, timeout=60) as response, zipped.open("wb") as out:
            total = 0
            while chunk := response.read(1 << 20):
                total += len(chunk)
                if total > 100_000_000:
                    raise RuntimeError("Voice model download exceeds the 100 MB limit")
                out.write(chunk)
        package_hash = _sha256(zipped)
        with zipfile.ZipFile(zipped) as archive:
            entries = archive.infolist()
            if sum(e.file_size for e in entries) > 300_000_000:
                raise RuntimeError("Voice model archive expands beyond the 300 MB limit")
            for entry in entries:
                parts = PurePosixPath(entry.filename).parts
                if ("\\" in entry.filename or not parts or parts[0] != target.name or
                        ".." in parts or entry.filename.startswith("/")):
                    raise RuntimeError("Voice model archive contains an unexpected path")
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise RuntimeError("Voice model archive contains a symbolic link")
            archive.extractall(tmp)
        extracted = Path(tmp) / target.name
        if not (extracted / "am" / "final.mdl").is_file():
            raise RuntimeError("Voice model archive is incomplete")
        shutil.move(str(extracted), str(target))
    manifest = {"source": source, "archive_sha256": package_hash,
                "model_sha256": _sha256(target / "am" / "final.mdl")}
    (target.parent / "voice-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify_models() -> dict:
    result = {}
    for name, filename in (("laya", "laya/model.safetensors"), ("qwen", "qwen.gguf")):
        path = data_dir() / "models" / filename
        manifest_path = path.parent / ("kairo-manifest.json" if name == "laya" else "qwen-manifest.json")
        installed = path.is_file()
        try:
            manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        except ValueError:
            manifest = {}
        result[name] = {"installed": installed, "verified": installed and bool(manifest) and _sha256(path) == manifest.get("weights_sha256")}
    voice_path = data_dir() / "models" / "vosk-model-small-en-us-0.15" / "am" / "final.mdl"
    voice_manifest = voice_path.parents[2] / "voice-manifest.json"
    try:
        manifest = json.loads(voice_manifest.read_text()) if voice_manifest.is_file() else {}
    except ValueError:
        manifest = {}
    result["voice"] = {"installed": voice_path.is_file(), "verified": voice_path.is_file() and
                       bool(manifest) and _sha256(voice_path) == manifest.get("model_sha256")}
    return result
