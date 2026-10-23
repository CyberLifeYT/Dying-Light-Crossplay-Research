/*
 * eos_logger.js — READ-ONLY logger for Dying Light (Epic) EOS SDK calls.  Frida 17.
 *
 * What it does:   observes arguments / results of selected EOSSDK-Win64-Shipping.dll exports
 * What it never does:
 *   - modify arguments, return values, memory or control flow
 *   - read ClientId / ClientSecret / EncryptionKey (Platform options +0x20/+0x28/+0x38)
 *   - read auth tokens (only the credential *type* enum is logged)
 *   - log user IDs; other players' names are redacted
 *   - log packet payloads (P2P = sizes/counts per socket+channel only)
 *
 * Struct offsets: EOS SDK 1.15.x C headers, x64. Each decoder prints ApiVersion so a layout
 * mismatch is visible; Platform options are only decoded if ProductId matches the known value.
 */
'use strict';

const EOS_DLL = 'EOSSDK-Win64-Shipping.dll';
const KNOWN_PRODUCT_ID = 'ec72fbf877284381a51d0d19d5358df9';
const SUMMARY_MS = 10000;

const ATTR_TYPE = ['BOOL', 'INT64', 'DOUBLE', 'STRING'];
const CMP_OP = ['EQUAL', 'NOTEQUAL', 'GREATERTHAN', 'GREATERTHANOREQUAL', 'LESSTHAN',
  'LESSTHANOREQUAL', 'DISTANCE', 'ANYOF', 'NOTANYOF', 'ONEOF', 'NOTONEOF', 'CONTAINS'];
const VISIBILITY = ['PUBLIC', 'PRIVATE'];
const PERMISSION = ['PUBLICADVERTISED', 'JOINVIAPRESENCE', 'INVITEONLY'];
const EXT_CRED = ['EPIC', 'STEAM_APP_TICKET', 'PSN_ID_TOKEN', 'XBL_XSTS_TOKEN', 'DISCORD_ACCESS_TOKEN',
  'GOG_SESSION_TICKET', 'NINTENDO_ID_TOKEN', 'NINTENDO_NSA_ID_TOKEN', 'UPLAY_ACCESS_TOKEN',
  'OPENID_ACCESS_TOKEN', 'DEVICEID_ACCESS_TOKEN', 'APPLE_ID_TOKEN', 'GOOGLE_ID_TOKEN',
  'OCULUS_USERID_NONCE', 'ITCHIO_JWT', 'ITCHIO_KEY', 'EPIC_ID_TOKEN', 'AMAZON_ACCESS_TOKEN',
  'STEAM_SESSION_TICKET'];
const AUTH_CRED = ['PASSWORD', 'EXCHANGE_CODE', 'PERSISTENT_AUTH', 'DEVICE_CODE', 'DEVELOPER',
  'REFRESH_TOKEN', 'ACCOUNT_PORTAL', 'EXTERNAL_AUTH'];
const REDACT_KEY = /name|player_?id|user_?id|owner|account|^20000083$/i;   // values of these keys are personal data (20000083 carries a SteamID64)

function ts() { return new Date().toISOString(); }
function log(tag, msg) { console.log(ts() + '\t' + tag + '\t' + msg); }
function nameOf(table, v) { return (v >= 0 && v < table.length) ? table[v] : ('?' + v); }
function cstr(p) {
  try { return p.isNull() ? '<null>' : JSON.stringify(p.readCString()); } catch (e) { return '<bad ptr>'; }
}
function guard(tag, fn) {
  return function (args) { try { fn.call(this, args); } catch (e) { log('ERR', tag + ': ' + e); } };
}

