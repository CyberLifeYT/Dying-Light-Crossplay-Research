# File inventory (as of 2026-10-23)

## Installed game — `D:\Games\DyingLight` (621 files, 37.07 GB) — READ ONLY
| File | Size | Version / PE timestamp | SHA-256 (prefix) | Role |
|---|---|---|---|---|
| DyingLightGame.exe | 1,020,480 | 1.55.0.0 / 2026-07-05 | 767F5686513D4008 | launcher; imports engine, gamedll, filesystem; no EOS imports |
| engine_x64_rwdi.dll | 11,374,144 | "1.0.0.0na" / 2026-07-05 | 4B3FFF9E83884A9B | Chrome Engine 6 (`builder_dlee_gaas_2021_eos`); lobby, sessions, sockets, Net::Repl; 148 EOS imports; Winsock imports |
| gamedll_x64_rwdi.dll | 31,789,632 | – / 2026-07-05 | A37265E56A77924C | game logic; 2 EOS imports; calls `IGame::SetXboxOneMatchHopper`, `SetXbox360TitleId` |
| EOSSDK-Win64-Shipping.dll | 20,023,248 | SDK 1.15.5-24099393 / 2023-02-16 | FADE5524958D2DE8 | Epic Online Services SDK |
| steam_api64.dll | 298,856 | 08.02.21.95 | A44E5537939AE4EE | present, **not imported** by any game binary |
| filesystem_x64_rwdi.dll | 350,784 | 2026-07-05 | BBE095E3E5D1D5D2 | logging/filesystem |
| `.egstore\*.manifest` (3) | | | | Epic install manifests (binary, not yet parsed) |
| `DW\Data\*.rpack`, `*.csb`, `DW_DLC*` | ~37 GB | | | assets; DLC presence markers `DLCn_present.txt` |

Engine EOS identifiers (public): ProductId `ec72fbf877284381a51d0d19d5358df9`, SandboxId `2c42520d342a46d7a6e0cfa77b4715de`. Three 32-hex deployment IDs, a ClientId and a ClientSecret are also embedded (in the `CLobbyCrossPlatform` constructor, `0x180699540`) — **deliberately not recorded**. A `--deploy=` command-line switch exists.

## Research folder — `C:\Users\cyber\AppData\Local\Temp\opencode` (4,094 files, ~2.6 GB)
About half is unrelated (Android TV launcher APKs, Dead-Fest, cinesrc, screenshots). Dying Light material:

| Item | Format | Notes |
|---|---|---|
| `ghidra_dl/dlproj.gpr/.rep` | Ghidra 12.1.3 project | 3 programs: engine (SHA-256 matches installed file — VERIFIED), gamedll, EOSSDK |
| `ghidra_scripts/`, `gs2/` | Ghidra Java scripts | earlier dump scripts (DumpFuncs2, CallersOf, EosFuncs…) |
| `dl_funcs1..11.txt`, `dl_lobbyfuncs.txt`, `dl_lanfuncs.txt`, `dl_lanfmt.txt`, `dl_gamefuncs1.txt` | Ghidra decompiler C | batches of decompiled functions |
| `dl_refs.txt`, `dl_feas1..5.txt` | STR/REF listings | string → referencing function |
| `dl_eos_callers.txt`, `dl_eosdecomp.txt`, `dl_eosfuncs.txt`, `eos_imports*.txt` | Ghidra output | EOS import callers; EOSSDK export stubs |
| `engine_all.txt`, `gamedll_all.txt`, `*_net.txt`, `*_imports.txt` | extracted strings / imports | |
| `dlpak/data/*.scr` | extracted game scripts | `network.scr` (GamePort 26100, dead Techland servers), `restclient.scr` (PLS), game-scanner tasks |
| `PROGRESS.md`, `CROSSPLAY_FEASIBILITY.md`, `LAN_PROTOCOL.md`, `DNS_ASSESSMENT.md`, `XBOX_OBSERVATION_RUNBOOK.md` | notes (2026-10-22) | contain some errors — see `DECISION_LOG.md` |
| `dl_*.py` (capture, dns logger, lan probe, session probe…) | Python tools | not executed in this session |
| `xbox_dns.log`, `xbox_phased.log`, `xbox_trace.pcapng/.etl` | console observations | pcap only contains console DNS + multicast |

## This notes folder
- `tools/XrefDecomp.java`, `tools/LobbyMap.java`, `tools/showfn.py` — read-only Ghidra headless scripts used 2026-10-23.
- `evidence/` — decompiler output from 2026-10-23, credential strings redacted.

Headless invocation used (read-only, no re-analysis):
```
C:\Tools\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat C:\Users\cyber\AppData\Local\Temp\opencode\ghidra_dl dlproj -process engine_x64_rwdi.dll -noanalysis -readOnly -scriptPath <tools> -postScript XrefDecomp.java <out.c> <hexaddr> ...
```
(The .bat launcher splits arguments on `|` and `,`; LobbyMap uses `+` as list separator.)

## Tools available on this machine
Ghidra 12.1.3, JDK 21, Python 3.13 (`pefile`, `scapy`), `pktmon`. **Missing:** x64dbg/Frida, Wireshark/tshark, IDA.
