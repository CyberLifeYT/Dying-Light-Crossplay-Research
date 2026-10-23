# Function analysis — engine_x64_rwdi.dll (image base 0x180000000)

Source: fresh Ghidra headless decompiles, 2026-10-23 (`evidence/engine_targets.c`, `evidence/engine_batch3.c`, `evidence/lobbymap.txt`).

## EOS SDK addresses from earlier notes
All nine (`EOS_P2P_SendPacket 180352c00`, `ReceivePacket 1803540c0`, `AcceptConnection 1803520d0`, `GetNATType 180351f60`, `QueryNATType 1803541c0`, `Lobby_PromoteMember 180352900`, `Lobby_CreateLobby 180353160`, `Lobby_JoinLobby 1803527c0`, `Platform_Create 18026ffc0`) are **exports of EOSSDK-Win64-Shipping.dll** (VERIFIED with pefile) — public entry stubs that null-check and dispatch internally. All nine are **imported by the engine** (VERIFIED). Active-path callers in the engine (from `dl_eos_callers.txt`, consistent with 2026-10-23 class map): SendPacket ← `CSessionSocketEos` `0x1806c4250`; AcceptConnection ← `0x1806c2b40`; CreateLobby ← CreationTask; Platform_Create ← `0x1806ab7d0`, `0x180686d50`.

## CLobby::SetGameAuthenticationType — `0x180266060` (272 B)
```c
void SetGameAuthenticationType(this, int type) {
  CLobby *l = g_Lobby;                     // DAT_180a3b8f8
  if (l && l->m_GameAuthType /*+0x3b0*/ != type) {
     log("[%s] Game authentication type '%s'", {0:"NoAuthentication",1:"FullAuthentication",2:"LicenceAuthentication"});
     l->m_GameAuthType = type;
  }
}
```
- Callers: no direct calls; referenced from a vtable slot (`0x18084f2f8`) → virtual.
- `SetLocalAuthenticationType` `0x180266170` is identical for `+0x3b4`.
- **No reader of +0x3b0/+0x3b4 in the lobby module**; only these setters and the CLobby ctor (`0x18067a7d0`, zeroes both). Readers elsewhere: UNKNOWN (untyped offset scan is too noisy).
- Assessment: STRONG INFERENCE that it's vestigial (Steam/VAC-era). Low priority.

## CLobby::CreateGame — `0x18067ed70` (693 B)
```c
int CreateGame(this, ELobbyMode mode /*0 Single,1 Mpl,2 Lan*/, int publicSlots, int privateSlots, p5, p6) {
  log("[CLobby::CreateGame] mode=%s public=%i private=%i");
  l->m_Sub79->vfunc_0x58(mode);  FUN_180683430(l);  FUN_180694780(l->m_ab, p5);
  l->+0x20c = l->vfunc_0x158();
  task = new SCreateGameTask{type=3, mode, publicSlots, privateSlots, p6};
  enqueue(l->clientTasks /*+0xcc..0xce, CS at +0xd8*/, task);  return 1;
}
```
Caller: IGame thunk `0x180265160` (tail jump). Asynchronous; the work happens in the lobby task loop.

## CLobby::JoinGame — `0x18067e3b0`
Logs `"[CLobby::JoinGame] address %s:%d"` (CInetAddr + port at +0x4c of a 0xb8-byte game-address struct); enqueues `SJoinGameTask` type 2. Caller: IGame thunk `0x1802652c0`.

## CLobby::PrepareSessionCreation — `0x18067bcc0` (4,785 B)
Task-loop worker ("ApplySessionSettings" states). Calls `SessionNew` (`0x18067e060`) and `ProcessAfterSessionCreation` (`0x18067d0a0`); compares the session's 0x21-byte id at session+0xe8 against a null id. Full pseudocode not yet transcribed.

## CLobby::SessionNew — `0x18067e060`
Creates session via factory `0x18067ddf0(mode)` → stored at `CLobby+0x408` (`[0x81]`); then `session->Create(...)` (vtable +0x48).

## CLobby::ProcessAfterSessionCreation — `0x18067d0a0`
Branch on session kind (`vfunc+0x10`): 0 → "Singleplayer" reset; else on state `+0x214`: 3 → "Online" (register with presence via `CLobby[0x7a]->vfunc+0x50`, set state 2), 4 → "Failed" (teardown, error callback).

## CLobby::CreateScanner — `0x18067f500`
`new CLobbyScanner(type)`; type 0|2 → factory +0x8 (**LAN** scanner); type 1|2 → factory +0x0 (**EOS** scanner); enqueue `SCreateScannerTask` (type 9). (Earlier note had the mapping reversed.)