// EOS_Lobby_AttributeData { int32 ApiVersion; const char* Key; union Value (8); int32 ValueType }
function attrData(p) {
  if (p.isNull()) return '<null attr>';
  const keyRaw = p.add(8).readPointer().readCString();
  const type = p.add(0x18).readS32();
  let val;
  switch (type) {
    case 0: val = p.add(0x10).readS32() ? 'true' : 'false'; break;
    case 1: val = p.add(0x10).readS64().toString(); break;
    case 2: val = p.add(0x10).readDouble().toString(); break;
    case 3: val = cstr(p.add(0x10).readPointer()); break;
    default: val = '?';
  }
  if (REDACT_KEY.test(keyRaw) && (type === 3 || type === 1)) val = '<redacted>';
  return JSON.stringify(keyRaw) + ' ' + nameOf(ATTR_TYPE, type) + ' = ' + val;
}

function hex(p, len) {
  try { return Array.from(new Uint8Array(p.readByteArray(len))).map(b => b.toString(16).padStart(2, '0')).join(' '); }
  catch (e) { return '<unreadable>'; }
}

const eos = Process.getModuleByName(EOS_DLL);

// EOSSDK folds identical export stubs: one address can serve several exports (e.g. LobbySearch_SetParameter
// == LobbyModification_SetPermissionLevel). Attribute each call by decoding the caller's `call [rip+disp32]`
// (FF 15) and looking the IAT slot up in the importing modules' import tables.
const slotName = new Map();
['engine_x64_rwdi.dll', 'gamedll_x64_rwdi.dll'].forEach(m => {
  try {
    Process.getModuleByName(m).enumerateImports().forEach(i => {
      if (i.slot && i.module && i.module.toLowerCase().startsWith('eossdk')) slotName.set(i.slot.toString(), i.name);
    });
  } catch (e) { log('INFO', 'imports unavailable for ' + m + ': ' + e); }
});
function calledName(ret) {
  try {
    const insn = ret.sub(6);
    if (insn.readU8() === 0xff && insn.add(1).readU8() === 0x15) return slotName.get(ret.add(insn.add(2).readS32()).toString()) || null;
  } catch (e) { /* unreadable */ }
  return null;   // indirect call through a register: cannot attribute
}
let unattributed = 0;
function hook(name, callbacks) {
  let addr;
  try { addr = eos.getExportByName(name); } catch (e) { log('INFO', 'export not found: ' + name); return; }
  const wrapped = {};
  if (callbacks.onEnter) wrapped.onEnter = function (a) {
    const n = calledName(this.returnAddress);
    this.mine = (n === name);
    if (n === null) unattributed++;
    if (this.mine) callbacks.onEnter.call(this, a);
  };
  if (callbacks.onLeave) wrapped.onLeave = function (r) {
    if (!callbacks.onEnter) this.mine = (calledName(this.returnAddress) === name);
    if (this.mine) callbacks.onLeave.call(this, r);
  };
  Interceptor.attach(addr, wrapped);
}
setInterval(function () { if (unattributed) { log('INFO', 'unattributed calls (indirect) skipped: ' + unattributed); unattributed = 0; } }, 60000);

// ---------- platform / auth ----------
hook('EOS_Platform_Create', { onEnter: guard('Platform_Create', function (a) {
  const o = a[0];
  const product = o.add(0x10).readPointer().readCString();
  if (product !== KNOWN_PRODUCT_ID) { log('PLATFORM', 'layout mismatch (ProductId field != known), not decoding'); return; }
  const dep = o.add(0x50).readPointer();
  const depStr = dep.isNull() ? '<null>' : dep.readCString();
  log('PLATFORM', 'ApiVersion=' + o.readS32() + ' ProductId=' + product +
      ' SandboxId=' + cstr(o.add(0x18).readPointer()) +
      ' DeploymentId=' + depStr.substring(0, 4) + '…(len ' + depStr.length + ')' +
      ' bIsServer=' + o.add(0x30).readS32() + ' Flags=0x' + o.add(0x58).readU64().toString(16));
}) });

