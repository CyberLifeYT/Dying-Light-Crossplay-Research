# Open questions

1. Does Xbox DL1 create EOS lobbies, or only Xbox Live (MPSD/SmartMatch) sessions? — UNKNOWN
2. If EOS: same ProductId/Sandbox/Deployment as PC? — UNKNOWN
3. What BucketId, attributes and search filters does the PC use? (`PlatformId` attribute exists) — UNKNOWN → NEXT_STEPS #1
4. Are lobbies created with `AllowedPlatformIds` / `bCrossplayOptOut`? (EOS SDK 1.15.5 in use) — UNKNOWN
5. Which EOS Connect credential type does PC use (Epic ID token expected)? — UNKNOWN
6. Console `REPL_VERSION` and content/DLC parity? — UNKNOWN
7. Does Xbox DL1 have any LAN mode? — UNKNOWN
8. Is LAN *gameplay* on PC raw UDP end-to-end, and does it still work on 1.55? — STRONG INFERENCE / untested
9. Which console DL1 build is installed (Xbox One build via BC, or next-gen)? — UNKNOWN
10. What reads `CLobby+0x3b0/+0x3b4` outside the lobby module, if anything? — UNKNOWN (low priority)
11. How is `--deploy=` used to pick among the three embedded deployment IDs? — UNKNOWN
12. Meaning of numeric attribute keys (`0x10000015` content/DLC mask?, `0x1000008a` search task/game type?, `0x1000003c`, `0x10000052/88/89`). — partially observed (E5)
13. Does any non-PC bucket (e.g. "Xbox", "XboxOne", "Live") exist in deployment 2a8b…? — UNKNOWN; test = relaxed-filter search
14. What value of `platform` (member attr) would a console use? PC Epic = 2. — UNKNOWN
Answered by E5: Q3 (bucket "Epic", filters listed), Q4 (v8 options → no AllowedPlatformIds, STRONG INFERENCE), Q5 (EPIC credential, exchange-code Auth login).
15. Which client creates lobbies with an empty BucketId (seen once in E6)? — UNKNOWN
Confirmed by E6: search gates = version (10000012) + content/progress window (10000015) + mode (1000008a) + misc; no platform/bucket gate on PC.
16. Console DL1 uses EOS at launch (E8, strong inference) — for identity only, or also lobbies/P2P? — UNKNOWN; DNS observation exhausted
Answered 2026-10-23 (static, see ATTRIBUTE_MAP.md): Q12 numeric keys = XLAST properties from data/spa/game.gameconfig (MP_Game_Version, MP_Progress, MP_DlcArea, MP_Game_Data_Crc, MP_Host_Xuid, …).
17. Console build's MP_Game_Version value (PC = 15500; PC client accepts 15500–15599)? — UNKNOWN
9. (update 2026-10-23) Console DL1 version shown on the Xbox: **1.7.0.8** (user-reported). Mapping to MP_Game_Version / REPL_VERSION still UNKNOWN — console patch numbering differs from PC (PC exe 1.55.0.0, MP_Game_Version 15500).
