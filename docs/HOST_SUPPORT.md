# Host support and evidence

**MIT preview: bounded offline checks passed in Claude Code, Claude web and ChatGPT Work.** Codex and Gemini execution remains unverified. These results do not certify live integrations, unattended operation or every product surface.

| Actual surface | Current-package result | Evidence and limit |
| --- | --- | --- |
| Claude Code | PASS, bounded synthetic checks | Version 2.1.301; actual tool stream, reference reads, 23 package members and inputs unchanged |
| Claude web | PASS, bounded synthetic checks | Native skill; expanded tool responses, eight core hashes and inputs checked; invocation correction below |
| Claude Desktop app | NOT RUN for skill acceptance | A desktop Chromium walkthrough preview was reviewed, but it is a different test from native skill/reference/runtime acceptance |
| ChatGPT Work web, native standalone skill | PASS, bounded conversation-reported checks | Native replacement/invocation observed; completed receipt reports 14 expected exits, eight matching core hashes and eleven unchanged input hashes; raw tool transcript not exposed |
| Codex CLI | BLOCKED; execution unverified | Earlier first skill-file read denied by execution policy; no current-package execution or retry |
| Gemini Apps | BLOCKED; execution unverified | Predecessor import did not establish reference reads or script execution; current package not accepted |
| Gemini CLI | NOT RUN | No tested CLI runtime; Apps results do not transfer |
| OpenAI plugin route | NOT RUN | Local plugin-layout checks only; ChatGPT standalone acceptance does not certify this route |

No production skill, social account, tracker, post, schedule or guide delivery was changed. Raw conversations, account identifiers, local paths and receipts remain outside this distributable subtree.

## Exact packages

All four archives were rebuilt twice with identical bytes. Build them with the commands in [setup](SETUP.md); documentation, tests and walkthrough assets are excluded.

| Archive | Current SHA-256 | Host acceptance |
| --- | --- | --- |
| `content-operations-claude.zip` | `f13b3cc5e8b0a397ba530b72a3c193a8c75c835206e490753651adbe50c725ca` | Claude Code/web and ChatGPT standalone PASS, with evidence limits below |
| `content-operations-codex.zip` | `f13b3cc5e8b0a397ba530b72a3c193a8c75c835206e490753651adbe50c725ca` | BLOCKED |
| `content-operations-openai.zip` | `55c1ea8d8d1bd8cfdb39acfbfaa92a4691161198661debe94ff23a1da6e4d275` | NOT RUN |
| `content-operations-gemini.zip` | `a3eb66e37efea3b151c1ff77c77e2fb3574ff36b353751d17985ad6097151999` | BLOCKED/unverified |

## Current acceptance, 1-2 November 2026

Claude Code, Claude web and ChatGPT Work read the skill and both portable-host/current-record references. Smoke, valid release and nullable-field controls returned 0. Six invalid cases (missing evidence, malformed timestamp, malformed URL, array status, false optional timestamp and null object) returned structured errors with exit 1. Deeply nested tracker and action-log inputs returned input error 2 without tracebacks. An overflowing slot window returned 2; the valid final-year slot and empty-window controls returned 0 with the expected arrays. These are 14 execution checks per surface, subject to the evidence limits below. No live service was exercised.

Claude Code used a session-only plugin, Python 3.12.10 and Opus 5.5. Its raw tool stream records 15 commands, including identity inspection; all 23 package members and synthetic inputs stayed unchanged. This final attempt had no denied command or retry and ended without persistent installation.

Claude web displayed Sonnet 5.5 Medium and Python 3.13.18. The importer unfolded the YAML description: replacing the folded marker/newline/indent with a single-line description reproduced the observed SKILL hash; the other seven checked core files matched. An initial inspection was not run because the host classifier had not evaluated it; the identical host-requested resubmission ran. The host initially added an undocumented `-I` flag to smoke execution, causing `ModuleNotFoundError` and exit 1. The documented invocation without `-I` passed, with no source or permission change. Expanded tool responses establish final exits, unchanged core/attachment/deep-input hashes, and a read-only comparison of all eight generated cases against their original attachment values. This is not a downloaded whole-import or raw-transcript audit. The task copy was disabled after testing. These browser observations are not a separate Claude Desktop skill test.

ChatGPT Work's first recovered task copy had stale validator/reference hashes and stopped safely before execution. An initially dismissed upload did not execute. Following a specific replacement instruction, the normal upload flow completed and replaced the same task-owned standalone copy, without a duplicate or indirect workaround. The replacement used the enclosing-folder Claude archive above, not the OpenAI plugin archive. The copy was briefly activated, invoked natively in a new synthetic-only chat, then uninstalled; its Add control was observed again.

The completed ChatGPT Work receipt reports Python 3.12.14, documented `python -B` commands, all 14 expected exits, no unexpected failed script attempts or tracebacks, eight unchanged core files and eleven unchanged inputs. Local comparison reproduced every reported core hash from the reviewed ZIP and every input hash from the original synthetic fixture/declared serialization or deep-input construction. The first read's displayed output was oversized and truncated; the completed result and JSON receipt were not. Native activity labels and the completed conversation are observable, but the underlying raw tool transcript and whole imported archive are not exposed here. This is bounded conversation-reported acceptance, not an independent raw execution audit or live-service test.

All three completed surfaces refused hypothetical guide sends/arrival claims without the required route and evidence, and described manual review with automated checks marked NOT RUN when Python is unavailable. These answers do not grant authority or verify integrations.

## Before using another surface

Use the [portable-host contract](../skills/content-operations/references/portable-hosts.md) and test the actual package, import route, reference access and runtime. A CLI result does not certify a chat UI or desktop app. Resolve policy restrictions through the supported owner/administrator workflow; never bypass a denial or treat an unavailable runtime as a pass.

Local packaging and disposable installation are not host acceptance. Passing any test never grants social-account access or permission to publish, send guides or start recurring service.