hook('EOS_Connect_Login', { onEnter: guard('Connect_Login', function (a) {
  const o = a[1]; const cred = o.add(8).readPointer();
  log('AUTH', 'Connect_Login ApiVersion=' + o.readS32() +
      ' ExternalCredentialType=' + (cred.isNull() ? '<null>' : nameOf(EXT_CRED, cred.add(0x10).readS32())));
}) });

hook('EOS_Auth_Login', { onEnter: guard('Auth_Login', function (a) {
  const o = a[1]; const cred = o.add(8).readPointer();
  log('AUTH', 'Auth_Login ApiVersion=' + o.readS32() +
      ' LoginCredentialType=' + (cred.isNull() ? '<null>' : nameOf(AUTH_CRED, cred.add(0x18).readS32())));
}) });

// ---------- lobby creation / advertisement ----------
hook('EOS_Lobby_CreateLobby', { onEnter: guard('CreateLobby', function (a) {
  const o = a[1]; const v = o.readS32();
  log('CREATE', 'ApiVersion=' + v + ' MaxLobbyMembers=' + o.add(0x10).readU32() +
      ' PermissionLevel=' + nameOf(PERMISSION, o.add(0x14).readS32()) +
      ' bPresenceEnabled=' + o.add(0x18).readS32() + ' bAllowInvites=' + o.add(0x1c).readS32() +
      ' BucketId=' + cstr(o.add(0x20).readPointer()) +
      ' bDisableHostMigration=' + o.add(0x28).readS32() + ' bEnableRTCRoom=' + o.add(0x2c).readS32());
  log('CREATE', 'raw[0..0x60]=' + hex(o, 0x60));
}) });

hook('EOS_LobbyModification_SetBucketId', { onEnter: guard('SetBucketId', function (a) {
  log('MODIFY', 'SetBucketId ApiVersion=' + a[1].readS32() + ' BucketId=' + cstr(a[1].add(8).readPointer()));
}) });

function addAttr(tag) {
  return { onEnter: guard(tag, function (a) {
    const o = a[1];
    log('MODIFY', tag + ' ApiVersion=' + o.readS32() + ' ' + attrData(o.add(8).readPointer()) +
        ' visibility=' + nameOf(VISIBILITY, o.add(0x10).readS32()));
  }) };
}
hook('EOS_LobbyModification_AddAttribute', addAttr('AddAttribute'));
hook('EOS_LobbyModification_AddMemberAttribute', addAttr('AddMemberAttribute'));
hook('EOS_LobbyModification_SetPermissionLevel', { onEnter: guard('SetPermissionLevel', function (a) {
  log('MODIFY', 'SetPermissionLevel ' + nameOf(PERMISSION, a[1].add(4).readS32()));
}) });
hook('EOS_LobbyModification_SetInvitesAllowed', { onEnter: guard('SetInvitesAllowed', function (a) {
  log('MODIFY', 'SetInvitesAllowed ' + a[1].add(4).readS32());
}) });

// ---------- search ----------
hook('EOS_Lobby_CreateLobbySearch', { onEnter: guard('CreateLobbySearch', function (a) {
  log('SEARCH', 'CreateLobbySearch ApiVersion=' + a[1].readS32() + ' MaxResults=' + a[1].add(4).readU32());
}) });
hook('EOS_LobbySearch_SetParameter', { onEnter: guard('SetParameter', function (a) {
  const o = a[1];
  log('SEARCH', 'SetParameter ' + attrData(o.add(8).readPointer()) + ' op=' + nameOf(CMP_OP, o.add(0x10).readS32()));
}) });
hook('EOS_LobbySearch_SetLobbyId', { onEnter: guard('SetLobbyId', function () {
  log('SEARCH', 'SetLobbyId (search by id)');
}) });
hook('EOS_LobbySearch_Find', { onEnter: guard('Find', function () { log('SEARCH', 'Find'); }) });
hook('EOS_LobbySearch_GetSearchResultCount', { onLeave: guard('GetSearchResultCount', function (r) {
  log('SEARCH', 'ResultCount=' + r.toUInt32());
}) });

