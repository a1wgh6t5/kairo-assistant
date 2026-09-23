# KAIRO — MASTER BUILD SPECIFICATION

Build a real, production-oriented, cross-platform AI computer assistant named **Kairo**.

Kairo is not primarily a chatbot.

Kairo is an **AI operating agent** designed to control, automate, organize, and interact with a user's own computers and connected devices through natural language and voice.

The long-term goal is to create an assistant that behaves like an intelligent operating layer rather than a conventional AI chat application.

---

# ABSOLUTE NON-NEGOTIABLE REQUIREMENTS

These requirements must influence the architecture from the beginning.

Kairo must:

1. Run on Windows.
2. Run on macOS.
3. Include a Raspberry Pi / ARM64 Linux runtime called **Kairo Node**.
4. Allow API keys for cloud AI providers.
5. Allow Jev API integration.
6. **Run Laya LOCALLY on the Raspberry Pi.**
7. **Run a Qwen language model LOCALLY on the Raspberry Pi.**
8. Allow Laya and Qwen to remain loaded/warm for low-latency requests when resources permit.
9. Allow cloud models as optional fallbacks rather than mandatory dependencies.
10. Continue performing basic AI routing and supported local reasoning if the Raspberry Pi loses internet access.
11. Control paired Windows/macOS computers from the Raspberry Pi.
12. Support voice activation using the wake word **"Kairo."**
13. Learn deterministic routines from previously successful workflows.
14. Be capable of controlled self-diagnosis and self-repair.
15. Use strong safety boundaries around destructive, privileged, financial, credential, and security-sensitive actions.
16. Prefer direct APIs and native tools over simulated mouse movement.
17. Be optimized aggressively for latency.

## IMPORTANT: LOCAL MEANS LOCAL

Do not falsely implement local AI by forwarding requests to a remote API.

When Kairo is configured for local mode:

```text
Laya inference
=
performed on the Raspberry Pi itself

Qwen inference
=
performed on the Raspberry Pi itself

```

The application may download model weights during installation.

After the required models are downloaded, Kairo must be capable of using those models without an internet connection.

Cloud providers may improve capabilities, but **local Laya and local Qwen must actually work without them**.

---

# 1. CORE PRODUCT CONCEPT

The user should eventually be able to say:

> "Kairo."

The nearest Kairo device activates.

User:

> "Take the PDF I just downloaded, rename it using the actual paper title, move it into my research folder, and open it."

Kairo determines the necessary actions, executes them on the appropriate computer, verifies their success, and responds:

> "Done."

The user can then say:

> "Make that a routine."

Kairo converts the successful execution into a reusable workflow.

Next time, Kairo should avoid unnecessary LLM calls and use that workflow directly.

Kairo should become:

- faster with repeated usage
- cheaper with repeated usage
- more deterministic with repeated usage
- more reliable with repeated usage
- less dependent on cloud AI over time

---

# 2. KAIRO IS AN AGENT, NOT JUST A CHATBOT

Do not make the primary architecture:

```text
user
↓
LLM
↓
text answer

```

Kairo should instead work approximately like:

```text
USER
 ↓
VOICE / TEXT
 ↓
INPUT PROCESSOR
 ↓
FAST INTENT ROUTER
 ↓
ROUTINE MATCHER
 ↓
MODEL ROUTER
 ↓
TASK PLANNER
 ↓
TOOLS
 ↓
OPERATING SYSTEM / DEVICE
 ↓
VERIFICATION
 ↓
RESPONSE

```

The AI exists to understand intentions and create plans.

Deterministic software should execute computer actions whenever possible.

---

# 3. HIGH-LEVEL ARCHITECTURE

Use modular components.

```text
                         USER
                           │
                      Voice / Text
                           │
                           ▼
                 ┌───────────────────┐
                 │  INPUT PROCESSOR  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │  INTENT ROUTER    │
                 └─────────┬─────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
 Local Rules         Routine Engine        AI Router
                                               │
                         ┌─────────────────────┼──────────────────┐
                         ▼                     ▼                  ▼
                     Laya Local             Qwen Local          Jev API
                         │                     │                  │
                         └──────────────┬──────┴───────────────┬──┘
                                        │                      │
                                        ▼                      ▼
                                  Fast Cloud LLM        Reasoning LLM
                                        │                      │
                                        └──────────┬───────────┘
                                                   ▼
                                            TASK PLANNER
                                                   │
                                                   ▼
                                            TOOL REGISTRY
                                                   │
                           ┌───────────────────────┼─────────────────────┐
                           ▼                       ▼                     ▼
                       Windows                  macOS                 Linux
                       Executor                Executor              Executor
                           │                       │                     │
                           └───────────────────────┼─────────────────────┘
                                                   ▼
                                                VERIFY
                                                   │
                                                   ▼
                                               RESPONSE

```

