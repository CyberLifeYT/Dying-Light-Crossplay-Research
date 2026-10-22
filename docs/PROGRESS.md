# Project Progress Report — DL1 PC(Epic/EOS) ↔ Xbox Series X Crossplay
# Updated: 2026-10-22, after the first console DNS observation

## STATUS
**MAJOR BREAKTHROUGH in Phase 1. The architecture question is now largely
answered, and the answer is favourable. Next: attribute the traffic to the
game (phased observation), then prototype.**

---

## VERIFIED FACTS

### PC build (Epic/EOS 2022) — fully characterised
- Chrome Engine 6, branch `dlee_gaas_2021_eos`.
- Identity: EOS only. Session: **EOS Lobby only**. Transport: **EOS P2P**
  (reliable=1, allowRelayed=1). Gameplay: `Net::Repl`, 33 message types,
  `REPL_VERSION = 5`, rejects mismatch with `DisconnectInvalidVersion(0x0D)`.
- Live service `pls.dyinglightgame.com` carries **no** matchmaking/gameplay
  traffic (dockets/MOTDs/rewards/patches only).
- Xbox exports in the PC engine are `ret` stubs (RVA 0x110f0, `c2 00 00`):
  `SetXboxOneMatchHopper`, `SetXbox360TitleId`, `NotifyXboxOffers`,
  `OnShowKeyboardUIXBox`.
- Lobby attributes include `GameId`, `ScannerId`, `PlatformId`, `MasterId`,
  `SerialId`, `PlayersCount`, `PlayerName%d`, `player_id`, `platform`.

### CONSOLE OBSERVATION (user run, 2026-10-22 13:47–13:49) — the breakthrough
Console at **192.168.0.195**, DNS observed via the corrected UDP/53+TCP/53
observer. 30 unique hostnames. Highlight:

| Class | Hostname | Notes |
|---|---|---|
| **EPIC** | `api.epicgames.dev` | **the EOS platform API** |
| **EPIC** | `signaling-service-prod.euw1.live.rtcp.on.epicgames.com` | **EOS RTC signaling** (voice) |
| **TECH** | `pls.dyinglightgame.com` | Techland PLS live service |
| XBOX | `sessiondirectory.xboxlive.com` | XBL session directory (session discovery) |
| XBOX | `peoplehub`, `profile`, `social`, `userpresence`, `rta`, `xnotify`, `privacy`, `instance.mgt`, `inventory`, `titlestorage`, `update`, `assets1`, `assets-srvs`, `xncsi`, `www.xboxlive`, `www.xbox` | OS/account/services |
| MSFT-GEN | `licensing.mp.microsoft.com`, `fs.microsoft.com`, `v20.events.data.microsoft.com`, `assets-srvs-net.trafficmanager.net`, `www.microsoft.com` | OS |
| OTHER | `www.bing.com`, `www.msftncsi.com`, `fg.microsoft.map.fastly.net` | OS |

**=> The Xbox build of DL1 contacts Epic Online Services.** That is a
fundamentally different world from the "disjoint Epic/Microsoft backends"
model I had assumed.

### Legacy Techland backend: DEAD (measured)
`AuthServer*.techland.pl` / `GameListServer.techland.pl` still resolve to AWS
IPs, but **364 TCP+UDP endpoints across 4 hosts → 0 open**
(`dl_scan_techland.py`). The pre-EOS Techland session service is gone.

---

## UNVERIFIED ASSUMPTIONS / OPEN QUESTIONS
1. **Q1** Do the EPIC resolutions come from the *game* or from the Xbox OS /
   a system app? → **phased observation** (next step).
2. **Q2** Does the console's game session live in **EOS Lobby** (like PC) or
   in **XBL sessions** (`sessiondirectory.xboxlive.com`)? If EOS Lobby →
   the two builds are on the same platform. → phased observation.
3. **Q3** Is gameplay **peer-to-peer** or relayed? → `capture_xbox.cmd`.
4. **Q4** Do the two builds use the same EOS ProductId/SandboxId? (PC:
   `ec72fbf877284381a51d0d19d5358df9` / `2c42520d342a46d7a6e0cfa77b4715de`.)
5. **Q5** Is the console's `REPL_VERSION` also 5? And is the content/DLC
   set the same?
6. **Q6** Does `PlatformId` filtering exclude the other platform?

---

## TESTS COMPLETED
| # | Test | Result |
|---|---|---|
| T1 | PC static analysis | DONE |
| T2 | LAN protocol decode | DONE |
| T3–T4 | DNS logger forward + redirect | PASS |
| T5–T7 | LAN prober, pcap triage, Xbox DNS observer self-tests | PASS |
| T8 | Legacy Techland servers alive? | **FAIL — dead (364 endpoints, 0 open)** |
| T9 | EOS endpoint resolution mechanism | DONE — remote signed config service |
| T10 | **Console DNS observation (unphased)** | **DONE — EOS FOUND ON CONSOLE** |
| T11 | pcapng reader + triage | PASS |
| T12 | Router-log parser | PASS |
| T13 | Phased DNS observer + per-phase report | PASS (9/9 regression) |
| T14 | **Phased console observation** | **DONE — EOS CONFIRMED IN GAME PHASES** |
| T15 | Console traffic capture (gameplay transport) | DONE — **Microsoft-relayed** |

---

## CURRENT STATUS

### CRITICAL BREAKTHROUGH (2026-10-22)
The phased console observation was completed and analyzed. **The Xbox build
of Dying Light 1 DOES use Epic Online Services** — `api.epicgames.dev` and
EOS RTC signaling (`signaling-service-prod.euw1.live.rtcp.on.epicgames.com`)
appeared in the game phases (PH1/P3/P4), not just the OS phases.

### Latest Traffic Capture Findings (T15)
The pktmon capture showed gameplay traffic goes through **Microsoft Xbox Live
infrastructure** (UDP port 7844, TCP port 443), NOT direct peer-to-peer.

---

## NEXT ACTIONS
1. Determine if Xbox and PC builds share the same EOS Product ID/Sandbox ID
2. Determine if `PlatformId` filtering excludes cross-platform lobbies
3. Determine if REPL_VERSION=5 matches the Xbox build

---

## PROBABILITY
| Milestone | Before | Now | Why |
|---|---|---|---|
| 1. Proving DNS redirection affects a relevant service | 70% | **85%** | EOS confirmed on console |
| 2. Discovering/joining a cross-platform session | 10% | **45%** | If the console uses EOS Lobby, both sides are on one platform |
| 3. Establishing a stable connection | 8% | **40%** | EOS P2P handles NAT for both |
| 4. Completing the gameplay handshake | 4% | **25%** | Depends on REPL_VERSION + content parity |
| 5. Reliable gameplay with replicated world state | 3% | **15–20%** | Requires version + content alignment |