// ---------- results the game inspects (deduplicated) ----------
const seenResult = new Map();
function noteResult(line) { seenResult.set(line, (seenResult.get(line) || 0) + 1); if (seenResult.get(line) === 1) log('RESULT', line); }

hook('EOS_LobbyDetails_CopyInfo', {
  onEnter: function (a) { this.out = a[2]; },
  onLeave: guard('CopyInfo', function (r) {
    if (r.toInt32() !== 0) return;
    const i = this.out.readPointer(); const v = i.readS32();
    noteResult('Info ApiVersion=' + v + ' Permission=' + nameOf(PERMISSION, i.add(0x18).readS32()) +
      ' AvailableSlots=' + i.add(0x1c).readU32() + ' MaxMembers=' + i.add(0x20).readU32() +
      ' BucketId=' + cstr(i.add(0x28).readPointer()) + ' RTC=' + i.add(0x34).readS32());
  })
});
function copyAttr(tag) {
  return {
    onEnter: function (a) { this.out = a[2]; },
    onLeave: guard(tag, function (r) {
      if (r.toInt32() !== 0) return;
      const attr = this.out.readPointer();          // EOS_Lobby_Attribute { ApiVersion; Data*; Visibility }
      noteResult(tag + ' ' + attrData(attr.add(8).readPointer()));
    })
  };
}
hook('EOS_LobbyDetails_CopyAttributeByKey', copyAttr('Attr'));
hook('EOS_LobbyDetails_CopyMemberAttributeByKey', copyAttr('MemberAttr'));

// ---------- join / lifecycle ----------
hook('EOS_Lobby_JoinLobby', { onEnter: guard('JoinLobby', function (a) {
  log('JOIN', 'JoinLobby ApiVersion=' + a[1].readS32() + ' bPresenceEnabled=' + a[1].add(0x18).readS32());
}) });
['EOS_Lobby_LeaveLobby', 'EOS_Lobby_DestroyLobby', 'EOS_Lobby_PromoteMember', 'EOS_Lobby_SendInvite',
 'EOS_Lobby_UpdateLobby'].forEach(n => hook(n, { onEnter: guard(n, function () { log('LOBBY', n); }) }));

// ---------- P2P: metadata only, summarised ----------
const p2p = new Map();
function bump(key, n) {
  const s = p2p.get(key) || { count: 0, bytes: 0, min: 1e9, max: 0 };
  s.count++; s.bytes += n; s.min = Math.min(s.min, n); s.max = Math.max(s.max, n); p2p.set(key, s);
}
hook('EOS_P2P_SendPacket', { onEnter: guard('SendPacket', function (a) {
  const o = a[1]; const sock = o.add(0x18).readPointer();
  const name = sock.isNull() ? '?' : sock.add(4).readCString();
  bump('TX ' + name + ' ch' + o.add(0x20).readU8() + ' rel' + o.add(0x34).readS32(), o.add(0x24).readU32());
}) });
hook('EOS_P2P_ReceivePacket', {
  onEnter: function (a) { this.sock = a[3]; this.ch = a[4]; this.len = a[6]; },
  onLeave: guard('ReceivePacket', function (r) {
    if (r.toInt32() !== 0) return;                  // EOS_Success only
    bump('RX ' + this.sock.add(4).readCString() + ' ch' + this.ch.readU8(), this.len.readU32());
  })
});
setInterval(function () {
  if (p2p.size === 0) return;
  p2p.forEach((s, k) => log('P2P', k + ' count=' + s.count + ' bytes=' + s.bytes + ' size=' + s.min + '..' + s.max));
  p2p.clear();
}, SUMMARY_MS);

log('INFO', 'eos_logger loaded; EOSSDK base ' + eos.base + ' (read-only hooks)');