---

# 4. SPEED IS THE PRIMARY DESIGN REQUIREMENT

Kairo should feel immediate.

Do not route every command through Qwen.

Do not route every command through a cloud LLM.

Do not route every command through Jev.

Do not route every command through Laya.

Use the cheapest and fastest correct path.

Preferred hierarchy:

```text
1. Direct deterministic command
2. Existing routine
3. Local rule
4. Cached resolution
5. Local Laya decision
6. Local Qwen
7. Jev API
8. Fast cloud LLM
9. Powerful reasoning model

```

The exact order may change depending on configuration, latency, confidence, privacy, and resource availability.

---

# 5. EXAMPLE OF FAST EXECUTION

Command:

> "Kairo, volume 30%."

Wrong:

```text
speech
↓
large LLM
↓
generate plan
↓
system tool

```

Correct:

```text
speech
↓
local intent classification
↓
set_volume(30)

```

Command:

> "Kairo, open Spotify."

Correct:

```text
wake word
↓
intent
↓
open_application("Spotify")
↓
verify process

```

No large language model should be required.

---

# 6. RASPBERRY PI IS A FIRST-CLASS PLATFORM

Create a runtime called:

# Kairo Node

The primary hardware target should be:

```text
Raspberry Pi 5
ARM64 Linux

```

Do not treat Raspberry Pi support as a future placeholder.

The initial architecture must be capable of supporting it.

Kairo Node should be able to function as:

```text
always-on assistant
wake-word processor
microphone interface
speaker interface
local Laya inference server
local Qwen inference server
routine engine
model router
memory service
device coordinator
desktop-control gateway
automation server

```

---

# 7. HARD REQUIREMENT — LAYA MUST RUN ON THE RASPBERRY PI

This is mandatory.

Kairo Node must support a real local installation of Laya.

Laya should function as a lightweight System-1 decision engine.

Its primary roles include:

```text
intent classification
tool selection
routine selection
risk classification
escalation decisions
model selection
confidence estimation
yes/no decisions
choice decisions
scoring decisions

```

Laya should not be treated as a text-generating chatbot.

---

# 8. LAYA LOCAL SERVICE

Implement Laya behind a reusable local service.

Conceptually:

```text
Kairo Core
   │
   ▼
Local Laya Service
   │
   ▼
Laya model weights
   │
   ▼
Raspberry Pi CPU / supported accelerator

```

Possible runtime approaches may include:

```text
Python inference
ONNX Runtime
another tested ARM64-compatible runtime

```

Do not tightly couple Kairo Core to one Laya runtime.

Create an abstraction:

```python
class DecisionProvider:
    async def choose(...)
    async def score(...)
    async def binary_decision(...)
    async def health_check(...)

```

Then implementations may include:

```text
LayaLocalProvider
JevCloudProvider
LLMFallbackProvider

```

---

# 9. LAYA SHOULD STAY WARM

Cold-loading models for every request would damage the Kairo experience.

When RAM permits:

```text
Kairo Node starts
↓
Laya loads
↓
Laya remains resident
↓
requests are processed immediately

```

Provide configuration:

```text
Laya

[x] Load at startup
[x] Keep model resident
[ ] Unload during memory pressure

```

Kairo's resource manager may unload it if absolutely necessary.

---

# 10. HARD REQUIREMENT — QWEN MUST RUN LOCALLY ON THE RASPBERRY PI

This is also mandatory.

Kairo Node must support running an actual Qwen language model locally.

Do not implement:

```text
"Qwen Local"
↓
hidden cloud request

```

Actual architecture:

```text
Raspberry Pi
     │
     ▼
local Qwen runtime
     │
     ▼
local Qwen model weights
     │
     ▼
response generated on Raspberry Pi

```

---

# 11. QWEN MODEL SIZE MUST BE HARDWARE-AWARE

Do not hard-code one enormous Qwen checkpoint.

The installer should detect:

```text
RAM
available storage
CPU architecture
thermal state
accelerator availability

```

Then recommend an appropriate Qwen checkpoint and quantization.

Conceptually:

