# Windows desktop launcher

`python -m app.desktop` wraps the existing Streamlit mini-chat in pywebview
6.2.1 with the Windows Edge Chromium renderer. It creates a centered, normally
framed, fixed-size window up to 560×720 with move/minimize/close controls.
Maximizing and user resizing are disabled; screen dimensions reduce the initial
size when necessary. No browser tab, address bar, executable packaging,
new service architecture, or AI/tool change is introduced.

## Setup

Use Python 3.12 and the repository's UI environment on Windows:

```powershell
.\.venv-ui\Scripts\python.exe -m pip install -e ".[desktop]"
$env:OLLAMA_MODEL = "qwen3:4b-instruct"
.\.venv-ui\Scripts\python.exe -m app.desktop
```

The already installed public qwen3:4b model is also supported. Ollama remains a
separately installed/running local service with cloud disabled. The desktop
launcher starts Streamlit automatically, not Ollama. WebView2 Runtime and the
Windows .NET support needed by pythonnet must already be available; no system
runtime installation is attempted. The optional desktop extra leaves core CLI
installation independent. `python -m app.web` still opens the browser-based UI.

## Process ownership and ports

A direct multiprocessing spawn worker calls Streamlit's existing native runner,
bound explicitly to 127.0.0.1 with headless mode, telemetry disabled, and no
watcher or exception-detail display. It inherits the existing synthetic-only
Ollama interface. No private paths, identity controls, or Python JS API are added.

The OS selects a free loopback port; the launcher never takes over or kills an
existing server. Releasing the probe socket creates a small bind race, so startup
retries up to three workers. An unpredictable per-run base path and live-child
check accompany the health probe; redirects/proxies are disabled. Only a healthy
owned worker permits window creation. Each attempt has a 20-second readiness
budget plus bounded request time. Startup failures are sanitized.

The native GUI loop blocks until window close. A finally block terminates/joins
only the direct worker handle, with a kill fallback for that same handle. There
is no port-based process kill, process-name matching, shell, taskkill, or reuse of
an unrelated server. GUI startup failure and KeyboardInterrupt also clean up.
A daemon worker adds interpreter-exit cleanup; abrupt OS/process termination is
not a crash-proof process supervisor and may require local cleanup.

## Verification performed on Windows — November 1, 2026

- Optional desktop installation succeeded on Python 3.12.14.
- Eight launcher tests passed. Native-window calls in unit tests are mocked;
  one integration test starts a real spawned Streamlit worker, waits for health,
  closes it, and verifies an unrelated occupied port stays reachable.
- Retry, failure cleanup, dead-worker readiness, owned-handle termination/kill,
  window dimensions, loopback/headless flags, and renderer settings are tested.
- Full available suite: **143 tests, 142 passed, 1 skipped**, no failures/errors,
  45.330 seconds. Live Ollama enabled; Gemini skipped for missing free-tier key.
- Separately, the real Windows window opened with WebView2 and no browser chrome.
  A real qwen3:4b-instruct turn returned the synthetic PIX quote R$90.09. The
  light/dark toggle retained chat. Native maximize/restore worked and title-bar
  minimize/close controls were visible. Compact messages remained readable and
  did not overflow horizontally after the scoped CSS correction.
- Closing through the native close button ended the launcher with exit code 0;
  its port 51203 became unreachable while Ollama on 11434 stayed reachable.
  That port is historical evidence, not a configured fixed application port.
- The compact native render exposed a pre-existing user-message contrast/wrapping
  issue. A scoped CSS rule now sets the user text color and wraps long lines;
  layout, agent, and privacy behavior remain unchanged.

## Limits

Windows/WebView2 only for this launcher. Display scaling changes measured client
size; very short resized windows can require vertical page scrolling in addition
to message scrolling. Sessions use private WebView storage and lose history/theme
when closed; theme survives reruns within a session. No transcript persistence,
API bridge, auto-updater, executable, installer, or production authentication.
This local wrapper does not eliminate the existing model-answer limitations.

The Streamlit child runs without a separate visible console. When launched with
python.exe, the invoking terminal can remain open and carries sanitized startup
errors. pythonw.exe can hide that terminal but also hides those messages; an
executable/shortcut installer was not requested. Source/background processes
remain local and no remote/push/submission was performed in this phase.

Official references: [pywebview API](https://pywebview.flowrl.com/api/),
[Windows web engine requirements](https://pywebview.flowrl.com/guide/web_engine).

## Startup diagnostics verification (Python 3.12.15)

The reported startup failure was investigated using the existing `.venv-desktop`
environment: Python 3.12.15, Streamlit 1.66.1 and pywebview 6.2.1. No packages or
Windows runtimes were reinstalled. The local module path and repository working
directory were checked. Both normal startup and startup through Windows
PowerShell 5.1.26100.9818 succeeded during verification. The PowerShell 5.1 run
subsequently exited with code 0. Thus the reported terminal failure's underlying
exception remains **unreproduced**; no backend/port/runtime cause is asserted.

The confirmed diagnostic defect was the blanket exception handler: it always
suggested missing dependencies while discarding the original exception. With
`EMPORIO_DESKTOP_DEBUG=1`, the launcher now prints the actual traceback and keeps
the spawned Streamlit output visible in the local console. Normal startup remains
quiet, with a neutral diagnostic hint on failure. This flag does not enable the
WebView inspector, change renderer/server behavior, record chat content, or expose
diagnostics through the customer UI. Local paths can appear in developer output.
The local environment directory is excluded from Git.

All 11 launcher tests passed, including real child startup, loopback readiness,
owned-worker cleanup and preservation of an unrelated occupied port. New mocked
tests verify opt-in traceback visibility and preservation of child output; they
do not claim to reproduce the user's original failure. Full suite in this
environment: **172 tests in 13.221 seconds, 166 passed, 6 skipped**, no failures or
errors. Skips were the six opt-in live provider/scope/correctness checks, not
desktop lifecycle tests. A traceback from the original failing session is still
needed before claiming a root-cause startup fix.
