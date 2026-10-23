# Network experiments

## E1 — Console DNS observation, unphased (2026-10-22 13:47–13:49) — earlier session
Log: `../xbox_dns.log`. Console 192.168.0.195. Names included `api.epicgames.dev`, `signaling-service-prod.euw1.live.rtcp.on.epicgames.com`, `pls.dyinglightgame.com`, `sessiondirectory.xboxlive.com` + Xbox OS names.
Result: not attributable to the game (no phases). Label: observation only.

## E2 — Console DNS observation, phased (2026-10-22 14:29–14:52) — earlier session
Log: `../xbox_phased.log`. Phases 0 baseline … 5 play.
- PH0 ("DL1 not running") already contains `pls.dyinglightgame.com`, `api.epicgames.dev`, EOS RTC signaling and `sessiondirectory.xboxlive.com` → **baseline not clean** (likely DL1 suspended in Quick Resume, or phase not advanced).
- PH1 (launch): `peoplehub/privacy/rta` burst + `api.epicgames.dev` (14:48:25), then `pls.dyinglightgame.com` (+22 s) — same pattern as PH0 14:30:03 / 14:30:25.
- PH2–PH5: essentially nothing (console DNS cache).
Interpretation: STRONG INFERENCE that launching DL1 on the console triggers `api.epicgames.dev`. Not proof that lobbies are EOS.

## E3 — pcapng triage (2026-10-23, of `../xbox_trace.pcapng`, 44,302 packets)
Only 18 flows involve the console: DNS to 192.168.0.17 and multicast (LLMNR, IGMP, UDP 3074 → 224.0.0.253:3544 Teredo). **No gameplay/session traffic visible** — the PC is not on the console's path (switched LAN).

## Methodology for the next console capture (E4, not run)
1. Full console shutdown (disable Quick Resume for DL1 / power off) between runs.
2. Capture vantage point that sees console traffic: router mirror port, or PC as Wi-Fi hotspot / bridge for the console.
3. Phases: baseline (dashboard 3 min) → launch DL1 → main menu → online menu → host co-op → friend joins → play 2 min → quit.
4. Record per phase: DNS names, TCP/UDP endpoints (IP:port), packet counts/sizes, UDP vs TCP, whether peer IPs are Epic relay ranges, Microsoft (Teredo/3074), or the friend's IP.
5. Record DL1 version shown on console title screen.
6. Never capture/decrypt TLS; don't record account tokens.

## E5 — PC runtime EOS logging, run 1 (2026-10-23 01:09–01:12 UTC) — `logs/eos_run1.log`
Setup: Frida 17.24.3, `tools/eos_logger.js` (v1) attached to DyingLightGame.exe pid 6040 ~instantly after launch. User hosted a co-op game, searched, joined one game.
**Caveat found:** EOSSDK folds identical export stubs — 21 of 25 hooked addresses are shared with 1–8 other exports (e.g. `LobbySearch_SetParameter` == `LobbyModification_SetPermissionLevel`, `LobbySearch_GetSearchResultCount` == `LobbyDetails_GetMemberByIndex`). v1 lines are therefore only trusted when self-validating (sane ApiVersion + readable key strings). v2 of the logger attributes every call by the caller's IAT slot (620 `FF 15` call sites in the engine) and drops foreign calls.
Privacy: other players' SteamIDs (`owner_id`, attr `20000083`) were captured by v1; scrubbed from the log (142 occurrences) and the redaction rule fixed.