```text
low-memory Pi
→ smallest supported Qwen model

medium-memory Pi
→ larger lightweight Qwen

16 GB Pi
→ larger model where practical

accelerated Pi
→ accelerator-compatible model where practical

```

Users should still be able to override the recommendation.

---

# 12. QUANTIZED QWEN SUPPORT

Kairo should support memory-efficient Qwen inference.

Prefer established formats and inference runtimes suited for local edge deployment.

For example:

```text
GGUF / quantized model
        ↓
ARM64-compatible inference runtime
        ↓
QwenLocalProvider

```

The exact quantization should be configurable.

Example settings:

```text
Qwen Local

Model:
Qwen ________

Quantization:
Automatic ▼

Context:
Automatic ▼

Threads:
Automatic ▼

Keep Loaded:
Yes

Memory Limit:
Automatic

```

---

# 13. QWEN LOCAL SERVER

Do not make every component load Qwen separately.

Expose one local inference service.

```text
                    ┌───────────────────┐
                    │ Qwen Local Server │
                    └─────────┬─────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
       Kairo Voice       Task Planner      Self Repair

```

Possible interface:

```text
localhost-only HTTP
Unix socket
gRPC

```

Do not expose it unauthenticated to the public network.

---

# 14. LOCAL MODEL MANAGER

Create a real model-management component.

Example:

```text
Settings
→ Local Models

Laya
Status: Installed
RAM: ...
Runtime: ...
[Load]
[Unload]
[Update]

Qwen
Status: Installed
Model: ...
Quantization: ...
RAM: ...
[Load]
[Unload]
[Change Model]

```

Model Manager responsibilities:

```text
download models
verify checksums
manage versions
manage storage
load models
unload models
report memory usage
report latency
detect corrupt downloads

```

---

# 15. LOCAL AI HEALTH CHECK

Provide diagnostics.

Example:

```text
Local AI Diagnostic

Laya:
PASS
17 ms

Qwen:
PASS
8.2 tokens/sec

Wake word:
PASS

Speech:
PASS

Internet:
Not required

Local Mode:
READY

```

---

# 16. OFFLINE ACCEPTANCE TEST

This is mandatory.

After required models have been installed:

```text
DISCONNECT INTERNET

```

Kairo Node must still be capable of performing tests such as:

> "Kairo, should this command open an application or manipulate a file?"

using local Laya.

And:

> "Kairo, explain what this local text file contains."

using local Qwen.

And:

> "Kairo, open Downloads on my connected computer."

using:

```text
local voice/input
+
local routing
+
local network connection to computer
+
desktop executor

```

If Kairo cannot do these after internet access is disabled, local Raspberry Pi AI support is incomplete.

---

# 17. HYBRID MODE

The recommended architecture should also support:

```text
Laya
LOCAL

Qwen
LOCAL

Jev
CLOUD OPTIONAL

Fast LLM
CLOUD OPTIONAL

Reasoning LLM
CLOUD OPTIONAL

```

This provides both local capability and stronger cloud escalation.

---

# 18. PROCESSING MODES

Provide profiles.

## FASTEST

Favor the fastest available execution regardless of local/cloud location.

## LOCAL FIRST

```text
rules
↓
routines
↓
Laya
↓
Qwen
↓
cloud only if needed

```

## CLOUD FIRST

Use cloud models where they meaningfully reduce latency.

## LOWEST COST

Prefer:

```text
rules
routines
Laya
Qwen

```

before paid APIs.

## MAXIMUM PRIVACY

Avoid uploading files/screenshots/content whenever possible.

## OFFLINE

Disable all cloud providers.

Use:

```text
rules
routines
Laya
Qwen
local tools

```

---

# 19. MODEL ROUTER

Create a central Model Router.

Example:

```python
route_request(request, context, resources)

```

The router considers:

```text
task
latency
confidence
privacy
internet
API price
RAM
CPU
model availability
device availability
user preference

```

---

# 20. MODEL PROVIDER ABSTRACTION

Support providers such as:

```text
Laya local
Qwen local
Jev
OpenAI
Anthropic
Google
OpenRouter
Groq
custom OpenAI-compatible APIs
custom HTTP inference server

```

Do not hardcode Kairo around a single AI company.

---

# 21. API KEY SETTINGS

Users must be able to enter API keys through Kairo.

Example:

```text
Settings
→ AI Providers

Jev
API Key: •••••••••••
[Test]

OpenAI
API Key: •••••••••••
[Test]

Anthropic
API Key: •••••••••••
[Test]

Google
API Key: •••••••••••
[Test]

OpenRouter
API Key: •••••••••••
[Test]

```