## CLobbySession::Create — `0x18068ee00` / ::Join — `0x18068ef30`
Base-class bookkeeping (slots, params at +0x168, state = 2). Overridden by `CLobbySessionEos::Create` `0x1806bfe20` (queues EOS CreationTask with maxMembers = public+private) and `CLobbySessionLan` (`0x180698af0` create, `0x180698b20` join).

## CLobbySessionLan::Join — `0x180698b20`
Calls base Join, copies the 0xb8-byte game-address (IPv4 sockaddr inside) into session+0x30..0xe0, then `FUN_18068fbc0`. `NotifyMigrate` (`0x180699030`) logs the master address via `inet_ntop(AF_INET)`.

## CLobbyScannerLan::InitializeSocket — `0x1806a5e30`
`socket = factory->CreateSocket(raw=1)` → `CSocket` (`0x1806a43f0`: `socket(AF_INET=2, SOCK_DGRAM=2, 0)`); sets broadcast option (vfunc +0x30, 1); binds trying up to 4 consecutive ports from the configured base; logs "Couldn't bind socket to local address!" on failure.

## CLobbyScannerLan::ReceiveFromNetwork — `0x1806a6130`
Loop: `select`-style poll (vfunc +0x28) → `recvfrom` into 0x578-byte buffer (vfunc +0x20) → `ProcessMessage`.

## CLobbyScannerLan::ProcessMessage — `0x1806a78a0`
```c
hdr = buf[0]; fmt = hdr & 0x7f;           // must be 0,1,2
if (hdr & 0x80) require *(u32*)(buf+1) == len;   // extended header w/ length
ReadHeader(r, 0x43364457 /*"C6DW"*/, 1);  // GameId and PlatformId==1 (FUN_1806a4ef0)
ReadType(r) → 0:FUN_1806a6340  1:FUN_1806a7060  2/3:FUN_1806a7f70  4/5:FUN_1806a9030 (only if scanner mode==1)
```
Field names may be literal or hashed (`h = h*41 + c`), per earlier `LAN_PROTOCOL.md`.

## Other
- `ELobbyGameVisibility`: 0 Visible, 1 VisibleFriendsOnly, 2 InvisibleJoinable, 3 Invisible.
- `ELobbyNAT`: 0 NAT_1, 1 NAT_2, 2 NAT_3, 3 NAT_Unknown.
- Engine export `0x1800110f0` = `ret 0`, shared by 40+ empty `IGame` callbacks (incl. `OnLobbyJoined`, `SetXboxOneMatchHopper`) — linker identical-code folding of empty base virtuals.

## Net::Repl verify-data handshake (2026-10-23) — VERIFIED from code
- `Net::Repl::CReplicatorsManager` ctor `0x1807007c0` calls `AddVerifyData(list@+0x148, "REPL_VERSION", 5)` (`0x1807181c0`). Entry = {name, nameHash (h = h*41 + c), u32 value, bool optional}.
- Exported `IGame::ReplAddVerifyData(const char*, unsigned, bool)` and `ILevel::ReplAddVerifyData` let the game DLL append entries. Game DLL (`src\games\deadisland\game\game\sessiondi.cpp`) adds:
  - `RTTI IDS CRC`, `RTTI CRCS CRC`, `RTTI SIZES CRC` (gamedll `0x180f2da60`) — CRCs over replicated class type IDs, per-class CRCs and **class sizes**;
  - `data_crc` = `IGame::GetMultiplayerFilesCrc()` (gamedll `0x1804caec0`);
  - per-file CRC entries (`File CRC (`… player_zombie_*.dds, `_texts_all.bin`) via `0x18047c5d0`; ` quests crc`; further named entries from objects (vfunc +0x18 value).
- Wire format (engine `AnalyseThreadMessage` `0x1807028d0`, case 7 send / case 1 check): message `IdRequest` (type 1) = `u8 1 | u16 count | count × (u32 nameHash, u32 value)`.
- Check on the master (case 1): count must equal; for each entry in order: nameHash must equal; value must equal unless the entry is optional and either side is 0. Otherwise the join is rejected (→ `DisconnectInvalidVersion`, message 0x0d).
- Message ids: 1 IdRequest, 2 IdReply, 3 Introduction, 4 Acceptance, 5 Authorization, 6 Connected, 7 Master, 8 WannaBeMaster, 9 AgreeMaster, 0xa DisagreeMaster, 0xb BecameMaster, 0xc AwareOfMaster, 0xd DisconnectInvalidVersion, 0xe DisconnectInvalidData, 0x10+ DataCompressed0..F (order from name table `0x180718550`).
