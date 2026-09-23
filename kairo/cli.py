"""One entry point for desktop, Pi Node, models, routines, and diagnostics."""
from __future__ import annotations

import argparse
import getpass
import json
import shlex
import sys

from .config import model_paths, read_config, voice_model_path
from .engine import Engine
from .models import install_laya, install_qwen, install_voice, verify_models
from .pairing import fingerprint, init_desktop, save_peer
from .routines import get, names, save
from .secrets import set_secret
from .server import serve_desktop
from .tools import REGISTRY


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="kairo", description="Kairo local-first assistant prototype")
    command = root.add_subparsers(dest="command", required=True)
    ask = command.add_parser("ask", help="Act on this computer")
    ask.add_argument("text")
    ask.add_argument("--file", help="Text file for local Qwen summarization")
    ask.add_argument("--chat", action="store_true", help="Ask Qwen directly")
    ask.add_argument("--allow-jev", action="store_true", help="Allow explicit Jev cloud fallback")
    tool = command.add_parser("tool", help="Execute a registered action")
    tool.add_argument("name", choices=list(REGISTRY))
    tool.add_argument("--source")
    tool.add_argument("--destination")
    tool.add_argument("--path")
    tool.add_argument("--url")
    tool.add_argument("--role")
    tool.add_argument("--name", dest="element_name")
    tool.add_argument("--label")
    tool.add_argument("--text")
    tool.add_argument("--remote", action="store_true")
    tool.add_argument("--confirm", action="store_true")
    desktop = command.add_parser("desktop")
    desk_cmd = desktop.add_subparsers(dest="desktop_command", required=True)
    desk_cmd.add_parser("init")
    desk_cmd.add_parser("fingerprint")
    serving = desk_cmd.add_parser("serve")
    serving.add_argument("--host", default="0.0.0.0")
    serving.add_argument("--port", type=int, default=18443)
    node = command.add_parser("node")
    node_cmd = node.add_subparsers(dest="node_command", required=True)
    pairing = node_cmd.add_parser("pair")
    pairing.add_argument("--url", required=True, help="https://desktop-LAN-IP:18443")
    pairing.add_argument("--fingerprint", required=True)
    remote_ask = node_cmd.add_parser("ask")
    remote_ask.add_argument("text")
    remote_ask.add_argument("--file")
    remote_ask.add_argument("--chat", action="store_true")
    remote_ask.add_argument("--allow-jev", action="store_true")
    node_cmd.add_parser("shell", help="Keep local models warm and accept typed commands")
    node_voice = node_cmd.add_parser("voice", help="Offline microphone and Kairo wake phrase")
    node_voice.add_argument("--mute", action="store_true")
    voice = command.add_parser("voice", help="Run offline microphone on this computer")
    voice.add_argument("--mute", action="store_true")
    browser = command.add_parser("browser", help="Persistent interactive browser session")
    browser.add_argument("--remote", action="store_true", help="Use the paired desktop's browser")
    routine = command.add_parser("routine")
    routine_cmd = routine.add_subparsers(dest="routine_command", required=True)
    routine_cmd.add_parser("list")
    rs = routine_cmd.add_parser("save")
    rs.add_argument("name")
    rr = routine_cmd.add_parser("run")
    rr.add_argument("name")
    rr.add_argument("--confirm", action="store_true")
    models = command.add_parser("models")
    models.add_argument("action", choices=["install-laya", "install-qwen", "install-voice", "verify"])
    key = command.add_parser("key")
    key.add_argument("action", choices=["set-jev"])
    command.add_parser("doctor")
    repair = command.add_parser("repair", help="Diagnose, stage, verify, apply or roll back code repairs")
    repair_cmd = repair.add_subparsers(dest="repair_command", required=True)
    repair_cmd.add_parser("diagnose")
    stage = repair_cmd.add_parser("stage")
    stage.add_argument("patch", help="Path to a unified diff")
    propose = repair_cmd.add_parser("propose")
    propose.add_argument("--error", required=True, help="A short diagnostic to fix")
    propose.add_argument("--file", required=True, help="Patchable file such as kairo/voice.py")
    verify = repair_cmd.add_parser("verify")
    verify.add_argument("id")
    verify.add_argument("--trusted-run", action="store_true", help="Explicitly run candidate tests without a sandbox")
    apply = repair_cmd.add_parser("apply")
    apply.add_argument("id")
    apply.add_argument("--approve", action="store_true")
    repair_cmd.add_parser("rollback")
    acceptance = command.add_parser("acceptance", help="Run hardware acceptance checks")
    acceptance_cmd = acceptance.add_subparsers(dest="acceptance_command", required=True)
    pi = acceptance_cmd.add_parser("pi")
    pi.add_argument("--mic-seconds", type=int, default=0, help="Say Kairo during a 1–15 second microphone recording")
    command.add_parser("ui", help="Open the prototype desktop interface")
    return root


def _run_engine(remote: bool, text: str, file: str | None = None, chat: bool = False,
                allow_jev: bool = False) -> None:
    engine = Engine(remote=remote)
    try:
        answer = engine.ask(text, file=file, chat=chat, allow_jev=allow_jev)
        print(answer.text)
        print(f"[{answer.route}; {answer.location}]", file=sys.stderr)
    finally:
        engine.close()


def _shell() -> None:
    engine = Engine(remote=True)
    try:
        engine.laya.prewarm()
        engine.qwen.prewarm()
        print("Kairo Node ready. Both local models resident; type 'exit' to stop.")
        while True:
            try:
                line = input("Kairo> ").strip()
            except EOFError:
                break
            if line.lower() in {"exit", "quit"}:
                break
            if line:
                try:
                    answer = engine.ask(line)
                    print(f"{answer.text}\n[{answer.route}; {answer.location}]")
                except Exception as exc:
                    print(f"Error: {exc}", file=sys.stderr)
    finally:
        engine.close()