---

# 22. SECURE CREDENTIAL STORAGE

Never store keys in plaintext settings.

Use:

```text
macOS
→ Keychain

Windows
→ Credential Manager / DPAPI-backed storage

Linux
→ Secret Service / secure keyring

```

Never write API keys into logs.

---

# 23. LOCAL MODEL REQUEST EXAMPLE

User:

> "Kairo, open my newest PDF."

Possible processing:

```text
voice
↓
local speech
↓
Laya
↓
intent = file operation
↓
find_file
↓
open_file

```

Qwen unnecessary.

---

# 24. LOCAL QWEN REQUEST EXAMPLE

User:

> "Kairo, look at these filenames and figure out which one is probably my economics essay."

Possible:

```text
local file listing
↓
Qwen local
↓
selection
↓
open file

```

No cloud API required.

---

# 25. ESCALATION EXAMPLE

User:

> "Research these six companies, compare their financial statements, find recent information online, and create a report."

Possible:

```text
Laya
↓
complex task detected
↓
Qwen determines cloud escalation useful
↓
reasoning model
↓
tools

```

The expensive model is used because it is justified.

---

# 26. WINDOWS + MAC CONTROL

Desktop clients must exist for:

```text
Windows
macOS

```

Kairo Node should be able to control either.

Use a universal action schema.

Example:

```json
{
  "tool": "move_file",
  "arguments": {
    "source": "...",
    "destination": "..."
  }
}

```

---

# 27. PLATFORM EXECUTORS

Translate universal actions into native implementations.

Windows may use:

```text
filesystem APIs
PowerShell
Windows APIs
UI Automation
COM
browser automation

```

macOS may use:

```text
filesystem APIs
AppleScript
JXA
Accessibility APIs
Shortcuts
shell
browser automation

```

Prefer direct APIs.

---

# 28. TOOL REGISTRY

Each tool must specify:

```text
name
description
input schema
output schema
platforms
risk level
permissions
verification
undo support

```

Examples:

```text
open_application
close_application
find_file
open_file
move_file
copy_file
rename_file
create_folder
trash_file
restore_file
open_url
download_file
set_volume
media_control
take_screenshot
read_clipboard
write_clipboard
browser_navigate
browser_click
browser_type
get_system_status

```

---

# 29. LLM OUTPUT MUST NEVER DIRECTLY CONTROL THE COMPUTER

LLM-generated natural language is untrusted.

Correct architecture:

```text
LLM
↓
structured action proposal
↓
schema validation
↓
permission check
↓
Tool Registry
↓
executor

```

Not:

```text
LLM
↓
arbitrary shell command
↓
run immediately

```

---

# 30. EXECUTION GRAPH

Complex tasks should become graphs.

Example:

```text
Find newest PDF
        ↓
Read metadata
        ↓
Determine paper title
        ↓
Rename
        ↓
Move
        ↓
Open
        ↓
Verify

```

Each node records:

```text
status
duration
tool
device
model
inputs
outputs
errors
retries
cost

```

---

# 31. VERIFY EVERYTHING IMPORTANT

Use:

```text
PLAN
 ↓
EXECUTE
 ↓
VERIFY
 ↓
SUCCESS?
 ↙     ↘
YES     NO
 ↓       ↓
DONE   DIAGNOSE
        ↓
      RETRY

```

Default retries:

```text
3

```

Never recurse forever.

---

# 32. ROUTINES

Support:

> "Make that a routine."

> "Remember how you did that."

> "Whenever I say research mode, do that."

> "Save those steps."

Kairo converts successful actions into reusable deterministic workflows.

---

# 33. PARAMETERIZED ROUTINES

Do not merely record mouse coordinates.

Bad:

```text
click x=824 y=411

```

Better:

```yaml
name: organize_latest_pdf

steps:
  - find_file:
      folder: Downloads
      extension: .pdf
      newest: true

  - move_file:
      source: ${previous.file}
      destination: ${destination}

```

---

# 34. ROUTINES SHOULD REDUCE AI USAGE

Initial:

```text
User
↓
Qwen / cloud LLM
↓
tools

```

After learning:

```text
User
↓
Laya routine match
↓
routine
↓
tools

```

Eventually common actions should involve almost no generative AI.

---

# 35. VOICE

Wake word:

# Kairo

Architecture:

