# Dying Light 1 — PC(EOS/2022) ↔ Xbox One Crossplay Feasibility
# Evidence base: REA/Ghidra 12.1.3 decompilation of D:\Games\DyingLight
# Date: 2026-10-22

## VERIFIED FACTS (from binary)

### Build identity
- PC build = Chrome Engine 6, branch `dlee_gaas_2021_eos` (PDB paths in engine+gamedll)
- Engine: 11,374,144 bytes; exports 6,817 names; imports 148 EOS SDK functions
- Game DLL: 31,789,632 bytes; imports only 2 EOS fns; imports 2,387 engine exports
- Official crossplay release = 2022-02-28 (Steam/Epic/GoG/Windows/Mac/Linux ONLY)

### Transport
- Online = EOS P2P: EOS_P2P_SendPacket/ReceivePacket/AcceptConnection/CloseConnection
  - reliable=1, allowRelayed=1 (0x03 / 0x0101 option words at 0x180726970, 0x1806c4250)
  - NAT: EOS_P2P_GetNATType / QueryNATType -> NAT_1/2/3/Unknown (0x1806adf60)
- LAN = raw UDP via CSocket (connectionless only: socket/bind/sendto/recvfrom/select)
  - CLobbyScannerLan broadcast discovery, magic 0x43364457 = "WD6C" (0x1806a78a0)
  - Ports: GamePort(26100), AllSeeingEyePort = GamePort+1  [data/network.scr]
- QoS framing: CQosEndpoint::SendPacket/TryReceivePacket, uint16 packet type header

### Session / matchmaking
- EOS Lobby only: CreateLobby/JoinLobby/UpdateLobby/DestroyLobby/PromoteMember
  - EOS_LobbySearch_Find for matchmaking; attributes via AddAttribute/AddMemberAttribute
- Auth = EOS only: EOS_Connect_Login + EOS_Auth_Login; auth_session_ticket string
  - CLobby::SetLocalAuthenticationType: NoAuthentication(0)/FullAuthentication(1)/LicenceAuthentication(2)
- NO Steam API import in ANY binary. steam_api64.dll present on disk but unimported.
- NO EOS AntiCheat import (0 of 148).
- Legacy VAC strings retained: SteamAuthVACBanned, m_LobbySettings.m_VacSecured,
  &INVITE_TO_VAC_SECURED_GAME_WITH_DISABLED_VAC&  (data model only, no VAC client)
- Legacy master servers (AuthServer*.techland.pl, GameListServer.techland.pl) in
  data/network.scr but NOT referenced anywhere in engine binary => dead config

### Replication (Net::Repl) — Chrome Engine 6 custom layer, ABOVE the transport
- engine/netreplication/netreplmanager.{h,cpp}, netreplobject.cpp
- REPL_VERSION = 5  (FUN_1807181c0(..., "REPL_VERSION", 5) at 0x1807007c0)
- 33 message types (FUN_180718550): IdRequest(1)..LevelInfo(0x20)
  - DisconnectInvalidVersion(0x0d), DisconnectInvalidData(0x0e)
  - 16 compression variants DataCompressed0..F
- Master election is peer-based, deterministic highest-id-wins:
  WannaBeMaster(8) -> AgreeMaster(9)/DisagreeMaster(0xa) -> BecameMaster(0xb) -> AwareOfMaster(0xc)
- Per-object ownership: OwnerId/RequestingId/AuthoritativeId; DoRequestOwnership/DoGiveAuthoritative
- Relevance culling per target (position based)
- Adaptive send intervals (congestion-aware, min/max/clamped)
- Reliable vs unreliable split; unreliable dropped under backpressure
- Host migration: EOS_Lobby_PromoteMember (CLobbySessionEos::Migrator, sessionmigrator.cpp)

### Game-side state
- m_GameSettingsRepl.* : random seed, world life, score/time limits, round count,
  wanted map/spawn, difficulty, blocked quest uid, is-public-match, intermission
- Vehicle m_ReplicationModule.* : gear, fuel, durability, throttle/brake/turn, owner target
- Quest join-sync: Quests::Replication::EClientState (CONNECTED/ACCOMPLISHING/SYNCHRONIZED/
  SYNCHRONIZING/CONNECTING/CONNECTING_HALTED/ACCOMPLISHED) with arbitration counters,
  checkpoint rollback, randomized "fuzz" tiebreak
- 4-player co-op (data comments: "for 4 players")

### XBOX-SPECIFIC CODE IN PC BUILD = STUBS
- Engine exports 4 Xbox APIs: SetXboxOneMatchHopper, SetXbox360TitleId,
  NotifyXboxOffers, OnShowKeyboardUIXBox
- ALL 4 resolve to RVA 0x110f0 => bytes `c2 00 00` = a single `ret`
- => no Xbox platform integration is compiled into this PC build
- (contrast: LobbyGetMasterNetId rva=0x23d880 => real prologue)

## MICROSOFT/TECHLAND POSITION (external, verified)
- Techland support KB 15000043923 (2022-03-02):
  "general cross-platform gameplay or save transfer is not possible for DYING LIGHT.
   PC players from Steam, GOG and Epic games CAN join one another, though!"
- Official site FAQ: "Full cross-play between different platforms (PC, PlayStation, Xbox)
  is not supported."
- Xbox One DL1 = 2016 build, was NEVER updated to EOS. Its live service is Xbox Live /
  Microsoft GDK stack, not EOS. It cannot be updated by third parties.

## CRITICAL ASSESSMENT POINTS
1. Xbox One DL1 (2016) does NOT use EOS. It cannot talk to an EOS lobby.
2. Even if it did, EOS_Lobby + EOS_P2P are Epic-operated services; you cannot
   enroll an arbitrary Xbox client into them.
3. Gameplay wire protocol (Net::Repl REPL_VERSION=5, 33 message types, 16 compression
   variants) is a Chrome Engine 6 internal protocol. The Xbox One 2016 build is CE5/early CE6
   and almost certainly a different REPL_VERSION => DisconnectInvalidVersion(0x0d).
   => The gameplay protocol itself is the hard blocker, independent of auth/session.
4. The LAN path (WD6C magic, raw UDP, port 26100/26101) is the ONLY transport that
   does not require a platform backend. It is where a cross-build attempt must start.
   Community proof-of-concept exists: Gyom03/DL-LAN-join-fix (Frida sendto port rewrite,
   Radmin VPN, DL 1.55). => LAN mode + raw UDP is reachable and hackable.
5. Xbox One is a closed platform: no code signing bypass for the title, no devkit,
   cannot patch the Xbox client. => Any Xbox-side change is impossible.
   => Therefore the PC side must be made compatible with an UNMODIFIABLE Xbox client.
   => Or the Xbox client must be made to talk to something we control.
