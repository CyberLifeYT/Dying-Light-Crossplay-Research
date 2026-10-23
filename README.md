# Dying Light 1 Crossplay Research

**Investigating cross-platform co-op between Epic Games Store PC and Xbox One / Xbox Series X|S**

> **Project status (2026-10-23): Concluded — PC (Epic) ↔ Xbox co-op is not achievable with the unmodified Xbox game.** See [Conclusion (2026-10-23)](#conclusion-2026-10-23) and [`docs/research-2026-10-23/CONCLUSION.md`](docs/research-2026-10-23/CONCLUSION.md).

This project investigates whether it is technically possible to enable cooperative multiplayer between the PC version of *Dying Light* distributed through the Epic Games Store and the Xbox One version of the game running on Xbox One or Xbox Series X|S.

The goal is to understand how the game's lobby system, authentication, session discovery, and peer-to-peer networking work, then determine whether the PC and Xbox versions can communicate using a compatible approach.

This repository documents findings, experiments, reverse-engineering notes, unanswered questions, and potential avenues for further research. It is intended to be useful even if the investigation ultimately concludes that cross-platform play is not feasible without changes to the game or its platform services.

---

## Table of Contents

- [Project Overview](#project-overview)
- [The Goal](#the-goal)
- [Current Status](#current-status)
- [Test Environment](#test-environment)
- [What Has Been Investigated](#what-has-been-investigated)
- [Reverse-Engineering Findings](#reverse-engineering-findings)
- [Networking and Service Observations](#networking-and-service-observations)
- [How Crossplay Might Work](#how-crossplay-might-work)
- [Main Technical Challenges](#main-technical-challenges)
- [Research Roadmap](#research-roadmap)
- [How to Contribute](#how-to-contribute)
- [Reporting Experiments](#reporting-experiments)
- [Security and Responsible Research](#security-and-responsible-research)
- [Limitations](#limitations)
- [Frequently Asked Questions](#frequently-asked-questions)
- [Disclaimer](#disclaimer)

---

## Project Overview

*Dying Light* supports cooperative multiplayer, but owning the game on two different platforms does not automatically mean that those versions can play together.

The PC and Xbox versions may differ in several important areas:

- Platform authentication and ownership checks.
- Lobby creation and matchmaking.
- How players invite and join one another.
- Network address discovery and connection establishment.
- Peer-to-peer transport and NAT traversal.
- Game version compatibility and protocol validation.
- Platform-specific networking APIs and services.

The purpose of this project is to investigate those differences rather than assume that a single workaround, such as changing DNS settings or forwarding network traffic, will be enough.

The initial focus is on the Epic Games Store PC build and the Xbox One game running through backward compatibility on Xbox Series X|S.

### Core research question

**Can the PC and Xbox versions establish a mutually compatible co-op session, and if not, which specific technical incompatibility prevents it?**

Answering this question requires more than discovering the game's server addresses. We need to understand the session setup, authentication requirements, and gameplay connection protocol.

## The Goal

The ideal outcome would be a documented, reproducible method for two players to play together:

| Player | Platform | Game version |
|---|---|---|
| Player 1 | Windows PC | Epic Games Store |
| Player 2 | Xbox One or Xbox Series X\|S | Xbox One version |

The investigation will prioritize solutions that do not require modifying the Xbox console, bypassing platform security, or distributing proprietary game files.

Possible approaches to investigate include:

1. Determining whether both builds use compatible gameplay networking protocols.
2. Understanding whether their lobby and session systems can interoperate.
3. Investigating whether an existing LAN implementation provides a useful research path.
4. Determining which platform authentication mechanisms are required.
5. Evaluating whether a compatibility layer or intermediary service could realistically help.

These are research directions, not confirmed solutions.

## Current Status

The following table separates established observations from unresolved questions.

| Area | Current finding |
|---|---|
| PC game analysis | The Epic PC build's `engine_x64_rwdi.dll` has been inspected using reverse-engineering tools. |
| EOS functions | EOS P2P and lobby-related function names are present in the analyzed PC binary. |
| Lobby implementation | Several lobby, session, and LAN-related functions and strings have been identified. |
| Authentication | Authentication-related functions and an `auth_session_ticket` string have been identified. |
| Xbox-specific code | Xbox-related strings and a `SetXboxOneMatchHopper` symbol are present in the PC binary. |
| Xbox LAN availability | The tested Xbox version does not expose a LAN multiplayer option in its normal game interface. |
| Network observations | Some potentially relevant service domains have been observed, but their roles are not yet fully established. |
| PC-to-Xbox connection | Not demonstrated. |
| Working crossplay method | None confirmed. |
| Join handshake (2026-10-23) | **Verified:** joining requires an exact, ordered match of build fingerprints (`REPL_VERSION`, RTTI IDs/CRCs/sizes CRCs, multiplayer data CRC, per-file CRCs). |
| Versions (2026-10-23) | PC Epic 1.55.0.0 (`MP_Game_Version` 15500); Xbox reports 1.7.0.8. |
| Overall (2026-10-23) | **Not achievable** under current constraints — see the conclusion section. |

**Important:** The presence of a function name or string does not prove that the corresponding code path is used during normal gameplay. Static analysis provides leads that must be confirmed through control-flow analysis, runtime observation, or reproducible testing.

---

## Test Environment

The initial investigation uses the following environment.

### PC

- Operating system: Windows.
- Game distribution: Epic Games Store.
- Game: *Dying Light 1*.
- Analysis target: `engine_x64_rwdi.dll`.
- Analysis methods: Binary string inspection, function identification, decompilation, and network observation.

### Xbox

- Console: Xbox Series X.
- Game: Xbox One disc version of *Dying Light 1*.
- Multiplayer interface: Online co-op with a Friends Only option.
- LAN: No LAN option exposed in the tested game interface.

### Network

- Home broadband connection.
- PC connected over Wi-Fi.
- DNS and domain observations used as an initial method of identifying services contacted during testing.

The exact game build numbers, executable hashes, tool versions, and repeatable network capture procedures still need to be recorded. Contributors should add these details when they become available.

---

## What Has Been Investigated

### 1. PC binary inspection

The PC game's `engine_x64_rwdi.dll` was inspected to identify functions and strings related to multiplayer.

The purpose was to find concrete implementation details that could help answer questions such as:

- How are lobbies created and joined?
- Does the game use Epic Online Services for any multiplayer functions?
- Is there a separate LAN session implementation?
- How is authentication selected?
- Are platform-specific session paths present?
- Does the game validate a replication or protocol version?

This produced several useful leads, documented in the reverse-engineering section below.

### 2. DNS and network observations

Network observation was investigated to identify domains contacted while the game and platform were active.

Potentially relevant domains appeared in the observations, but the initial captures did not reliably distinguish separate test phases. As a result, these observations are preliminary.

They should not be treated as proof that every listed service is directly used by the game. Some traffic may originate from the game launcher, platform services, or the Xbox operating system.

The next step is to repeat captures with clearly separated phases and appropriate timestamps.

### 3. Xbox game access and inspection

The Xbox One disc runs on Xbox Series X through backward compatibility.

Accessing the retail game files for conventional PC-style reverse engineering has not been established. Xbox retail game packages have platform-specific protection and signing requirements, so the disc should not be assumed to provide a directly readable PC executable.

A PC DLL analysis alone cannot establish how the Xbox build implements its multiplayer code.

### 4. LAN multiplayer investigation

The PC binary contains names associated with a LAN lobby scanner and LAN session joining.

This is worth investigating because LAN networking can sometimes avoid an online matchmaking service during discovery and session establishment.

However, three separate things must be distinguished:

1. The game contains LAN-related code.
2. The PC build can actually use that code in a supported configuration.
3. The Xbox build can participate in the same LAN session and speak a compatible gameplay protocol.

Only the first point is currently supported by the identified binary strings and symbols. The second and third remain unverified.

---

## Reverse-Engineering Findings

The following findings come from symbol and string extraction performed on the PC build's `engine_x64_rwdi.dll`.

### Epic Online Services: P2P and lobby functions

The extracted function list includes:

| Function | Address in analyzed binary | Research relevance |
|---|---|---|
| `EOS_P2P_SendPacket` | `0x180352c00` | Potential P2P packet transmission path. |
| `EOS_P2P_ReceivePacket` | `0x1803540c0` | Potential P2P packet reception path. |
| `EOS_P2P_AcceptConnection` | `0x1803520d0` | Potential P2P connection acceptance path. |
| `EOS_P2P_GetNATType` | `0x180351f60` | NAT type-related functionality. |
| `EOS_P2P_QueryNATType` | `0x1803541c0` | NAT type query functionality. |
| `EOS_Lobby_CreateLobby` | `0x180353160` | Lobby creation-related functionality. |
| `EOS_Lobby_JoinLobby` | `0x1803527c0` | Lobby joining-related functionality. |
| `EOS_Lobby_PromoteMember` | `0x180352900` | Lobby member promotion functionality. |
| `EOS_Platform_Create` | `0x18026ffc0` | EOS platform initialization-related functionality. |

These names provide concrete entry points for further investigation.

They do **not** prove that EOS is responsible for every co-op session, that the Xbox build uses the same EOS implementation, or that an Xbox player can join a PC EOS lobby.

#### Suggested next steps

- Inspect cross-references to each function.
- Trace which game functions invoke the EOS lobby APIs.
- Determine whether lobby creation and joining are used in the normal Epic PC co-op flow.
- Identify the relationship between lobby membership and gameplay session creation.
- Determine whether EOS P2P is used for gameplay packets, session setup, or another networking task.
- Record any required product, sandbox, deployment, or authentication configuration without publishing credentials.

### Lobby authentication and session functions

The binary contains the following names:

- `CLobby::SetLocalAuthenticationType`
- `CLobby::SetGameAuthenticationType`
- `CLobby::SessionNew`
- `CLobby::CreateGame`
- `CLobby::JoinGame`
- `CLobby::LeaveGame`
- `CLobbySessionLan::Join`

It also contains the string `auth_session_ticket`.

These findings suggest that lobby authentication and session creation are useful areas to investigate.

The actual meaning of the authentication modes, the data they require, and the way those modes are selected have not yet been fully established.

The presence of `auth_session_ticket` does not establish which platform issues the ticket, whether it is used in the tested Epic build, or whether an Xbox-issued credential would be accepted by the PC build.

**Priority investigation:** Decompile `CLobby::SetGameAuthenticationType` and `CLobby::CreateGame`, then trace how their inputs affect session creation and authentication selection.

### LAN-related functionality

The binary includes:

- `CLobbyScannerLan::ProcessMessage`
- `CLobbyScannerLan::InitializeLocalInetAddress`
- `CLobbyScannerLan::InitializeSocket`
- `CLobbyScannerLan::ReceiveFromNetwork`
- `CLobbySessionLan::Join`

A diagnostic string references an unknown packet type received from a network address and port.

This is evidence that the analyzed binary contains code associated with LAN discovery and joining. It does not reveal the full packet format or prove that LAN gameplay is enabled in the current PC build.

#### Questions to answer

- Which packet types does the LAN scanner recognize?
- How are LAN sessions advertised?
- Which ports and transports are used?
- How does the scanner identify compatible sessions?
- Does joining a LAN session eventually use the same gameplay networking layer as online co-op?
- Are LAN and online sessions different only during discovery, or do they use different authentication and transport implementations?
- Does the relevant code depend on platform-specific functionality?

These questions should be answered from the decompiled code and controlled experiments, not inferred from function names alone.

### Version and Xbox-related strings

Other extracted strings include:

- `REPL_VERSION`
- `DisconnectInvalidVersion`
- `SetXbox360TitleId`
- `SetXboxOneMatchHopper`

These are useful leads for investigating version compatibility and platform-specific session configuration.

For example, `REPL_VERSION` may be relevant to replication or protocol compatibility, but its exact purpose must be confirmed by tracing its references and the code that consumes it.

Similarly, `SetXboxOneMatchHopper` is evidence of an Xbox-related code symbol in the analyzed binary. It does not establish that the PC game uses Xbox matchmaking or that the two platforms share a matchmaking backend.

---

## Networking and Service Observations

The following domains appeared in preliminary network observations:

| Domain | Initial interpretation | Confidence |
|---|---|---|
| `api.epicgames.dev` | Potentially associated with Epic services. | Low for attribution to a specific game action. |
| `signaling-service-prod.euw1.live.rtcp.on.epicgames.com` | Potentially associated with Epic real-time communication signaling. | Low until the traffic is correlated with a controlled action. |
| `pls.dyinglightgame.com` | Potentially related to Dying Light services. | Low until its purpose is established. |
| `sessiondirectory.xboxlive.com` | Xbox session-directory-related service domain. | Low for determining which component initiated the request. |

These are observations to investigate, not confirmed endpoints for a crossplay bridge.

### Why attribution matters

A domain appearing in a DNS log does not prove that the game itself initiated the request. The launcher, operating system, platform networking layer, or other background activity could be responsible.

To improve confidence, future captures should separate the following phases:

1. Platform idle, with the game closed.
2. Launcher open, with the game closed.
3. Game started but not in a lobby.
4. Host creates a co-op session.
5. Client attempts to join.
6. Session ends or the game disconnects.

Each phase should have a separate timestamped record. Where possible, correlate DNS observations with process-level connection data and the action performed in-game.

Do not publish personal IP addresses, account identifiers, authentication headers, session tokens, or other secrets in public logs.

---

## How Crossplay Might Work

There are several possible approaches, each with different requirements and obstacles.

### Approach A: Existing cross-platform infrastructure

The first question is whether the game already contains a supported cross-platform session path.

If the PC and Xbox versions use compatible services and session protocols, the problem could be smaller than expected. If their authentication or platform restrictions differ, simply finding the same service domains will not be enough.

**Status:** Not established.

### Approach B: LAN discovery

The PC build contains LAN-related symbols, making LAN discovery worth examining.

If LAN discovery is separate from gameplay transport, a discovery compatibility layer might theoretically help a compatible client find a session. However, if the Xbox version does not expose LAN functionality or uses a different session protocol, discovery alone would not solve the problem.

**Status:** Research lead only. No working PC-to-Xbox LAN session has been demonstrated.

### Approach C: A compatibility proxy or intermediary

An intermediary might theoretically translate certain session-discovery or signaling messages between incompatible clients.

This would only be useful if the underlying authentication and gameplay protocols are sufficiently compatible. It cannot automatically make platform-specific credentials valid or translate arbitrary differences in game state replication.

Before writing a proxy, the project needs to establish:

- The actual messages exchanged during session setup.
- The authentication requirements of each build.
- Whether both builds use compatible gameplay packet formats.
- Whether an intermediary is technically possible without bypassing required platform security.
- Whether the approach is permitted by applicable terms and rules.

**Status:** Hypothetical. No proxy implementation is available.

### Approach D: Game binary modification

Modifying game code could potentially change how sessions are selected or initialized, but retail console executables have platform-specific signing, packaging, and security restrictions.

The project does not currently have a verified method to modify and run a compatible Xbox retail build.

This route should not be treated as a simple extension of PC DLL patching.

**Status:** No demonstrated solution.

---

## Main Technical Challenges

### 1. Authentication

The game may rely on platform-specific ownership verification, identity, session tickets, or other authentication mechanisms.

A credential being present in one platform's session does not imply that it is accepted by another platform.

The project must identify the authentication flow before proposing a workaround.

### 2. Lobby compatibility

The PC build may create sessions using EOS or another platform-specific service. The Xbox build may use a different matchmaking or session path.

Even if both systems can represent a group of players, their lobby identifiers, join requests, permissions, and metadata may be incompatible.

### 3. Gameplay networking

Successful lobby discovery is not equivalent to successful co-op gameplay.

The clients must also establish a usable gameplay connection and exchange compatible packets. Differences in replication formats, packet sequencing, game versions, or session state could prevent the game from working after a lobby is joined.

### 4. NAT traversal and connectivity

Peer-to-peer networking can involve signaling, address discovery, NAT traversal, and relay services.

A DNS change alone does not automatically change these mechanisms. Redirecting a service may also fail if the expected TLS identity, authentication, protocol, or server behavior does not match.

### 5. Version compatibility

The PC and Xbox builds may differ in executable versions, game data, protocol versions, or platform-specific logic.

The `REPL_VERSION` and `DisconnectInvalidVersion` strings provide leads for investigation, but the relevant compatibility checks have not yet been confirmed.

### 6. Limited access to the Xbox implementation

The PC DLL can be inspected directly, but it cannot stand in for the Xbox executable.

Without reliable information about the Xbox networking path, some of the most important assumptions will remain unresolved.

---

## Research Roadmap

The following roadmap prioritizes learning whether a feasible route exists before investing time in a large implementation.

### Phase 1 — Document the baseline

- [ ] Record exact PC and Xbox game versions.
- [ ] Record executable and DLL hashes where appropriate.
- [ ] Document the normal co-op hosting and joining process on each platform.
- [ ] Record the available multiplayer options in each build.
- [ ] Repeat network observations using clearly separated test phases.
- [ ] Separate confirmed observations from hypotheses.

### Phase 2 — Understand the PC lobby flow

- [ ] Decompile `CLobby::SetGameAuthenticationType`.
- [ ] Decompile `CLobby::CreateGame`.
- [ ] Trace `CLobby::SessionNew`.
- [ ] Trace `CLobby::JoinGame`.
- [ ] Identify the call paths to EOS lobby functions.
- [ ] Determine how the game chooses a session implementation.
- [ ] Investigate the relationship between lobby creation and gameplay networking.

### Phase 3 — Investigate LAN functionality

- [ ] Trace `CLobbyScannerLan::InitializeSocket`.
- [ ] Trace `CLobbyScannerLan::ProcessMessage`.
- [ ] Trace `CLobbySessionLan::Join`.
- [ ] Identify LAN discovery packet structure and handling.
- [ ] Determine whether LAN discovery and gameplay use separate code paths.
- [ ] Verify which LAN modes are actually available in the PC game.
- [ ] Record any platform-specific limitations.

### Phase 4 — Establish the Xbox side

- [ ] Document the Xbox session creation and joining behavior from observable results.
- [ ] Determine which platform services are involved using controlled observations.
- [ ] Look for reliable documentation of the Xbox build's session and transport requirements.
- [ ] Identify any evidence of shared or incompatible session protocols.
- [ ] Avoid assuming that the PC build's implementation is identical to the Xbox build.

### Phase 5 — Evaluate feasibility

- [ ] Compare the known PC and Xbox authentication flows.
- [ ] Compare session discovery and joining requirements.
- [ ] Determine whether gameplay networking is compatible.
- [ ] Identify the smallest unresolved incompatibility.
- [ ] Decide whether a testable compatibility experiment is justified.

### Phase 6 — Prototype only if justified

- [ ] Define a narrow experiment with a measurable success criterion.
- [ ] Avoid handling real authentication secrets where possible.
- [ ] Test one protocol layer at a time.
- [ ] Record failures and negative results.
- [ ] Do not describe crossplay as working until both players complete a reproducible co-op session.

The roadmap is intentionally allowed to end with a feasibility conclusion. Determining that a proposed approach cannot work is a useful research result.

---

## How to Contribute

Contributions are welcome, particularly from people with experience in game networking, binary analysis, Epic Online Services, console networking, and protocol debugging.

Useful contributions include:

- Reproducible decompilation findings.
- Cross-references and call graphs for identified functions.
- Explanations of lobby and session selection logic.
- Controlled network captures with sensitive information removed.
- Documentation of relevant public APIs and platform limitations.
- Evidence that confirms or disproves a proposed approach.
- Improvements to the research log and test methodology.

### Good contribution practices

1. Explain how a finding was obtained.
2. Identify the exact game build and tool used.
3. Include function names and addresses when useful.
4. Separate direct evidence from interpretation.
5. Describe what would falsify your conclusion.
6. Avoid sharing proprietary game binaries or sensitive credentials.
7. Keep failed experiments documented so others do not repeat them unnecessarily.

### Questions worth answering

If you have relevant expertise, these are especially valuable questions:

- What does `CLobby::SetGameAuthenticationType` actually select?
- How does `CLobby::CreateGame` choose a lobby or session implementation?
- Is `CLobbySessionLan::Join` part of a complete gameplay path or only session discovery?
- Which call sites use the identified EOS lobby and P2P functions?
- What exactly checks `REPL_VERSION`?
- Is there evidence that the Xbox and PC versions share a compatible gameplay transport?
- Which differences would require a translation layer, and which would make crossplay impractical?

A small, well-supported finding is more valuable than an unverified claim that crossplay should work.

---

## Reporting Experiments

Use a consistent template when documenting an experiment.

### Experiment template

**Title:** Short description of the test.

**Date:** When the experiment was performed.

**Game builds:** Exact versions tested.

**Environment:** Platform, operating system, and relevant network setup.

**Objective:** The question the experiment is intended to answer.

**Method:** The steps performed, including tools and settings.

**Expected result:** What would support the hypothesis.

**Actual result:** What happened, including errors or failures.

**Interpretation:** What the result supports and what it does not prove.

**Confidence:** Low, medium, or high, with an explanation.

**Next step:** The smallest useful follow-up test.

### Evidence labels

To keep the project reliable, use these labels in issues and notes:

- **Confirmed:** Reproduced or directly demonstrated.
- **Observed:** Seen in a log, binary, or test, but not fully interpreted.
- **Hypothesis:** A plausible explanation that still needs testing.
- **Disproved:** A specific hypothesis contradicted by reproducible evidence.
- **Unknown:** Insufficient evidence to reach a conclusion.

For example, identifying `EOS_Lobby_CreateLobby` in a binary is an **observed** result. Proving that a particular in-game action calls it is a stronger finding. Proving that the resulting lobby can be joined by an Xbox player is a separate test.

---

## Security and Responsible Research

This project focuses on interoperability research, documentation, and understanding network behavior.

Contributors should:

- Use their own legitimate game copies and accounts.
- Avoid publishing account credentials, session tokens, or authentication tickets.
- Never upload private network captures without reviewing them for sensitive information.
- Avoid distributing proprietary game assets or executable files.
- Avoid bypassing console security or platform access controls as a shortcut.
- Respect the applicable platform terms, game terms, and laws.
- Use synthetic or redacted data when sharing protocol examples.

If an experiment requires a real authentication token, document the token's role without publishing its value. Never assume a token can be safely transferred between platforms.

---

## Limitations

This repository currently documents an investigation, not a working modification or crossplay tool.

At present:

- No successful PC-to-Xbox co-op session has been demonstrated.
- The Xbox networking implementation has not been fully reverse-engineered.
- The preliminary network observations do not conclusively attribute every domain to the game.
- The presence of EOS functions in the PC binary does not establish cross-platform compatibility.
- LAN-related code does not establish that LAN multiplayer is enabled on Xbox.
- No working DNS redirection, proxy, or protocol translation solution has been verified.

These limitations may change as new evidence is collected.

---

## Frequently Asked Questions

### Is crossplay working?

Not yet. The project is investigating whether it is technically possible. There is no confirmed method at this time.

### Why investigate the PC DLL?

The PC DLL contains identifiable networking, lobby, session, and authentication-related symbols. These provide concrete entry points for understanding the PC implementation.

### Does the presence of EOS prove Xbox crossplay is possible?

No. It establishes that EOS-related functions are present in the analyzed PC binary. It does not establish which functions are used in a given session or whether the Xbox build uses compatible services.

### Can DNS redirection enable crossplay?

Not by itself in any demonstrated way. DNS changes can affect where a client attempts to connect, but they do not automatically solve authentication, session compatibility, or gameplay protocol differences.

### Could LAN functionality be the answer?

Possibly, but this remains unproven. The PC binary contains LAN-related symbols, while the tested Xbox game interface does not expose a LAN option. The compatibility of the underlying gameplay protocol is unknown.

### Why not simply use a proxy?

A proxy can only help with the parts of the protocol it can understand and legitimately handle. It cannot automatically make incompatible authentication systems, lobby formats, or gameplay protocols interoperable.

### What is the most useful next step?

Inspect `CLobby::SetGameAuthenticationType` and `CLobby::CreateGame`, then trace the actual session-creation flow. In parallel, gather better evidence about the Xbox networking path. These investigations may reveal whether a prototype is justified.

### Is a negative result still useful?

Absolutely. A reproducible finding that the two versions require incompatible authentication or gameplay protocols would help establish the project's technical limits and save others from repeating unsuccessful approaches.

---

## Disclaimer

This is an independent, community research project. It is not affiliated with, endorsed by, or supported by Techland, Epic Games, Microsoft, or Xbox.

All trademarks belong to their respective owners.

No working crossplay solution is currently claimed or guaranteed. The purpose of this repository is to document evidence, investigate feasibility, and share reproducible findings.

---

## Final Note

The objective is not to assume that crossplay can be made to work at any cost. The objective is to investigate the technical barriers carefully, publish what is learned, and determine whether a safe, reproducible, and technically realistic solution exists.

Every verified finding helps move that goal forward — including findings that rule out a proposed approach.

---

## Latest Findings (2026-10-22) — Phased Console Observation and Traffic Capture

> **Correction (2026-10-23):** the 2026-10-22 capture did **not** contain console gameplay traffic. Re-analysis of `xbox_trace.pcapng` shows only 18 flows involving the console (192.168.0.195), all DNS to the PC plus multicast — the PC is not on the console's network path. The `198.41.x.x:7844` flows were the PC's own traffic (that range belongs to Cloudflare, not Xbox Live). The "gameplay goes to Xbox Live relays on UDP 7844" and "Is gameplay peer-to-peer? No" rows below are therefore **withdrawn**. Also, PH0 of that phased run was not a clean baseline (Dying Light was likely in Quick Resume). The EOS-at-launch observation was later confirmed with a clean baseline (see below).

### Bottom line

- The Xbox Series X build of *Dying Light 1* **does contact Epic Online Services** — `api.epicgames.dev` and the EOS RTC signaling host were observed while the game was running.
- The console **also** uses Xbox Live services (`sessiondirectory.xboxlive.com`) and Techland's live service (`pls.dyinglightgame.com`).
- A 44,302-frame packet capture of an active console session showed gameplay traffic going to **Microsoft Xbox Live infrastructure on UDP port 7844** (plus TCP/443), with **no high-volume UDP flow to a non-Microsoft peer**.

### Game-attributable DNS (phased observer)

| Class | Hostname | First seen | Meaning |
|---|---|---|---|
| EPIC | `api.epicgames.dev` | PH0/PH1 | EOS platform API |
| EPIC | `signaling-service-prod.euw1.live.rtcp.on.epicgames.com` | PH0 | EOS RTC signaling (voice) |
| TECH | `pls.dyinglightgame.com` | PH1 | Techland PLS live service |
| XBOX | `sessiondirectory.xboxlive.com` | PH0 | Xbox Live session directory |

> Caveat: several of these names are also resolved by the Xbox OS/dashboard services, so phase attribution alone is not conclusive. They are reported together with the traffic capture rather than as proof of the game's session backend.

### Gameplay transport (pktmon capture)

| Flow | Protocol | Interpretation |
|---|---|---|
| `… ↔ 198.41.200.233:7844` | UDP | Xbox Live relay infrastructure |
| `… ↔ 198.41.192.227:7844` | UDP | Xbox Live relay infrastructure |
| Multiple hosts on TCP/443 | TCP | Microsoft/Akamai HTTPS services |

No direct peer-to-peer UDP flow to a non-Microsoft address was observed during gameplay.

### Feasibility assessment

| Question | Status |
|---|---|
| Does the Xbox build use EOS at all? | **Yes** (EOS API + EOS RTC signaling resolved) |
| Is the EOS ProductId/SandboxId the same as PC? | **Unverified** — PC values are `ec72fbf877284381a51d0d19d5358df9` / `2c42520d342a46d7a6e0cfa77b4715de` |
| Is session discovery EOS Lobby or Xbox Live? | **Mixed evidence** — both appear |
| Is gameplay peer-to-peer? | **No** — observed Microsoft relay (UDP 7844 / TCP 443) |
| Is the console patchable? | **No** — closed platform |

The Microsoft relay and the closed console platform remain the hard blockers. EOS usage on the console is a positive signal for a shared platform, but it is not sufficient on its own.

### Repository layout

```
docs/        Reverse-engineering notes and assessments
scripts/     DNS observer, phase report, traffic triage, LAN tools
evidence/    Raw console DNS logs and the pktmon capture
analysis/    Extracted EOS imports, decompilation excerpts, protocol strings
```

### Tool quick start

```powershell
# 1. Observe which names the console resolves, phase by phase
#    (right-click -> Run as administrator)
scripts\run_xbox_dns_phased.cmd

# 2. Analyse the phase log
python scripts\dl_phase_report.py evidence\xbox_phased.log

# 3. Capture and triage gameplay traffic
scripts\capture_xbox.cmd
python scripts\dl_session_probe.py --pcap evidence\xbox_trace.pcapng
```

### Status

Crossplay is **not achieved**. This repository documents the verified findings, the measurement tools, and the remaining unknowns.

---

## Conclusion (2026-10-23)

**Answer: PC (Epic) ↔ Xbox co-op cannot be made to work with the unmodified Xbox game and the access available to this project.** The decisive obstacle is the game's own join handshake, which requires both players to run layout-identical builds. Full write-up: [`docs/research-2026-10-23/CONCLUSION.md`](docs/research-2026-10-23/CONCLUSION.md).

### How PC co-op actually works (verified from the binary and read-only runtime logging)

```
Epic launcher exchange code → EOS Auth → EOS Connect (credential type EPIC)
→ EOS lobby: BucketId "Epic", XLAST-schema attributes (MP_Game_Version=15500, MP_Progress, MP_DlcArea, …)
→ search: NO platform/bucket filter; MP_Game_Version == 15500 + mode/progress filters  → Steam + Epic lobbies returned
→ client check: found game accepted only if version is 15500–15599
→ join → EOS P2P (socket named by lobby id, unreliable packets, game-level reliability)
→ Net::Repl IdRequest: exact ordered match of verify list
     REPL_VERSION=5, RTTI IDS CRC, RTTI CRCS CRC, RTTI SIZES CRC, data_crc, per-file/quest CRCs
→ replicated gameplay
```

### Key evidence

| Finding | Label |
|---|---|
| Online play = EOS lobbies + EOS P2P; lobby layers `CLobby → CLobbyCrossPlatform → CLobbyEpic` (RTTI class map) | Verified |
| PC cross-store play works by not filtering on store/platform (searches returned "Epic" and "Steam" lobbies) | Verified (runtime) |
| Lobby keys are Xbox Live **XLAST** properties from the game's `data/spa/game.gameconfig` (e.g. `0x10000012` = `MP_Game_Version`, `0x2000003b` = `MP_Host_Xuid`) | Verified |
| Version gate: search `MP_Game_Version == 15500`, client accepts 15500–15599 | Verified |
| Join handshake requires identical, ordered fingerprints including class-size/layout CRCs and multiplayer data CRC | Verified (static) |
| Xbox Dying Light contacts `api.epicgames.dev` on game launch (clean baseline has none) | Strong inference |
| Whether the Xbox build uses EOS **lobbies**, and in which deployment | Unknown |
| A separately built Xbox build (1.7.0.8) produces different layout/data fingerprints than PC 1.55 | Strong inference |

### Routes

| Route | Verdict |
|---|---|
| A — existing services (EOS) | Ruled out in practice: version gates, then the layout-fingerprint handshake |
| B — modify the PC build | Ruled out: can relax PC filters, but can't make the PC's replicated object layout match a different build; spoofing fingerprints would only admit corrupt state |
| C — LAN | Ruled out for crossplay: PC LAN (raw UDP, "C6DW" discovery) uses the same handshake; Xbox shows no LAN option |
| D — Xbox Dev Mode / port | Ruled out: retail games don't run in Dev Mode; a port is a separate multi-year engine-reconstruction project |
| E — relay / protocol bridge | Ruled out: the incompatibility is in game-state serialization, not transport |
| DNS redirection | Observation tool only |

### Corrections to earlier notes
- "Xbox ret-stubs prove there's no Xbox code" — overstated (the same empty function is shared by 40+ callbacks).
- `CreateScanner` types are 0 = LAN, 1 = EOS, 2 = both (earlier notes had them reversed).
- LAN first byte is a header-format selector (0–2), not the message type; `0x43364457` is the FourCC "C6DW", not "WD6C".
- Observed EOS P2P gameplay packets are unreliable-unordered (the game handles reliability), not "reliable=1".
- The 2026-10-22 capture did not contain console gameplay traffic (see the correction above).

### Nearest feasible alternatives
1. Play on the same platform family: PC ↔ PC across Epic, Steam and GOG works today; Xbox ↔ Xbox works on Xbox Live.
2. Ask Techland — only the developer can ship matched builds or console crossplay.

### New material in this update
```
docs/research-2026-10-23/   Conclusion, feasibility, function analysis, attribute map, experiments E1–E8, decision log, open questions
scripts/2026-10-23/         Read-only Ghidra scripts (XrefDecomp, LobbyMap), read-only EOS logger v2 (Frida) + attach runner,
                            phase-marked Xbox DNS observer v2 (+ RUN_XBOX_DNS.cmd launcher)
```
Not published on purpose: decompiled game code, extracted game data files, raw runtime logs (identifiers), and EOS client credentials embedded in the game.
