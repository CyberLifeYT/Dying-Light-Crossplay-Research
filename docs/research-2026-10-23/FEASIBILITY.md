# Feasibility assessment (2026-10-23)

Legend: 1 = already proven · 2 = evidence, not confirmed · 3 = plausible hypothesis · 4 = unknown

| Question | Finding | Level |
|---|---|---|
| PC uses EOS for lobbies and gameplay transport? | Yes: `CLobbySessionEos` + `CSessionSocketEos`→`EOS_P2P_SendPacket` | 1 |
| PC has a working LAN path independent of platform services? | Raw UDP discovery (`CSocket`), IPv4 LAN session | 1 (discovery) / 2 (gameplay) |
| Xbox build initializes EOS? | `api.epicgames.dev` resolved at DL1 launch twice | 2 |
| Xbox build creates EOS **lobbies**? | EOS RTC signaling resolved ~0.1 s before `sessiondirectory.xboxlive.com` | 3 |
| Same EOS deployment/sandbox for both? | — | 4 |
| Lobbies platform-restricted (`AllowedPlatformIds`/`bCrossplayOptOut`) or filtered by attribute/bucket? | Official stance is "no console crossplay"; mechanism unknown. Backend-enforced restriction can't be patched on PC | 4 |
| Player IDs compatible? | Both would be EOS ProductUserIds *if* console uses EOS Connect; console's XUID is separate | 3 |
| Authentication platform-bound? | EOS Connect tokens are platform-issued; no token transplanting will be attempted | 1 (by design, out of scope) |
| Same gameplay protocol / REPL_VERSION? | PC = 5; console unknown | 4 |
| Version validation rejects mismatch? | `DisconnectInvalidVersion` exists on PC | 1 (PC side) |
| Xbox has a LAN mode? | — | 4 |
| PC binary modifiable for tests? | Yes, user's copy; work on a separate copy; ToS risk for live-service interaction | 1 (technically) |
| Xbox retail binary modifiable? | No (closed platform, not attempted) | 1 |
| Dev Mode app could join retail DL1 multiplayer? | Retail titles don't run in Dev Mode; a Dev Mode app can't share the console with DL1 and can't speak Xbox Live title multiplayer as DL1 | 1 for "same console"; 3 for "second console as relay" (and low value) |
| Relay/bridge would solve a concrete problem? | Only after a shared protocol is shown (EOS lobby visibility or LAN) | 4 |

## Overall answer today: **MAYBE**
The smallest experiment that converts the biggest uncertainty into evidence: determine whether a console-hosted DL1 co-op game exists as an EOS lobby the PC can see. Concretely: log the PC's own EOS lobby create/search parameters (NEXT_STEPS #1), then observe whether a console-hosted public session appears in a PC search with filters relaxed (requires user approval re: ToS).

## Stop/go criteria
- **STOP Route A/B** if: console traffic shows no EOS lobby/P2P use (only Xbox Live MPSD + Teredo peers), OR EOS backend excludes console lobbies from PC searches even with all client-side filters removed.
- **STOP Route C** if: Xbox DL1 has no LAN option.
- **GO to protocol work** if: a console lobby is visible/joinable from PC → next gate is `REPL_VERSION`/content parity (`DisconnectInvalidVersion`).

## Update after E5 (2026-10-23)
- PC search has no platform/bucket filter; the gates are attribute filters, notably `10000012 == 15500` (build). → If a console build used the same EOS deployment, the main client-side gate would be this version value (patchable on PC for a test), plus the console's own filters (not patchable).
- PC lobbies created with CreateLobbyOptions v8 → no `AllowedPlatformIds` restriction from the PC side (STRONG INFERENCE).
- Still the decisive unknown: does the console build create lobbies in deployment `2a8b…` (same ProductId/Sandbox)? Not observable from the PC unless console lobbies appear in an unfiltered search.
- Next decisive PC-side test (requires user decision, ToS-sensitive): one search with the version filter relaxed, logging only bucket names / `platform` values of results — looks for any bucket other than "Epic"/"Steam"/"GOG".

## Update 2026-10-23 — gameplay handshake (static) and console version
- Console DL1 reports version **1.7.0.8** (user-observed); PC exe 1.55.0.0 / MP_Game_Version 15500. Different release numbering; console MP_Game_Version unknown.
- In-session join requires an **exact, ordered match of a fingerprint list**: REPL_VERSION, RTTI IDS/CRCS/SIZES CRCs, multiplayer data-files CRC, per-file and quest CRCs (VERIFIED from code).
- STRONG INFERENCE: a separately compiled Xbox One build will not produce identical RTTI/layout and data CRCs to the PC build (different platform code compiled into replicated classes, different data packaging). This is the *gameplay protocol* barrier: even with a shared lobby, the join would be rejected.
- Spoofing the fingerprint values on the PC side would not help in principle: the CRCs exist because replicated object layouts must match; if they differ, replicated state is misinterpreted. Matching values are only meaningful if the builds are layout-identical, which cannot be checked without the console binary (not obtainable legitimately).
- Revised overall assessment: **Route A/B (EOS crossplay with the unmodified Xbox client) — very unlikely**: three independent gates (deployment/version filters, client version range 15500–15599, exact layout/data fingerprint handshake), the last of which reflects a real binary-compatibility requirement. Remaining unknowns no longer have a plausible path to change that outcome without Techland shipping matched builds.