Results (trusted lines):
| Item | Value | Label |
|---|---|---|
| Platform options | ApiVersion 12, ProductId ec72fb…, SandboxId 2c4252…, DeploymentId = first embedded ID (prefix `2a8b`), not server | VERIFIED |
| Epic login | `EOS_Auth_Login` with EXCHANGE_CODE (launcher) → `EOS_Connect_Login` ExternalCredentialType EPIC | VERIFIED |
| CreateLobby | ApiVersion **8**, MaxLobbyMembers 5, INVITEONLY at creation, presence 0, invites 1, **BucketId "Epic"**, host migration on, RTC room on | VERIFIED |
| Lobby attributes (host) | `VISIBILITY`, `players_cnt`, `name`, `owner_id`, `query_id`, and ~25 numeric-hash keys, e.g. `10000012=15500`, `10000015=16780550`, `1000008a=-2`, `1000003c=14`, `10000052=1000`, `10000088=1060`, `10000089=100` | VERIFIED |
| Member attributes | `platform` INT64 **= 2** (Epic), `team`, `name`, `player_id`, `connected` | VERIFIED |
| Search filters | MaxResults 200; `10000012 == 15500`; `10000015` range (≥16777216 / ≤16780550 etc.); `1000008c==0`; `1000008d==0`; `10000050<=1`; `10000017<=0`; `1000008a == -2 / 2 / 39` (varies by search task); **no bucket filter, no platform filter** | VERIFIED |
| Search results | counts 15, 18, 122, then 0/1; lobbies in buckets **"Epic" and "Steam"** | VERIFIED |
| Gameplay transport (joined game) | EOS P2P, socket name = lobby ID, channel 0, reliability 0 (unreliable-unordered → game does its own reliability), 9–1150-byte packets, ~150 pkts/10 s each way | VERIFIED |

Interpretation:
- Cross-store play on PC is implemented by **not filtering on bucket/platform**; buckets just record the owner's store. STRONG INFERENCE.
- `10000012 = 15500` behaves as an exact-match **build/version gate** (1.55.00). STRONG INFERENCE. A console lobby is only visible to this PC search if it advertises the same value.
- CreateLobbyOptions v8 predates `AllowedPlatformIds`/`bCrossplayOptOut` (SDK 1.16) — so PC lobbies carry no backend platform restriction. STRONG INFERENCE (from SDK version history; verify against 1.15.5 headers).
- No lobby with a non-Steam/non-Epic bucket was observed in any search. This does **not** prove consoles are absent from the deployment — consoles at a different version value would be filtered out by `10000012`.

## E6 — PC runtime EOS logging, run 2 with logger v2 (2026-10-23 01:18–01:21 UTC) — `logs/eos_run2.log`
Logger v2 attributes every hooked call by the caller's IAT slot. 505 lines, **0 errors, 0 unattributed calls** → all lines below are VERIFIED.
Session: launch → login → host co-op → 11-task public search → join a game by lobby id → play ~40 s → quit.

| Item | Value |
|---|---|
| Login | Auth_Login EXCHANGE_CODE → Connect_Login EPIC; deployment prefix `2a8b` (same as run 1) |
| Host lobby | CreateLobby v8, 5 members, INVITEONLY then `SetPermissionLevel PUBLICADVERTISED`, invites on, BucketId "Epic", host migration on, RTC on; attributes as in E5 (`10000012=15500`, `10000015=16780550`, `1000008a=-2`, `1000003c=14`, …) |
| Member attrs | `platform=2`, `team=1`, `name`, `player_id` (redacted), `connected` |
| Public search | **11 searches**, MaxResults 200. Every one: `10000012 == 15500`, `10000017 <= 0`, `10000050 <= 1`, `1000008c == 0`, `1000008d == 0`. Varying: `10000015` window (exact 16780550 / 16780544–16780550 / 16777216–16780544 / exact 83886080) × `1000008a` ∈ {-2, 2, 17, 39}. **No bucket filter, no platform filter.** |
| Result counts | 18, 20, 123, then 0 for the other 8 (only `1000008a = -2` returns games) |
| Buckets of inspected results | "Steam" ×3, "Epic" ×3, **"" (empty) ×1** |
| Join | search-by-id (MaxResults 1, SetLobbyId) → 1 result → JoinLobby v3 |
| Gameplay | EOS P2P, socket name = lobby id, channel 0, reliability 0 (unreliable-unordered), 9–1150 B, ~140–200 packets / 10 s each way |

Run-1 conclusions are all confirmed by run 2's clean data.

