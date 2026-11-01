# Phase 3: Configurable Providers and Interactive Tool Calling

## Delivered

An interactive, single-LLM customer-service CLI with native Gemini/Ollama
adapters, validated deterministic tools, session-bound order access, bounded
multi-turn context, public synthetic fixtures, and no paid-provider dependency.
No frontend, vector store, framework, multi-agent system, push, or submission.

The fixed synthetic scenario runner remains an optional smoke tool. It is not
the conversational interface: `python -m app.cli` accepts arbitrary customer
questions. Local Ollama preserves the full input; Gemini receives only a limited
synthetic projection, never the original free-form question.

## Incremental milestones

1. `ab3740c` — `feat(providers): add Gemini free-tier and local Ollama adapters`.
   All 75 then-existing tests passed on Python 3.15.1 and 3.12.14 before commit.
2. `43882bf` — `feat(agent): integrate bounded tools with synthetic cloud isolation`.
   88 discovered tests: 86 passed, two live-model skips before commit.
3. Interactive conversation, fixture packaging, CLI/security verification, and
   documentation are the final milestone recorded by this phase's next commit.

No earlier history was rewritten or squashed. Original Phase 1/2 implementation
and tests remain unchanged. The integration test formerly named as a fresh-run
check now explicitly describes non-persistence of unverified turns; successful
turns are retained as required for conversation.

## Files

Created during Phase 3:

- `app/providers.py`: native REST adapters, configuration, bounded/sanitized HTTP.
- `app/tool_runtime.py`: allowlisted tool schemas/dispatch, minimized results.
- `app/agent.py`: explicit function-calling loop and per-session conversation state.
- `app/synthetic.py`: approved fixture loading, temporary CSV/PDF generation.
- `app/cloud_privacy.py`: approved-vocabulary projection for free-form cloud input.
- `app/cli.py`: interactive input, reset/quit, data modes, startup identity.
- `app/provider_demo.py`: optional fixed synthetic smoke runner.
- `app/fixtures/synthetic.json`: inspectable public fictitious data/policies.
- `tests/test_providers.py`: mocked native provider/HTTP contracts.
- `tests/test_agent_integration.py`: synthetic tool/agent protocol integration.
- `tests/test_cli_conversations.py`: fake-provider CLI/history/privacy tests.
- `tests/test_http_transport.py`: actual loopback HTTP against a synthetic stub.
- `tests/test_live_providers.py`: opt-in real LLM smoke tests.
- `docs/PROVIDERS.md`: dated provider verification and primary sources.
- `docs/PHASE_3.md`: this report.

Updated README, pyproject metadata/version/entry point/package data, environment
example, and Git exclusions. Version is 0.3.0. No new runtime dependencies beyond
the existing pinned pypdf. Generated wheel/virtual environment remain ignored.

## Key decisions

- Gemini 3.1 Flash-Lite was verified in official documentation as stable,
  function-calling capable, and free-tier eligible on November 1, 2026. This does
  not establish a particular account's access, quota, or billing state.
- GEMINI_FREE_TIER_CONFIRMED requires explicit operator confirmation of a free
  project without billing. An inference key cannot verify billing configuration.
  Unknown/paid models are rejected; quota/errors have no automatic retry/fallback.
- Local Ollama is restricted to HTTP loopback IP/port and an installed local model
  advertising tools capability. Cloud names/remote metadata and redirects/proxies
  are rejected. The trusted server must also run with OLLAMA_NO_CLOUD=1.
- Supplied store data/policy never enters the application Gemini path. Only the
  exact built-in SyntheticTools factory is accepted. Public fixture content is
  fingerprinted; changing it needs an explicit code update after review.
- Gemini supports contextual demo questions through a narrow Portuguese intent
  vocabulary plus synthetic IDs/fixed budgets. Original text/unknown tokens are
  discarded, common identifiers rejected, and only projected history retained.
  This is not a general-purpose anonymizer; unrestricted customer input is local.
- Startup flags bind demo identity; neither conversation nor tools can change it.
  Reset forgets history only. Ownership checks remain inside the Phase 2 service.
- Four model requests/six tools per turn, four whole exchanges, and bounded
  serialized history prevent unbounded loops/context. Failed/incomplete turns
  are not retained. Follow-ups may use prior authorized snapshot evidence.
- First-turn factual prose without tool evidence is withheld; greetings are local.
  Tool outputs carry source/unknown/truncation flags. Generated prose is still
  subject to model error and requires live evaluation, not an accuracy claim.

## Executed verification — November 1, 2026

| Check | Actual result |
| --- | --- |
| Final full suite, Python 3.15.1 | 103 discovered: 101 passed, two live-model skips, zero failures |
| Final full suite, Python 3.12.14 | 103 discovered: 101 passed, two live-model skips, zero failures |
| Full suite without original resources | 103 discovered: 90 passed, 13 skipped, zero failures |
| Explicit opt-in live suite | Both skipped: Gemini key/free-tier confirmation absent; Ollama server unavailable |
| Editable install | emporio-agent 0.3.0 installed successfully |
| Dependency check | No broken requirements |
| Public wheel build | Built successfully; approved JSON fixture included |
| Wheel content audit | No CSV, PDF, or secret environment file included |
| Isolated wheel fixture loading | Three synthetic products and expected deterministic quote verified |
| Installed CLI help | Entry point/arguments verified |
| Actual CLI startup/greeting/quit | Passed from another directory; no model invoked |

Default test command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Tests explicitly distinguish mocked API responses, actual local HTTP stub
execution, original-data integration, and genuine LLM execution. No actual LLM
response or customer transcript is claimed. A new history test initially assumed
Mock arguments were snapshots; it was corrected to inspect the last user message
because the in-memory list later includes the final assistant message. Successful
results above were executed after that correction.

## Local setup and conversation

See the README for exact server and client commands. Install a current Ollama
release, pull qwen3:4b, verify tools capability, and start the server with cloud
disabled. The client uses 16K context and disables thinking for local tool turns;
hardware must fit weights/context. Use LLM_TIMEOUT_SECONDS=120 for slower local
hardware. No latency/quality result is claimed for this machine.

Run synthetic mode without private resources, or local mode against the six
provided CSVs and policy PDF. Order access is denied unless startup explicitly
binds a demo identity. The Gemini interactive demo always uses approved public
fixtures, and its narrower input projection is explained before the prompt.

## Remaining limitations and next step

- Live tool selection, multilingual answer quality, latency, grounding, and
  prompt-injection behavior have not been measured against an actual model here.
  Configure a local provider and run the opt-in tests plus genuine conversations.
- No fabricated transcripts are included. Capture 3-5 real, reviewed/sanitized
  examples after live execution, including policy ambiguity and denied access.
- Conversation memory is bounded; resetting/old-turn removal loses prior context.
- Demo binding is not production authentication or Python-process isolation.
- Policy retrieval remains a limited document profile/lexical matcher; source
  conflicts, missing facts, stale snapshots, and truncated excerpts remain visible.
- Original challenge/email, final submission format, redistribution permission,
  and deadline still need confirmation before submission. Nothing was pushed.
