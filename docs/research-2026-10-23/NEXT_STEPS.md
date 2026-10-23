# Next steps (priority order)

## 1. PC runtime EOS logging (read-only) — highest value
Goal: record what the PC game actually sends to EOS:
`EOS_Platform_Create` options (deployment choice only — never log ClientSecret), `EOS_Lobby_CreateLobby` options (MaxMembers, PermissionLevel, BucketId, AllowedPlatformIds, bCrossplayOptOut, RTC), every `EOS_LobbyModification_AddAttribute` key/value, `SetBucketId`, every `EOS_LobbySearch_SetParameter` key/value/comparison, search result counts, `EOS_Connect_Login` credential *type* (not token).
Method: Frida script or x64dbg conditional log breakpoints on the EOSSDK exports. Run the unmodified game; host and search for a co-op game.
Needs: install Frida or x64dbg — **requires user approval**.
Stop/go: tells us whether PC filtering is client-side (patchable) or platform-restricted.

## 2. Clean console observation (E4 in NETWORK_EXPERIMENTS.md)
Goal: attribute EOS usage to DL1 and see whether co-op peers are reached via Epic relays or Xbox Live/Teredo.
Needs: a vantage point (router mirror port or PC hotspot), Wireshark (install needs approval).

## 3. LAN reality check
a) Look through Xbox DL1 menus for any LAN/local network option (screenshots).
b) PC↔PC LAN test (second PC or VM) on 1.55 to confirm LAN gameplay works.
If (a) is negative, Route C is closed for crossplay.

## Later
- Decompile `CLobbySessionEos::CreationTask` (`0x1806d6940`) and the attribute producers to recover BucketId/attribute keys statically (cross-check of #1).
- Locate who reads `--deploy=` (deployment selection).
- Re-verify `REPL_VERSION` handshake (`0x1807007c0`, `0x180718550`).

## Update after E5 (2026-10-23)
1. ✅ Done (run 1). Re-run with logger v2 once to get clean, attributed data (also catches CopyInfo buckets reliably).
2. **Decision needed:** relaxed-filter search experiment — drop/alter the `10000012` (and optionally `10000015`) filter in one search and log only result buckets + platform values. Changes what the client asks Epic for (read-only query, but a modified client talking to a live service → ToS risk).
3. Clean console capture (E4) and the Xbox LAN menu check remain open.
