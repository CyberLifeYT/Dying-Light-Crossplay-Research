# Conclusion — Dying Light 1: Epic PC ↔ Xbox One / Series co-op

_Date: 2026-10-23. Builds examined: PC (Epic) 1.55.0.0, engine/gamedll PE timestamp 2026-07-05, EOS SDK 1.15.5. Console: Xbox, Dying Light 1.7.0.8 (user-reported)._

## Answer
**Not achievable under the current constraints** (unmodified Xbox retail game, no access to the console binary, no cooperation from Techland/Epic/Microsoft).
Not because of one missing setting, but because the game's join handshake demands that both players run **layout-identical builds**, which a separately compiled console version almost certainly is not. Every other obstacle is secondary to that one.

Confidence: high that it cannot be made to work by the means available here; the one thing that would overturn it is evidence that the console build is compiled to produce the same replication fingerprints as PC 1.55 — which only Techland can provide.

## How a PC co-op game actually works (VERIFIED from binary + runtime logs)
```
Epic launcher exchange code → EOS Auth (Epic account) → EOS Connect (ProductUserId, credential EPIC)
→ EOS lobby: BucketId "Epic", XLAST-schema attributes (MP_Game_Version=15500, MP_Progress, MP_DlcArea, …)
→ search: no platform/bucket filter; MP_Game_Version == 15500 + mode/progress filters  (Steam + Epic lobbies returned)
→ client check: found game accepted only if version in 15500–15599
→ join via EOS Lobby → EOS P2P (socket = lobby id, unreliable packets, game-level reliability)
→ Net::Repl IdRequest: exact ordered match of verify list
     REPL_VERSION=5, RTTI IDS CRC, RTTI CRCS CRC, RTTI SIZES CRC, data_crc, per-file/quest CRCs
→ replicated gameplay
```

## Key evidence
| # | Finding | Label | Where |
|---|---|---|---|
| 1 | Online play = EOS lobbies + EOS P2P; lobby layers `CLobby → CLobbyCrossPlatform → CLobbyEpic` | VERIFIED | FUNCTION_ANALYSIS, NETWORK_ARCHITECTURE |
| 2 | PC cross-store play works by *not* filtering on store/platform (results in buckets "Epic" and "Steam") | VERIFIED | NETWORK_EXPERIMENTS E5/E6 |
| 3 | Lobby keys are XLAST properties from `data/spa/game.gameconfig` (Xbox Live schema, has `MP_Host_Xuid`) — same schema very likely on console | VERIFIED / STRONG INFERENCE | ATTRIBUTE_MAP |
| 4 | Version gate: search `MP_Game_Version == 15500`; client accepts 15500–15599 | VERIFIED | ATTRIBUTE_MAP |
| 5 | Join handshake requires identical, ordered fingerprints incl. class-size and layout CRCs and multiplayer data CRC | VERIFIED | FUNCTION_ANALYSIS (verify-data) |
| 6 | Xbox DL1 contacts `api.epicgames.dev` on game launch (clean baseline has none) | STRONG INFERENCE | NETWORK_EXPERIMENTS E8 |
| 7 | Whether the Xbox build creates EOS lobbies, and in which deployment | UNKNOWN | — |
| 8 | Console version 1.7.0.8 vs PC 1.55 (separate release lines) | VERIFIED (user) | OPEN_QUESTIONS |
| 9 | Xbox build produces different RTTI/layout/data CRCs from PC | STRONG INFERENCE | FEASIBILITY |

## Routes
| Route | Verdict | Reason |
|---|---|---|
| A — existing services (EOS) | **Ruled out in practice** | Even if both use the same EOS deployment (unknown), finding #4 then #5 reject the join; #5 reflects real binary incompatibility |
| B — modify the PC build | **Ruled out** | PC-side changes can relax filters/version checks, but cannot make the PC's replicated object layout match a different console build; spoofing fingerprints would only admit corrupt state. Modifying live-service queries was also declined in this project |
| C — LAN | **Ruled out for crossplay** | PC LAN (raw UDP, "C6DW" discovery, PlatformId == 1) is real, but uses the same Net::Repl handshake; console LAN support never shown |
| D — Xbox Dev Mode / port | **Ruled out** | Retail games don't run in Dev Mode; a port means reconstructing a proprietary engine (separate, multi-year project, not crossplay with the retail game) |
| E — relay / protocol bridge | **Ruled out** | No shared protocol to bridge: the incompatibility is in game-state serialization, not transport or discovery |
| DNS redirection | **Ruled out** | Observation tool only; can't change console behaviour or bypass TLS/auth |

## What was disproven or corrected along the way
- "Xbox DL1 never got EOS" — contradicted (E8: EOS lookup at console game launch).
- "Xbox ret-stubs prove no Xbox code" — overstated (shared empty-function folding).
- LAN header/magic interpretation and scanner-type mapping in the early notes — corrected.
- EOS P2P "reliable" assumption — observed traffic is unreliable-unordered with game-level reliability.

## Nearest feasible alternatives
1. **Play on the same platform family.** PC ↔ PC across Epic, Steam and GOG works today (verified: Epic searches return Steam-hosted lobbies). Xbox ↔ Xbox works on Xbox Live. The practical fix is for both players to be on PC, or both on Xbox.
2. **Ask Techland.** Only the developer can ship matched builds or console crossplay. A support request citing the evidence (separate console line 1.7.0.8 vs PC 1.55; XLAST schema already console-ready) is the only path that changes the core obstacle.
3. **Check newer titles for crossplay** (e.g. whether the newer Dying Light games support PC–console crossplay) — not investigated here; verify against current official information.

## What could still change the answer
- Techland documentation or a statement that console and PC builds share replication layouts and a common EOS deployment.
- A future official update enabling console crossplay.
Absent those, further reverse-engineering of the PC client cannot produce crossplay with the unmodified Xbox game.

## Artifacts
Notes: this folder (`PROJECT_OVERVIEW`, `FILE_INVENTORY`, `NETWORK_ARCHITECTURE`, `FUNCTION_ANALYSIS`, `ATTRIBUTE_MAP`, `NETWORK_EXPERIMENTS`, `FEASIBILITY`, `DECISION_LOG`, `OPEN_QUESTIONS`). Tools: `tools/` (Ghidra scripts, read-only EOS logger v2, DNS observer v2). Logs: `logs/` (third-party IDs redacted). Extracted: `extracted/game.gameconfig`.
Reminder: this folder lives under `%LOCALAPPDATA%\Temp` — copy it somewhere permanent.