```text
always-on wake word
↓
streaming microphone
↓
speech recognition
↓
intent routing
↓
execution
↓
speech response

```

The wake-word engine should remain lightweight.

---

# 36. STREAMING

Use streaming wherever possible.

```text
audio
↓
partial transcript
↓
early intent prediction
↓
prepare tools/models
↓
final transcript
↓
execute

```

Do not unnecessarily wait for every stage sequentially.

---

# 37. PREWARMING

Keep lightweight critical components ready:

```text
wake-word engine
Laya
routine matcher
Tool Registry
device registry

```

Optionally keep Qwen resident depending on available RAM.

---

# 38. RESOURCE MANAGER

Monitor:

```text
RAM
CPU
temperature
storage
battery
network
local-model memory

```

If memory becomes constrained:

```text
preserve Laya where possible
↓
unload Qwen if needed
↓
use cloud Qwen/LLM fallback if allowed

```

When resources recover:

```text
reload Qwen

```

---

# 39. DISTRIBUTED COMPUTE

Kairo may use different devices for different jobs.

Example:

```text
Wake word
→ Raspberry Pi

Laya
→ Raspberry Pi

Qwen
→ Raspberry Pi

large vision
→ desktop GPU

large reasoning
→ cloud

file operation
→ Windows computer

speech response
→ Raspberry Pi

```

---

# 40. DEVICE DISCOVERY

Every Kairo installation reports capabilities.

Example:

```json
{
  "device": "Main-PC",
  "os": "windows",
  "ram_gb": 32,
  "capabilities": [
    "filesystem",
    "browser",
    "desktop_control",
    "gpu_inference"
  ]
}

```

Kairo Node:

```json
{
  "device": "Kairo-Node",
  "os": "linux-arm64",
  "capabilities": [
    "wake_word",
    "microphone",
    "speaker",
    "laya_local",
    "qwen_local",
    "routine_engine"
  ]
}

```

---

# 41. DEVICE PAIRING

Never allow unauthenticated LAN control.

Desktop:

```text
Pair Kairo Node

Code:
493 284

```

Pi:

```text
Enter code:
493 284

```

Then establish secure credentials.

Future traffic should be encrypted and authenticated.

---

# 42. KAIRO NODE CONTROL PATH

Example:

> "Kairo, open Spotify on my computer."

```text
Pi microphone
↓
local STT
↓
local Laya
↓
open_application intent
↓
authenticated LAN connection
↓
Windows Kairo Agent
↓
open_application("Spotify")
↓
verify
↓
Pi speaker
↓
"Done."

```

---

# 43. LOCAL NETWORK PERFORMANCE

For paired computers on the same LAN, avoid unnecessary cloud round trips.

The Pi should communicate directly with the desktop.

Target:

```text
Pi
↔
PC

```

not:

```text
Pi
→ internet server
→ internet server
→ PC

```

unless required.

---

# 44. OPTIONAL PHYSICAL KAIRO DEVICE

Support hardware such as:

```text
Raspberry Pi 5
microphone array
speaker
status LED
optional display
optional camera
optional AI accelerator
physical action button
physical microphone kill switch

```

---

# 45. SELF-DIAGNOSIS

Collect structured errors.

Examples:

```text
tool failure
permission failure
API failure
Laya failure
Qwen failure
model crash
timeout
network outage
high latency
memory pressure
routine failure

```

---

# 46. SELF-REPAIR

Kairo may diagnose and improve its own code.

But never edit the active production installation blindly.

Use:

```text
detect problem
↓
inspect diagnostics
↓
inspect source
↓
generate patch
↓
temporary Git branch/worktree
↓
apply patch
↓
lint
↓
build
↓
unit tests
↓
integration tests
↓
benchmark
↓
candidate build

```

---

# 47. SELF-REPAIR MUST SUPPORT LOCAL QWEN

When appropriate, the local Qwen model should be able to participate in:

```text
log summarization
simple code diagnosis
config repair suggestions
error explanation

```

For difficult programming tasks, a configured cloud coding model may be used.

This ensures self-diagnosis still has some functionality offline.

---

# 48. PROTECTED COMPONENTS

Do not allow unattended self-modification of:

```text
authentication
permission engine
credential vault
remote-control security
audit log protection
self-modification authorization
update verification
rollback system
sandbox

```

Kairo may propose patches but must require explicit approval.

---

# 49. VERSIONING

Maintain:

```text
active
candidate
last-known-good
previous

```

Support:

