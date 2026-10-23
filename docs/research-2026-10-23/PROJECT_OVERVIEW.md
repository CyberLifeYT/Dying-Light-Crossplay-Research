# Dying Light 1 — PC (Epic) ↔ Xbox One / Series co-op research

_Started this notes set: 2026-10-23. Earlier work (2026-10-22) lives in the parent `opencode` folder and is left untouched._

## Goal
Determine, with evidence, whether Dying Light 1 on Epic Games Store PC can play co-op with Dying Light 1 on Xbox One (incl. backward-compatible play on Series X|S), and the most practical route.

## Scope / routes
| Route | Description | Status (2026-10-23) |
|---|---|---|
| A | Crossplay via existing services (EOS lobby / P2P) | **OPEN** — hinges on whether the Xbox build uses EOS lobbies in a reachable deployment |
| B | Modify/instrument the PC build | **OPEN** — first step is read-only runtime logging of EOS calls |
| C | LAN | **OPEN, conditional** — PC LAN path is real (raw UDP); unknown if Xbox has any LAN mode |
| D | Xbox Dev Mode custom client / port | **STOPPED as a crossplay route** — retail games don't run in Dev Mode; full port = separate multi-year project |
| E | Compatibility layer (relay/bridge) | **PARKED** — only meaningful once A/C establish a shared protocol |
| — | DNS redirection | **STOPPED** — measurement tool only |

## Evidence labels
VERIFIED · STRONG INFERENCE · HYPOTHESIS · UNKNOWN · DISPROVEN (never upgrade a label in a later summary without new evidence).

## Current status
PC architecture mapped from the binary (see `NETWORK_ARCHITECTURE.md`, `FUNCTION_ANALYSIS.md`). Biggest unknown: does the Xbox build create EOS lobbies, and in which deployment/with which platform restrictions? Next actions in `NEXT_STEPS.md`.

## Handling rules
- Original game files and earlier research files are never modified.
- EOS ClientId / ClientSecret and deployment IDs embedded in the engine are **not** recorded in these notes. Product ID and Sandbox ID are recorded (public identifiers).
- Note: this folder is under `%LOCALAPPDATA%\Temp`; Windows Disk Cleanup / Storage Sense can delete it. Keep a backup elsewhere.

## Index
`FILE_INVENTORY.md` · `NETWORK_ARCHITECTURE.md` · `FUNCTION_ANALYSIS.md` · `NETWORK_EXPERIMENTS.md` · `FEASIBILITY.md` · `NEXT_STEPS.md` · `DECISION_LOG.md` · `OPEN_QUESTIONS.md` · `tools/` (Ghidra scripts) · `evidence/` (redacted decompiler output)

_Update 2026-10-23: lobby attribute schema decoded — see `ATTRIBUTE_MAP.md`._

_Final conclusion (2026-10-23): see `CONCLUSION.md` — PC↔Xbox co-op not achievable under current constraints._
