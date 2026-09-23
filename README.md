# Kairo: expanded local-first prototype

> **Risk and liability notice:** Kairo is experimental software. Bugs or unexpected behavior could cause data loss, device damage, account or privacy issues, or other harm. It is provided “as is,” and you decide whether to install or use it. No disclaimer can guarantee that an author or contributor cannot be sued or that every liability limit will be enforceable. Review the code and back up important data before running it. See [DISCLAIMER.md](DISCLAIMER.md).

Kairo is a cross-platform assistant prototype built from [SPEC.md](SPEC.md). It supports typed commands, an offline speech path, structured browser actions, local Laya and Qwen adapters, optional Jev decisions, basic routines, a desktop interface, authenticated LAN control, and staged code repair. It is still a prototype; the hardware acceptance tests in the spec have not passed yet.

## What runs now

| Component | State |
| --- | --- |
| macOS / Windows desktop executor | Python file tools and TLS agent, pending native-device checks |
| Raspberry Pi Node | Python ARM64 entry point with local Laya SDK and `llama-server` adapter, pending Pi hardware checks |
| Laya | English checkpoint on disk; local `laya.load(path)` and typed-choice decisions |
| Qwen | Qwen3 0.6B GGUF on disk; local `llama-server` bound to `127.0.0.1` |
| Jev | Official hosted System One endpoint, only via `--allow-jev` with a configured key |
| Routines | Save and replay one verified tool action |
| Voice | Offline Vosk transcription; recognizes “Kairo” or “Cairo” before a command; optional offline TTS |
| Browser | Separate Playwright Chromium profile; URL, visible page text, exact named elements, labeled fields |
| Self-repair | Metadata-only diagnostics, up to three local Qwen patch attempts, staged tests, explicit approval, rollback |

The cloud never substitutes for a missing local model without an explicit `--allow-jev`. Direct commands such as “open Downloads” use rules without model calls.

## Install