Decodings (STRONG INFERENCE, from value patterns + `scripts/gamescanner/coopscantasks.scr`):
- `10000015` = (content area << 24) | progress: 0x01xxxxxx = base game, 0x05000000 = another DLC/area; low bits = quest progress (0x0E06 ≈ chapter 14 step 6; host `1000003c = 14`). The three windows match the scan tasks MatchExact / MatchGood / MatchOther.
- `1000008a` = game type/mode (-2 = co-op; 2, 17, 39 = other modes, no results).
- `10000012 = 15500` = build version gate (exact match in every search).
- Empty BucketId lobby: some client creates lobbies without a store bucket (GOG? older build?) — UNKNOWN, worth one look.

## E7 — Console DNS, phased v2 with 10 s TTL cap (2026-10-23 02:35–02:41 local) — `logs/xbox_dns_20261023_023525.tsv`
Result: **INCONCLUSIVE — the console sent almost no queries to the PC.** 11 queries total, all from 192.168.0.195:
- PH0 (boot): xnotify, device.auth, xsts.auth, title.mgt, cert.mgt (xboxlive), xbox.ipv6.microsoft.com, msftconnecttest, ocsp.digicert.
- PH1–PH4 (launch, menu, online menu, host): **zero queries** — not even `pls.dyinglightgame.com`, which DL1 resolved in every earlier run.
- PH5: v20.events.data.microsoft.com; PH6: xsts.auth.xboxlive.com.
Diagnosis (HYPOTHESIS): most lookups bypassed the PC. Evidence: several names appear only as AAAA queries (title.mgt, cert.mgt) with their A queries missing; the console checks `xbox.ipv6.microsoft.com` (IPv6 present). Likely causes: secondary DNS still pointing at the router, and/or an IPv6 DNS server advertised by the router. Phases were also short (host 28 s, play 20 s).
Nothing about EOS can be concluded from E7. Earlier E1/E2 (old observer, same network) did see DL1 names, so the setup has changed or queries are being split.
Fix for the rerun: set both Primary **and Secondary** DNS on the console to 192.168.0.17; if possible disable IPv6 on the router for the test; stay ≥2 min in each game phase.

## E8 — Console DNS, phased v2, Primary+Secondary DNS = PC (2026-10-23 02:46–02:52 local) — `logs/xbox_dns_20261023_024607.tsv`
19 queries, all from 192.168.0.195. Baseline was clean (full shutdown, DL1 not in Quick Resume).
| Phase | Queries |
|---|---|
| PH0 dashboard (2 min) | device.auth, xnotify (xboxlive), xbox.ipv6.microsoft.com, msftconnecttest — **no Epic, no Techland** |
| PH1 launch (02:48:12) | +4.7 s title.mgt.xboxlive.com; **+6.0 s `api.epicgames.dev` (A+AAAA)** together with peoplehub/rta/privacy/social.xboxlive.com (title sign-in burst) |
| PH2–PH4 menu / online menu / host | none |
| PH5 join | v20.events.data.microsoft.com |
| PH6 play | none |
| PH7 quit | watson.events.data.microsoft.com (Windows Error Reporting endpoint — crash or normal termination report; not interpreted) |

Findings:
- **STRONG INFERENCE (upgraded from E2): launching DL1 on the console triggers an EOS (`api.epicgames.dev`) lookup**, with a clean baseline that has none. The Xbox OS on the dashboard does not contact Epic.
- `pls.dyinglightgame.com`, `sessiondirectory.xboxlive.com` and the EOS RTC signaling host were **not** looked up in this run (all were seen in E1/E2). Even with the 10 s TTL cap, no name was re-queried in later phases → the console keeps connections/caches beyond DNS TTL, so DNS cannot attribute traffic to the host/join phases. UNKNOWN whether an online session was actually created in PH4.
- Limit reached: DNS observation can show *that* DL1 talks to EOS, not *what for* (identity only vs lobbies/P2P). Further progress needs either a traffic vantage point or the PC-side relaxed-filter search.