> "Kairo, undo your last update."

---

# 50. SELF-BENCHMARKING

Measure:

```text
wake latency
STT latency
Laya latency
Qwen first-token latency
Qwen tokens/sec
tool latency
end-to-end latency
RAM
CPU
temperature
API cost
success rate

```

---

# 51. LOCAL MODEL PERFORMANCE DASHBOARD

Example:

```text
LOCAL AI

Laya
Loaded
Average latency: 24 ms
RAM: ___

Qwen
Loaded
Model: ___
Quantization: ___
First token: ___
Generation: ___ tok/s
RAM: ___

```

---

# 52. COST TRACKING

Track cloud use separately.

Example:

```text
TODAY

Local Laya decisions:
1,482

Local Qwen requests:
127

Jev requests:
42

Cloud fast LLM:
17

Cloud reasoning:
3

Routine executions:
611

Estimated cost:
$0.09

```

---

# 53. COST OPTIMIZATION

Kairo should identify commands that unnecessarily use APIs.

Example:

```text
This command has been sent to Qwen 31 times.

It can be converted to a deterministic routine.

Convert?

```

---

# 54. MEMORY

Separate:

```text
session memory
operational memory
routine memory
device memory
preference memory
semantic memory

```

Do not send the entire memory database into Qwen or cloud LLMs.

Retrieve only relevant context.

---

# 55. LOCAL DATA INDEX

Optionally maintain lightweight indexes of:

```text
applications
folders
recent files
routine names
recent documents

```

This enables fast semantic commands without full-disk searching.

---

# 56. SECURITY LEVELS

Example:

```text
LOW
open app
search file
read folder
volume control

MEDIUM
move
rename
download
create folder

HIGH
delete
install application
send communication
submit external form

CRITICAL
financial transaction
credential handling
security settings
administrator/root
mass deletion

```

Confirmation requirements should correspond to risk.

---

# 57. UNDO

Maintain transaction metadata for undoable operations.

Support:

> "Kairo, undo that."

Examples:

```text
file move
rename
folder creation
routine modification
some configuration changes

```

---

# 58. BROWSER CONTROL

Prefer structured browser automation.

Support:

```text
navigate
read DOM/accessibility tree
click
type
upload
download
switch tab
close tab
extract text

```

Visual control should be fallback behavior.

---

# 59. VISUAL CONTROL

When no structured interface exists:

```text
screenshot
↓
vision
↓
locate UI target
↓
mouse/keyboard
↓
screenshot
↓
verify

```

---

# 60. SYSTEM TRAY / MENU BAR

Kairo should normally run in the background.

Controls:

```text
Open Kairo
Activate
Mute
Pause automation
Devices
Local Models
Settings
Quit

```

---

# 61. USER INTERFACE

Sidebar:

```text
Home
Devices
Routines
Models
Memory
Activity
Performance
Settings
Developer

```

---

# 62. DEVELOPER MODE

Show:

```text
transcript
intent
Laya probabilities
routine match
model selected
model location
device selected
execution graph
tool calls
latency
RAM
errors
token usage
cost

```

Critical for debugging Kairo.

---

# 63. LOCAL VS CLOUD MUST BE VISIBLE

Every model call should identify its location.

Example:

```text
Intent:
Laya
LOCAL — Kairo Node

Reasoning:
Qwen
LOCAL — Kairo Node

```

or:

```text
Reasoning:
Cloud provider
REMOTE

```

Never misrepresent where inference occurred.

---

# 64. FIRST-RUN RASPBERRY PI SETUP

Kairo Node installer should approximately perform:

```text
detect architecture
↓
detect Raspberry Pi hardware
↓
detect RAM
↓
install runtime dependencies
↓
install Laya runtime
↓
download Laya checkpoint
↓
benchmark Laya
↓
recommend Qwen model
↓
download Qwen model
↓
benchmark Qwen
↓
configure wake word
↓
start Kairo services

```

---

# 65. MODEL DOWNLOADS MUST BE RESUMABLE

Model files can be large.

Support:

```text
resume downloads
checksum verification
partial-download cleanup
model version management
disk-space checks

```

---

# 66. RASPBERRY PI THERMAL MANAGEMENT

Long-running local inference can generate heat.

Monitor temperature.

Allow policies such as:

```text
normal
performance
quiet
thermal-safe

```

If thermal limits are reached:

```text
reduce inference load
↓
use smaller model
↓
optionally cloud escalate

```