def _browser_shell(remote: bool) -> None:
    engine = Engine(remote=remote)
    print("Browser commands: open URL | read | click ROLE 'Exact name' | fill 'Field label' | close | exit")
    try:
        while True:
            try:
                parts = shlex.split(input("Browser> "))
            except EOFError:
                break
            if not parts:
                continue
            verb = parts[0].lower()
            if verb in {"exit", "quit"}:
                break
            try:
                if verb == "open" and len(parts) == 2:
                    answer = engine.tool("browser_navigate", {"url": parts[1]})
                elif verb == "read" and len(parts) == 1:
                    answer = engine.tool("browser_read", {})
                elif verb == "click" and len(parts) == 3:
                    if input(f"Click {parts[1]} '{parts[2]}'? [y/N] ").lower() != "y":
                        continue
                    answer = engine.tool("browser_click", {"role": parts[1], "name": parts[2]}, confirmed=True)
                elif verb == "fill" and len(parts) == 2:
                    value = getpass.getpass(f"Value for '{parts[1]}': ")
                    if input(f"Fill '{parts[1]}'? [y/N] ").lower() != "y":
                        continue
                    answer = engine.tool("browser_fill", {"label": parts[1], "text": value}, confirmed=True)
                elif verb == "close" and len(parts) == 1:
                    answer = engine.tool("browser_close", {})
                else:
                    print("Use: open URL | read | click ROLE 'Exact name' | fill 'Field label' | close")
                    continue
                print(answer.text)
            except Exception as exc:
                print(f"Kairo: {exc}", file=sys.stderr)
    finally:
        engine.close()


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "ask":
            _run_engine(False, args.text, args.file, args.chat, args.allow_jev)
        elif args.command == "tool":
            arguments = ({"source": args.source, "destination": args.destination} if args.name == "move_file" else
                         {"path": args.path} if args.name == "read_text" else
                         {"url": args.url} if args.name == "browser_navigate" else
                         {"role": args.role, "name": args.element_name} if args.name == "browser_click" else
                         {"label": args.label, "text": args.text} if args.name == "browser_fill" else {})
            engine = Engine(remote=args.remote)
            try:
                print(engine.tool(args.name, arguments, confirmed=args.confirm).text)
            finally:
                engine.close()
        elif args.command == "desktop":
            if args.desktop_command == "init":
                token, pin = init_desktop()
                print(f"Pairing token (shown once): {token}\nTLS SHA-256 fingerprint: {pin}")
            elif args.desktop_command == "fingerprint":
                print(fingerprint())
            else:
                serve_desktop(args.host, args.port)
        elif args.command == "node":
            if args.node_command == "pair":
                token = getpass.getpass("Desktop pairing token: ")
                save_peer(args.url, args.fingerprint, token)
                print("Paired; token saved to the operating system keyring.")
            elif args.node_command == "shell":
                _shell()
            elif args.node_command == "voice":
                from .voice import VoiceService
                VoiceService(remote=True, muted=args.mute).listen()
            else:
                _run_engine(True, args.text, args.file, args.chat, args.allow_jev)
        elif args.command == "voice":
            from .voice import VoiceService
            VoiceService(muted=args.mute).listen()
        elif args.command == "browser":
            _browser_shell(args.remote)
        elif args.command == "routine":
            if args.routine_command == "list":
                print("\n".join(names()) or "No routines saved.")
            elif args.routine_command == "save":
                print(f"Saved {args.name}: {save(args.name)['action']}")
            else:
                routine = get(args.name)
                engine = Engine(remote=routine["remote"])
                try:
                    print(engine.tool(routine["action"], routine["args"], confirmed=args.confirm).text)
                finally:
                    engine.close()
        elif args.command == "models":
            action = {"install-laya": install_laya, "install-qwen": install_qwen,
                      "install-voice": install_voice, "verify": verify_models}[args.action]
            print(json.dumps(action(), indent=2))
        elif args.command == "key":
            secret = getpass.getpass("Jev API key (hidden): ")
            if not secret:
                raise ValueError("Key cannot be empty")
            set_secret("jev", secret)
            print("Jev key saved in the operating system keyring.")
        elif args.command == "doctor":
            cfg = read_config()
            laya, qwen = model_paths(cfg)
            print(json.dumps({"models": verify_models(), "laya_path": str(laya),
                              "qwen_path": str(qwen), "voice_path": str(voice_model_path(cfg)),
                              "peer_configured": bool(cfg.get("peer")),
                              "cloud_default": "disabled", "runtime": sys.platform}, indent=2))
        elif args.command == "repair":
            from . import repair
            if args.repair_command == "diagnose":
                result = repair.diagnose()
            elif args.repair_command == "stage":
                from pathlib import Path
                result = repair.stage(Path(args.patch).read_text(encoding="utf-8"))
            elif args.repair_command == "propose":
                result = repair.propose(args.error, args.file)
            elif args.repair_command == "verify":
                result = repair.verify(args.id, trusted_run=args.trusted_run)
            elif args.repair_command == "apply":
                result = repair.apply(args.id, approve=args.approve)
            else:
                result = repair.rollback()
            print(json.dumps(result, indent=2))
        elif args.command == "acceptance":
            from .acceptance import check_pi
            result = check_pi(microphone_seconds=args.mic_seconds)
            print(json.dumps(result, indent=2))
            if not result.get("all_requested_passed", False):
                return 1
        else:
            from .ui import launch
            launch()
        return 0
    except (ValueError, RuntimeError, OSError, KeyboardInterrupt) as exc:
        print(f"Kairo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