Use Python 3.11+ on macOS, Windows or Raspberry Pi OS 64-bit. On each computer:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[edge,voice,browser]'
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`, then run `python -m pip install -e ".[edge,voice,browser]"`. The `edge` extra can pull large PyTorch dependencies. Voice requires a working microphone and PortAudio. Install or build a compatible `llama-server` binary separately using the [llama.cpp build instructions](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Install the browser once on each desktop with `playwright install chromium`. Set `llama_server` to its absolute executable path in `~/.kairo/config.json` if it is not on `PATH` (on Windows, the equivalent is the home directory's `.kairo` folder).

### Download local weights (internet required once)

```bash
kairo models install-laya
kairo models install-qwen
kairo models install-voice
kairo models verify
kairo doctor
```

The Laya and Qwen installers pin each download to the repository revision seen at install time and record a SHA-256 digest. The voice installer downloads the official small English Vosk model. All three read local files thereafter. The Laya SDK is forced into offline mode before loading. Keep several gigabytes of free disk and expect material RAM use; Pi 5 memory, speed, Vosk accuracy for “Kairo,” and ARM64 dependency installation remain unmeasured. The first Qwen model is the official 0.6B Q8 GGUF, which is limited in reasoning ability.

## Run on one computer

```bash
kairo ask "list Downloads"
kairo ask "open my Downloads folder"
kairo ask "summarize this" --file "$HOME/Documents/notes.md"
kairo ask "What does this mean?" --chat
kairo ui
kairo voice
kairo browser
```

The UI has an API-key field backed by the OS keyring. For a headless device with no Secret Service backend, you can supply `KAIRO_JEV_API_KEY` only for commands where you intentionally pass `--allow-jev`. Kairo does not store the key in `config.json`.

The file executor is confined to the home directory, handles `.txt`, `.md`, `.csv` and `.json` files up to 16 KB, and moves files only when `--confirm` is specified:

```bash
kairo tool move_file --source "$HOME/Downloads/notes.md" --destination "$HOME/Documents/notes.md" --confirm
kairo routine save move_my_notes
kairo routine run move_my_notes --confirm
```

A saved move routine uses the original paths and will fail safely after its source moves. Parameterized routines remain a later milestone.

### Voice and browser

`kairo voice` continuously transcribes microphone audio locally. Say “Kairo, open Downloads,” or say “Kairo” and then the command within eight seconds. `kairo node voice` performs the same recognition on the Pi and sends supported desktop actions over the paired LAN connection. Speech synthesis uses a local driver when available. The first wake implementation matches Vosk transcriptions, rather than using a separately trained low-power wake-word model. Say “Kairo, stop” for best-effort cancellation; an action already completed on a computer cannot be undone by the stop command.

`kairo browser` keeps a desktop browser session open for commands `open URL`, `read`, `click ROLE 'Exact name'`, and `fill 'Field label'`. `kairo browser --remote` controls the paired desktop. The GUI has a Browser tab. Clicking and filling require explicit confirmation; form contents and clicks are excluded from routines. This Chromium session uses its own profile, so a site may ask you to sign in there separately. Kairo does not execute page scripts or model-generated shell commands.

## Pair a Pi and a desktop

On the desktop, initialize once and keep the displayed token private:

```bash
kairo desktop init
kairo desktop serve --host 0.0.0.0 --port 18443
```

On the Pi, use the desktop's LAN IP and the SHA-256 fingerprint shown by `desktop init`. The pairing token is entered through a hidden prompt. The Pi checks the certificate fingerprint **before** sending the token. Pairing requires an unlocked OS keyring on the Pi; headless deployments can set `KAIRO_PEER_TOKEN` as a process credential instead and configure `peer.url` and `peer.fingerprint` in `~/.kairo/config.json` manually.

```bash
kairo node pair --url https://DESKTOP_LAN_IP:18443 --fingerprint FINGERPRINT_FROM_DESKTOP
kairo node ask "list Downloads"
kairo node ask "summarize this file" --file /home/desktop-user/Documents/notes.md
kairo node shell
kairo node voice
kairo browser --remote
```

`kairo node shell` loads Laya and Qwen once and keeps both resident while accepting typed requests. The Pi calls the paired computer over LAN for file actions, and local Qwen summarizes returned text. Opening the desktop port should be limited to a trusted LAN or firewall zone. The client has a strict fingerprint pin; loss or rotation of the desktop certificate requires re-pairing. Neither models nor API keys travel through the desktop protocol.

## Diagnostics and staged self-repair

```bash
kairo repair diagnose
kairo repair propose --file kairo/voice.py --error "short error description"
kairo repair stage candidate.patch
kairo repair verify CANDIDATE_ID
kairo repair apply CANDIDATE_ID --approve
kairo repair rollback
```

`propose` asks local Qwen for a minimal unified diff and stops after three invalid attempts. `stage` accepts a supplied diff. Only `kairo/voice.py`, `kairo/providers.py`, and `kairo/ui.py` can be modified through this path; authentication, permission checks, remote control, audit, and rollback code are protected. The candidate remains separate from the running installation. Verification parses changed Python, then runs tests without network in Linux bubblewrap where that sandbox is available. On a computer without bubblewrap, `verify --trusted-run` explicitly runs candidate tests with the current user's privileges. An unverified candidate cannot be applied. `apply --approve` saves original files for rollback and refuses to overwrite source that changed since staging. The action journal records only tool names, timings, success, and exception types.

This code-repair flow does not automatically deploy model-generated patches or prove that a patch is safe beyond the checks it ran. Do not promote a candidate without reading its stored `proposal.patch` and test output.

## Acceptance status

`python -m unittest discover -s tests -v` covers file permissions, LAN pairing, mocked local model APIs, voice dispatch, browser session behavior, candidate repair, and rollback. The development environment lacks model weights, a microphone, Chromium, a Raspberry Pi, Windows, and macOS. The Linux bubblewrap test sandbox also could not start here because the container denied its network namespace operation; Kairo records that as unavailable. Real microphone, browser, and offline Pi checks remain open. A claim of full offline Pi operation requires:

1. Download all three weights; run `kairo models verify`.
2. Disconnect Pi from the internet, leave LAN connected, run `kairo node shell` and `kairo node voice`.
3. Ask a previously unseen intent requiring Laya; observe `[Laya LOCAL]`.
4. Ask `kairo node ask "summarize this" --file DESKTOP_TEXT_PATH`; observe `[rule → Qwen; LOCAL on Kairo Node]` and verify no external network requests.
5. Speak “Kairo, open Downloads” into a real Pi microphone and confirm the desktop action and audible or printed result.
6. Benchmark load time, RAM, temperatures, Laya latency, Qwen tokens/sec and end-to-end action latency on Pi 5. Test the browser separately on the actual Windows and macOS desktops.

# Kairo: expanded local-first prototype

> **Risk and liability notice:** Kairo is experimental software. Bugs or unexpected behavior could cause data loss, device damage, account or privacy issues, or other harm. It is provided “as is,” and you decide whether to install or use it. No disclaimer can guarantee that an author or contributor cannot be sued or that every liability limit will be enforceable. Review the code and back up important data before running it. See [DISCLAIMER.md](DISCLAIMER.md).

Kairo is a cross-platform assistant prototype built from [SPEC.md](SPEC.md). It supports typed commands, an offline speech path, structured browser actions, local Laya and Qwen adapters, optional Jev decisions, basic routines, a desktop interface, authenticated LAN control, and staged code repair. It is still a prototype; the hardware acceptance tests in the spec have not passed yet.

## What runs now

| Component | State |
| --- | --- |
| macOS / Windows desktop executor | Python file tools and TLS agent, pending native-device checks |
| Raspberry Pi Node | Python ARM64 entry point with local Laya SDK and `llama-server` adapter, pending Pi hardware checks |
| Laya | English checkpoint on disk; local `laya.load(path)` and typed-choice decisions |
| Qwen | Qwen3 0.6B GGUF on disk; local `llama-server` bound to `127.0.0.1` |
| Jev | Official hosted System One endpoint, only via `--allow-jev` with a configured key |
| Routines | Save and replay one verified tool action |
| Voice | Offline Vosk transcription; recognizes “Kairo” or “Cairo” before a command; optional offline TTS |
| Browser | Separate Playwright Chromium profile; URL, visible page text, exact named elements, labeled fields |
| Self-repair | Metadata-only diagnostics, up to three local Qwen patch attempts, staged tests, explicit approval, rollback |

The cloud never substitutes for a missing local model without an explicit `--allow-jev`. Direct commands such as “open Downloads” use rules without model calls.

## Install

Use Python 3.11+ on macOS, Windows or Raspberry Pi OS 64-bit. On each computer:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[edge,voice,browser]'
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`, then run `python -m pip install -e ".[edge,voice,browser]"`. The `edge` extra can pull large PyTorch dependencies. Voice requires a working microphone and PortAudio. Install or build a compatible `llama-server` binary separately using the [llama.cpp build instructions](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Install the browser once on each desktop with `playwright install chromium`. Set `llama_server` to its absolute executable path in `~/.kairo/config.json` if it is not on `PATH` (on Windows, the equivalent is the home directory's `.kairo` folder).

### Download local weights (internet required once)

```bash
kairo models install-laya
kairo models install-qwen
kairo models install-voice
kairo models verify
kairo doctor
```

The Laya and Qwen installers pin each download to the repository revision seen at install time and record a SHA-256 digest. The voice installer downloads the official small English Vosk model. All three read local files thereafter. The Laya SDK is forced into offline mode before loading. Keep several gigabytes of free disk and expect material RAM use; Pi 5 memory, speed, Vosk accuracy for “Kairo,” and ARM64 dependency installation remain unmeasured. The first Qwen model is the official 0.6B Q8 GGUF, which is limited in reasoning ability.

## Run on one computer

```bash
kairo ask "list Downloads"
kairo ask "open my Downloads folder"
kairo ask "summarize this" --file "$HOME/Documents/notes.md"
kairo ask "What does this mean?" --chat
kairo ui
kairo voice
kairo browser
```

The UI has an API-key field backed by the OS keyring. For a headless device with no Secret Service backend, you can supply `KAIRO_JEV_API_KEY` only for commands where you intentionally pass `--allow-jev`. Kairo does not store the key in `config.json`.

The file executor is confined to the home directory, handles `.txt`, `.md`, `.csv` and `.json` files up to 16 KB, and moves files only when `--confirm` is specified:

```bash
kairo tool move_file --source "$HOME/Downloads/notes.md" --destination "$HOME/Documents/notes.md" --confirm
kairo routine save move_my_notes
kairo routine run move_my_notes --confirm
```

A saved move routine uses the original paths and will fail safely after its source moves. Parameterized routines remain a later milestone.

### Voice and browser

`kairo voice` continuously transcribes microphone audio locally. Say “Kairo, open Downloads,” or say “Kairo” and then the command within eight seconds. `kairo node voice` performs the same recognition on the Pi and sends supported desktop actions over the paired LAN connection. Speech synthesis uses a local driver when available. The first wake implementation matches Vosk transcriptions, rather than using a separately trained low-power wake-word model. Say “Kairo, stop” for best-effort cancellation; an action already completed on a computer cannot be undone by the stop command.

`kairo browser` keeps a desktop browser session open for commands `open URL`, `read`, `click ROLE 'Exact name'`, and `fill 'Field label'`. `kairo browser --remote` controls the paired desktop. The GUI has a Browser tab. Clicking and filling require explicit confirmation; form contents and clicks are excluded from routines. This Chromium session uses its own profile, so a site may ask you to sign in there separately. Kairo does not execute page scripts or model-generated shell commands.

## Pair a Pi and a desktop

On the desktop, initialize once and keep the displayed token private:

```bash
kairo desktop init
kairo desktop serve --host 0.0.0.0 --port 18443
```

On the Pi, use the desktop's LAN IP and the SHA-256 fingerprint shown by `desktop init`. The pairing token is entered through a hidden prompt. The Pi checks the certificate fingerprint **before** sending the token. Pairing requires an unlocked OS keyring on the Pi; headless deployments can set `KAIRO_PEER_TOKEN` as a process credential instead and configure `peer.url` and `peer.fingerprint` in `~/.kairo/config.json` manually.

```bash
kairo node pair --url https://DESKTOP_LAN_IP:18443 --fingerprint FINGERPRINT_FROM_DESKTOP
kairo node ask "list Downloads"
kairo node ask "summarize this file" --file /home/desktop-user/Documents/notes.md
kairo node shell
kairo node voice
kairo browser --remote
```

`kairo node shell` loads Laya and Qwen once and keeps both resident while accepting typed requests. The Pi calls the paired computer over LAN for file actions, and local Qwen summarizes returned text. Opening the desktop port should be limited to a trusted LAN or firewall zone. The client has a strict fingerprint pin; loss or rotation of the desktop certificate requires re-pairing. Neither models nor API keys travel through the desktop protocol.

## Diagnostics and staged self-repair

```bash
kairo repair diagnose
kairo repair propose --file kairo/voice.py --error "short error description"
kairo repair stage candidate.patch
kairo repair verify CANDIDATE_ID
kairo repair apply CANDIDATE_ID --approve
kairo repair rollback
```

`propose` asks local Qwen for a minimal unified diff and stops after three invalid attempts. `stage` accepts a supplied diff. Only `kairo/voice.py`, `kairo/providers.py`, and `kairo/ui.py` can be modified through this path; authentication, permission checks, remote control, audit, and rollback code are protected. The candidate remains separate from the running installation. Verification parses changed Python, then runs tests without network in Linux bubblewrap where that sandbox is available. On a computer without bubblewrap, `verify --trusted-run` explicitly runs candidate tests with the current user's privileges. An unverified candidate cannot be applied. `apply --approve` saves original files for rollback and refuses to overwrite source that changed since staging. The action journal records only tool names, timings, success, and exception types.

This code-repair flow does not automatically deploy model-generated patches or prove that a patch is safe beyond the checks it ran. Do not promote a candidate without reading its stored `proposal.patch` and test output.

## Acceptance status

`python -m unittest discover -s tests -v` covers file permissions, LAN pairing, mocked local model APIs, voice dispatch, browser session behavior, candidate repair, and rollback. The development environment lacks model weights, a microphone, Chromium, a Raspberry Pi, Windows, and macOS. The Linux bubblewrap test sandbox also could not start here because the container denied its network namespace operation; Kairo records that as unavailable. Real microphone, browser, and offline Pi checks remain open. A claim of full offline Pi operation requires:

1. Download all three weights; run `kairo models verify`.
2. Disconnect Pi from the internet, leave LAN connected, run `kairo node shell` and `kairo node voice`.
3. Ask a previously unseen intent requiring Laya; observe `[Laya LOCAL]`.
4. Ask `kairo node ask "summarize this" --file DESKTOP_TEXT_PATH`; observe `[rule → Qwen; LOCAL on Kairo Node]` and verify no external network requests.
5. Speak “Kairo, open Downloads” into a real Pi microphone and confirm the desktop action and audible or printed result.
6. Benchmark load time, RAM, temperatures, Laya latency, Qwen tokens/sec and end-to-end action latency on Pi 5. Test the browser separately on the actual Windows and macOS desktops.

The on-device check `kairo acceptance pi --mic-seconds 8` probes ARM64 Pi hardware, local Laya and Qwen, a paired desktop, a short spoken “Kairo” sample, free RAM, and CPU temperature. Run it after disconnecting internet access while keeping the LAN active. It saves a JSON result under the Pi's `.kairo/acceptance` directory. It does not itself prove that all network egress was blocked, and it does not yet calculate Qwen tokens per second.

If a model cannot load or memory is insufficient, Kairo reports an error and does not claim that a cloud response was local.

## Remaining engineering work

Add native Windows/macOS application APIs, a dedicated wake model with measured false-positive rates, parameterized routines, rich browser navigation and verification, model memory policies, supervised background services, real Pi benchmarks, OS installers, and an isolated build environment for repair checks on macOS and Windows. Current tools deliberately have no arbitrary model-driven shell execution.

## Primary integration references

- [Laya upstream model card](https://huggingface.co/convaiinnovations/laya) and [Python SDK](https://github.com/NandhaKishorM/laya)
- [Official Qwen3 0.6B GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF)
- [llama.cpp server API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [TypeSafe Jev API](https://docs.typesafe.ai/api)
- [Vosk offline models and microphone example](https://alphacephei.com/vosk/models)
- [Playwright Python locators](https://playwright.dev/python/docs/locators)
- [Bubblewrap sandbox](https://github.com/containers/bubblewrap)
The on-device check `kairo acceptance pi --mic-seconds 8` probes ARM64 Pi hardware, local Laya and Qwen, a paired desktop, a short spoken “Kairo” sample, free RAM, and CPU temperature. Run it after disconnecting internet access while keeping the LAN active. It saves a JSON result under the Pi's `.kairo/acceptance` directory. It does not itself prove that all network egress was blocked, and it does not yet calculate Qwen tokens per second.

If a model cannot load or memory is insufficient, Kairo reports an error and does not claim that a cloud response was local.

## Remaining engineering work

Add native Windows/macOS application APIs, a dedicated wake model with measured false-positive rates, parameterized routines, rich browser navigation and verification, model memory policies, supervised background services, real Pi benchmarks, OS installers, and an isolated build environment for repair checks on macOS and Windows. Current tools deliberately have no arbitrary model-driven shell execution.

## Primary integration references

- [Laya upstream model card](https://huggingface.co/convaiinnovations/laya) and [Python SDK](https://github.com/NandhaKishorM/laya)
- [Official Qwen3 0.6B GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF)
- [llama.cpp server API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [TypeSafe Jev API](https://docs.typesafe.ai/api)
- [Vosk offline models and microphone example](https://alphacephei.com/vosk/models)
- [Playwright Python locators](https://playwright.dev/python/docs/locators)
- [Bubblewrap sandbox](https://github.com/containers/bubblewrap)