Do not crash the device through uncontrolled resource usage.

---

# 67. OPTIONAL ACCELERATORS

The architecture should permit future support for:

```text
Raspberry Pi AI accelerators
USB inference accelerators
desktop GPU servers
other edge accelerators

```

Do not make an accelerator mandatory.

Laya and an appropriately sized Qwen model must have CPU-capable fallback paths where practical.

---

# 68. KAIRO MODEL PROFILES

Example:

```text
PI LIGHT

Laya:
local

Qwen:
small local checkpoint

Cloud:
fallback


PI BALANCED

Laya:
local always loaded

Qwen:
larger local quantized model

Cloud:
optional


PI CLOUD ASSIST

Laya:
local

Qwen:
local for normal requests

Cloud reasoning:
complex tasks only


FULL OFFLINE

Laya:
local

Qwen:
local

Cloud:
disabled

```

---

# 69. FAILOVER

Example:

```text
Laya local fails
↓
restart local service
↓
still fails?
↓
Jev if configured
↓
LLM classifier if necessary

```

Qwen:

```text
Qwen local unavailable
↓
restart
↓
memory insufficient?
↓
load smaller local model
↓
cloud fallback if user permits

```

---

# 70. MODEL WATCHDOG

Local model processes should be supervised.

If Qwen crashes:

```text
detect process exit
↓
capture diagnostic
↓
restart service
↓
restore model

```

Do the same for Laya.

---

# 71. SERVICES

Potential service layout:

```text
kairo-core
kairo-desktop
kairo-node
kairo-voice
kairo-laya
kairo-qwen
kairo-model-router
kairo-executor
kairo-routines
kairo-memory

```

A single service failure should not unnecessarily destroy the entire system.

---

# 72. IPC

Use structured IPC.

Possible:

```text
gRPC
WebSockets
Unix sockets
named pipes

```

Do not use free-form natural-language messages for critical internal commands.

---

# 73. EVENT BUS

Events may include:

```text
wake_word_detected
speech_started
speech_completed
laya_request
laya_completed
qwen_request
qwen_completed
intent_resolved
tool_started
tool_completed
tool_failed
routine_started
routine_completed
device_connected
device_disconnected

```

---

# 74. KAIRO RESPONSE STYLE

Normal responses should be concise.

User:

> "Kairo, open Downloads."

Kairo:

> "Done."

Not:

> "Certainly! I would be delighted to open your Downloads folder."

---

# 75. INTERRUPT

Commands:

> "Kairo, stop."

> "Cancel."

> "Pause."

> "Continue."

> "Undo that."

Stopping must propagate to active model generations and agent workflows where technically safe.

---

# 76. NO INFINITE AUTONOMY

Recursive planning must have bounds.

Default:

```text
maximum automatic retries = 3
maximum recursive plan depth = configurable
maximum runtime = configurable

```

If Kairo repeatedly fails, it should stop and explain the problem.

---

# 77. MVP

The first meaningful release should include:

```text
Windows desktop agent
macOS desktop agent
Raspberry Pi Kairo Node
text input
voice input
wake word
secure provider settings
Jev integration
LOCAL Laya on Pi
LOCAL Qwen on Pi
model manager
model routing
file tools
application launching
basic browser control
routines
device pairing
encrypted LAN communication
verification
activity log
basic self-diagnostics

```

Again:

# LOCAL LAYA AND LOCAL QWEN ON THE RASPBERRY PI ARE MVP REQUIREMENTS.

They are not Phase 12 features.

They are not placeholders.

They are not optional integrations.

---

# 78. DEVELOPMENT ORDER

Recommended implementation order:

```text
PHASE 1
Core schemas
logging
configuration
event bus
database
tests

PHASE 2
Windows/macOS tool executors

PHASE 3
Kairo Node ARM64 service architecture

PHASE 4
Laya LOCAL integration on Raspberry Pi

PHASE 5
Qwen LOCAL integration on Raspberry Pi

PHASE 6
Model Router

PHASE 7
Desktop ↔ Pi pairing

PHASE 8
Routines

PHASE 9
Voice

PHASE 10
Cloud providers / Jev

PHASE 11
Self-diagnosis

PHASE 12
Controlled self-repair

PHASE 13
Performance optimization

```

Do not postpone local Pi inference until the end.

Prove it works early.

---

# 79. HARD ACCEPTANCE TEST — LAYA

A build cannot claim Raspberry Pi Laya support until this works:

