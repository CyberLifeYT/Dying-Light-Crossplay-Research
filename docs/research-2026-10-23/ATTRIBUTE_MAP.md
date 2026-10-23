# EOS lobby attribute map (decoded 2026-10-23, static + E5/E6 runtime)

## Source of the IDs — VERIFIED
- The numeric lobby keys are **Xbox Live XLAST property/context IDs**, rendered as hex strings. Format: type nibble (`0x1…` INT32, `0x2…` INT64, `0x4…` string) + ID; system contexts `0x800A` GAME_TYPE, `0x800B` GAME_MODE.
- They come from **`data/spa/game.gameconfig`** in `DW\Data0.pak` (copy: `extracted/game.gameconfig`): an `XboxLiveSubmissionProject` / `GameConfigProject name="Dying Light"`, platform "Xbox 360", **titleId `0x5752083F`**, 149 properties, 5 contexts.
- The game DLL exposes them through class `SLobbyGameSpecificDI` (vftable `0x181635fb8`, 48 slots): constant getters (`mov eax, imm32; ret`) plus name lookups (`PROPERTY_MP_SCENARIO`, `PROPERTY_MP_TEAM1COUNT/2COUNT`, `PROPERTY_MP_CHARACTER_BEN/KIM/EDDIE`, `PROPERTY_MP_BALANCE`, `CONTEXT_MODE_COMPETITIVETDM/OB`). The engine parses XLAST (`CLobbySessionParams::ParseXLastParameters`, `xlast::XLastData`, `MPL_PROPERTY_*`/`MPL_CONTEXT_*` names).

## Keys seen on the wire
| Key | XLAST name | Host value (PC 1.55, E6) | Search filter (E6) |
|---|---|---|---|
| 0x10000012 | **MP_Game_Version** | 15500 | `== 15500` (every search) |
| 0x10000015 | MP_Progress | 16780550 (0x01000E06) | windows: exact / ≥16780544 / 16777216–16780544 / 83886080 |
| 0x10000017 | MP_GameVisibility | 0 / 3 | `<= 0` |
| 0x1000003c | MP_Map_Id | 14 | — |
| 0x1000003d | MP_Characters | 196608 / … | — |
| 0x10000050 | MP_ZombieCanJoin | 0 | `<= 1` |
| 0x10000052 | MP_Rank | 1000 | — |
| 0x10000088 | MP_TrackedQuest | 876 / 1060 | — |
| 0x10000089 | MP_PlotPercent | 100 | — |
| 0x1000008a | **MP_DlcArea** | -2 | `==` -2 / 2 / 17 / 39 (only -2 returned games) |
| 0x1000008b | MP_TrackedQuestTreeCrc | -1934880499 | — |
| 0x1000008c | **MP_Game_Data_Crc** | **0** | `== 0` |
| 0x1000008d | MP_Lobby | 0 | `== 0` |
| 0x100000aa | MP_AntiCheatStatus | 0 | — |
| 0x2000003b | **MP_Host_Xuid** | **0 on PC** | — |
| 0x20000083–87 | MP_ZombiePlayerA–E | A = a SteamID64 on some lobbies, else 0 | — |
| 0x800a | CONTEXT GAME_TYPE (0 RANKED, 1 STANDARD) | 0 | — |
| 0x800b | CONTEXT GAME_MODE (system) | 0 | — |
| 9 | CONTEXT "Mode" (0 Cooperative) | 0 | — |
| string keys | `VISIBILITY`, `players_cnt`, `name`, `owner_id`, `query_id` | | — |
| member attrs | `platform` (Epic = 2), `team`, `name`, `player_id`, `connected` | | — |

## Version check — VERIFIED
- `15500` (`0x3c8c`) is a hard-coded constant in gamedll (15 sites).
- Server-side gate: search parameter `MP_Game_Version == 15500`.
- Client-side gate: `LobbyCallback_OnGameFound` (`gamedll 0x180a14930`) accepts a found game only if `version == 15500 || (unsigned)(version - 15500) < 100` → 15500–15599.
- In-session gate (engine): `REPL_VERSION = 5` / `DisconnectInvalidVersion` (from earlier notes).

## Implications
- STRONG INFERENCE: the session schema is Techland's cross-platform XLAST schema (it even has `MP_Host_Xuid`), so a console build would most likely publish the **same keys**. Attribute *format* is not a crossplay obstacle.
- `MP_Game_Data_Crc` is published and filtered as 0 → no data-CRC gate on PC (VERIFIED for PC).
- Remaining gates for a console lobby to appear on PC: (1) being in the same EOS deployment, (2) `MP_Game_Version` value, (3) `MP_DlcArea`/`MP_Progress` compatibility, then (4) `REPL_VERSION` and content parity in-session.
- UNKNOWN: the console build's `MP_Game_Version` value.
