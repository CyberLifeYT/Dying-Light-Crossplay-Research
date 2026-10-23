# PC networking architecture (engine_x64_rwdi.dll, build 1.55 / 2026-07-05)

## Class layers (from RTTI vftable names — VERIFIED)
```
CLobby  ──►  CLobbyCrossPlatform  ──►  CLobbyEpic
 (generic)    (EOS layer: crossplatform/*.cpp)  (Epic-store layer)

CLobbyCrossPlatform owns: EOS platform handle, CEosAuthenticator (EOS Connect / ProductUserId),
  CNatInfoEos, CQosEndpoint on CEosSocket("DyingLightQoS"), CInviteProcessorEos, CVoiceChatEos
CLobbyEpic owns: CEpicAuthenticator (EOS Auth / Epic account), CEpicFriendsManager,
  AchievementsEpic, CLeaderboardEpic, CLobbyStorageEpic::DlcOwnershipTask, CLobbyProfileEpic, CLobbyPresenceEpic
Factory: CEosFactory<CLobbyFactoryEpic> (vft 0x1808a79d0)
  +0x0  → CLobbySessionEos::Scanner (EOS internet scanner)
  +0x8  → CLobbyScannerLan
  +0x10 → CreateSocket(raw): raw=1 → CSocket (Winsock UDP), raw=0 → CEosSocket("DyingLightMultiplayer")
Sessions (factory 0x18067ddf0): mode 0 → CLobbySessionSingle, 1 (Mpl) → CLobby vfunc +0x188 → CLobbySessionEos, 2 (Lan) → CLobbySessionLan
Addresses: CInetAddr, CInetAddrEos, CInetAddrMultiPlatform
```

## Flow
| Step | Mechanism | Label |
|---|---|---|
| Startup → platform init | engine init `0x1802298c0` → `CLobbyCrossPlatform` ctor `0x180699540` → `EOS_Platform_Create` | VERIFIED (calls) |
| Authentication | `EOS_Connect_Login` (`0x18069fc40`) + `EOS_Auth_Login` (`0x1806b74c0`); credential type not yet read | VERIFIED calls / UNKNOWN credential type |
| Lobby creation (Mpl) | `CLobby::CreateGame` → `SCreateGameTask` queue → `PrepareSessionCreation` → `SessionNew` → `CLobbySessionEos::Create` → CreationTask (`EOS::Lobby::CreateOptions` built at `0x1806d6940`) | VERIFIED chain; option values UNKNOWN |
| Lobby advertisement | `CLobbySessionEos::Updater` `0x1806da280`: `EOS_LobbyModification_AddAttribute` (loop over generic list) + `SetBucketId` + `EOS_Lobby_UpdateLobby` | VERIFIED calls; keys/bucket string UNKNOWN |
| Discovery | `CLobby::CreateScanner(type)`: 0 = LAN, 1 = EOS, 2 = both; EOS search via `CLobbySessionEos::SearchTask` (`0x1806aacd0`) + `EOS_LobbySearch_SetParameter` (`0x1806ceac0`); criteria from `scripts/gamescanner/*.scr` | VERIFIED structure; filter values UNKNOWN |
| Join | `CLobby::JoinGame` → `SJoinGameTask` → `CLobbySession::Join` → `CLobbySessionEos::JoinTask` (`EOS_Lobby_JoinLobby`) or `CLobbySessionLan::Join` | VERIFIED |
| Transport (Mpl) | `CSessionSocketEos` send (`0x1806c4250`) → `EOS_P2P_SendPacket`; accept `0x1806c2b40` | VERIFIED |
| Transport (LAN discovery) | `CSocket`: `socket(AF_INET, SOCK_DGRAM, 0)`; header must contain GameId `0x43364457` ("C6DW") and PlatformId 1 | VERIFIED |
| Transport (LAN gameplay) | `CLobbySessionLan` master address is IPv4 (`inet_ntop(AF_INET)`); socket presumably raw | STRONG INFERENCE |
| Gameplay protocol | `Net::Repl`, `REPL_VERSION = 5`, 33 message types, `DisconnectInvalidVersion (0x0d)` | VERIFIED in 2026-10-22 notes, not re-checked |
| Live service | PLS `https://pls.dyinglightgame.com`, login route `/auth/login/epic/` | VERIFIED (strings) |

## Controlled by binary vs external
- Binary (patchable on PC): lobby mode, scanner type, LAN header checks (GameId/PlatformId), attribute values, search filters, REPL version check.
- External (not patchable): EOS deployment scoping, backend-enforced `AllowedPlatformIds` search restriction, EOS P2P authorization, Xbox Live services, everything in the Xbox retail binary.