```text
1. Fresh Raspberry Pi setup
2. Install Kairo Node
3. Download Laya
4. Disconnect internet
5. Start Kairo
6. Send typed decision request
7. Laya produces local decision
8. Verify no external network request occurred

```

PASS required.

---

# 80. HARD ACCEPTANCE TEST — QWEN

A build cannot claim Raspberry Pi Qwen support until:

```text
1. Fresh Raspberry Pi setup
2. Install supported local Qwen model
3. Disconnect internet
4. Start Kairo
5. Ask Qwen a natural-language question
6. Receive generated response
7. Confirm inference occurred locally

```

PASS required.

---

# 81. HARD ACCEPTANCE TEST — FULL LOCAL AGENT PATH

Test:

```text
Internet:
DISCONNECTED

Windows computer:
CONNECTED TO LOCAL NETWORK

Kairo Node:
CONNECTED

```

User:

> "Kairo, open my Downloads folder."

Required:

```text
wake word
↓
speech recognition or text input
↓
local Laya
↓
desktop tool selection
↓
encrypted LAN
↓
Windows agent
↓
open Downloads
↓
verify
↓
response

```

Cloud APIs must not be required.

---

# 82. HARD ACCEPTANCE TEST — LOCAL QWEN REASONING

Internet disconnected.

User provides a local text file.

User:

> "Kairo, summarize this file."

Required:

```text
file
↓
local Qwen
↓
local response

```

No cloud model.

---

# 83. PERFORMANCE TESTS

Benchmark on supported Raspberry Pi configurations.

Track:

```text
Laya cold load
Laya warm inference

Qwen load time
Qwen first-token latency
Qwen tokens/sec

RAM usage
CPU usage
temperature

voice-to-action latency

```

Save results.

---

# 84. OPTIMIZATION TARGET

The important metric is not benchmark bragging.

It is:

# TIME FROM USER INTENT TO SUCCESSFUL ACTION

Optimize that aggressively.

---

# 85. AI SHOULD DISAPPEAR FOR COMMON COMMANDS

Ideal evolution:

```text
FIRST TIME

User
↓
Qwen
↓
plan
↓
tools

```

Then:

```text
SECOND/REPEATED TIME

User
↓
Laya
↓
routine
↓
tools

```

Eventually:

```text
COMMON COMMAND

User
↓
direct local command
↓
tool

```

That is the intended learning architecture.

---

# 86. FINAL PRODUCT EXPERIENCE

Example:

User anywhere near the Pi:

> "Kairo."

Immediate response.

> "Find the PDF I downloaded earlier, figure out its actual title, rename it, move it to my research folder, and open it on the PC."

Possible execution:

```text
Wake word
Raspberry Pi

Speech
Raspberry Pi

Intent
Laya LOCAL

Planning
Qwen LOCAL

File discovery
Windows PC

Metadata
Qwen LOCAL

Rename
Windows PC

Move
Windows PC

Open
Windows PC

Verification
Windows PC

Response
Raspberry Pi

```

Then:

> "Make that a routine."

Kairo:

> "Saved."

Next time, the workflow should rely primarily on:

```text
Laya
+
routine
+
desktop tools

```

rather than repeatedly calling Qwen.

---

# 87. LONG-TERM KAIRO ARCHITECTURE

Eventually:

```text
                       KAIRO

                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼

      Raspberry Pi    Windows PC       Mac

      Wake word       Desktop tools    Desktop tools
      Laya LOCAL      GPU models       Native APIs
      Qwen LOCAL      Files            Files
      Memory          Browser          Browser
      Routines        Applications     Applications

          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼

                   Optional Cloud

                     Jev API
                    Fast LLM
                 Reasoning LLM
                  Vision Model
                  Coding Model

```

Cloud intelligence expands Kairo.

It must not be the only thing making Kairo intelligent.

---

# FINAL ENGINEERING PRINCIPLE

Kairo should follow this philosophy:

```text
Rules before AI.

Routines before generation.

Laya before unnecessary LLM calls.

Local Qwen before cloud when appropriate.

Cloud when it genuinely improves the task.

Native tools before mouse simulation.

Verification after execution.

Rollback before risky self-modification.

```

And above all:

# KAIRO NODE MUST ACTUALLY RUN LAYA AND QWEN LOCALLY ON THE RASPBERRY PI.

This is a defining feature of Kairo, not an optional enhancement.

The codebase, installer, model manager, router, tests, and Raspberry Pi architecture must all be designed around this requirement from the beginning.