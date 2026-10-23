# Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-23 | Notes live in `opencode\research_notes`; existing files untouched | User instruction |
| 2026-10-23 | Do not record EOS ClientId/ClientSecret/deployment IDs | Credential hygiene |
| 2026-10-23 | Ghidra used only with `-readOnly -noanalysis` | Preserve existing project |
| 2026-10-23 | Route D stopped as a crossplay route | Retail titles don't run in Dev Mode (Microsoft docs); full port = proprietary engine reconstruction |
| 2026-10-23 | DNS redirection stopped as a solution | Can't change console behaviour or bypass TLS/auth; agreed with `DNS_ASSESSMENT.md` |
| 2026-10-23 | SetGameAuthenticationType deprioritized | Plain setter; no readers in lobby module |
| 2026-10-23 | Next priority = runtime EOS logging on PC | Cheapest way to learn lobby partitioning |

## Corrections to 2026-10-22 notes (originals not edited)
| Earlier claim | Correction | Evidence |
|---|---|---|
| Xbox exports are `ret` stubs ⇒ no Xbox code compiled (`CROSSPLAY_FEASIBILITY.md`, `PROGRESS.md`) | Overstated: `0x1800110f0` is shared by 40+ empty IGame callbacks (ICF folding) | pefile export scan |
| `CreateScanner` picks LAN for type 1/2 (`DNS_ASSESSMENT.md`) | Type 0 = LAN, 1 = EOS, 2 = both | factory vtable `0x1808a79d0` |
| First LAN byte low7 = message type 0..5 (`LAN_PROTOCOL.md`) | Low7 = header format (0–2); high bit = length field; type comes from `Type` field | `0x1806a78a0` |
| `0x43364457` = "WD6C" magic | FourCC "C6DW" GameId value ("DW" = game data prefix) | constant + folder names |
| "Xbox One DL1 never updated to EOS" | Unsupported; console resolves `api.epicgames.dev` at DL1 launch | `xbox_phased.log` |
| Phased run attributes traffic | PH0 baseline contaminated | `xbox_phased.log` |
| PC build is "2022" | Installed binaries are 1.55, PE timestamp 2026-07-05 | PE headers |
| 2026-10-23 | Installed Frida 17.24.3 + frida-tools 14.11.0 (pip --user) | User approved |
| 2026-10-23 | Logger v1 results only trusted when self-validating; logger v2 attributes calls via caller IAT slot | EOSSDK identical-stub folding discovered |
| 2026-10-23 | Scrubbed third-party SteamIDs from eos_run1.log; widened redaction rule | Privacy |
| 2026-10-23 | Earlier static claim "P2P reliable=1" superseded: observed sends use reliability 0 on socket named by lobby id | E5 |
| 2026-10-23 | Logger v2 validated (0 unattributed / 0 errors in run 2); run-1 findings confirmed | E6 |
| 2026-10-23 | Relaxed-version-filter live search NOT performed (blocked; modifies live-service queries) | Switched to static decoding |
| 2026-10-23 | Extracted data/spa/game.gameconfig (read-only from Data0.pak) to research_notes\extracted | Decodes all lobby attribute keys |
| 2026-10-23 | Feasibility of PC↔Xbox gameplay revised to "very unlikely" | Verify-data handshake requires identical RTTI/layout/data CRCs (static, VERIFIED); console on 1.7.0.8 |
