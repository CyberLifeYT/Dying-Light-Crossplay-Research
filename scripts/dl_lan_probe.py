#!/usr/bin/env python3
"""
dl_lan_probe.py — Dying Light 1 LAN session discovery prober, implementing the
Chrome Engine 6 "field-tagged" LAN protocol as decoded from the PC build.

PROTOCOL (decoded from engine_x64_rwdi.dll via Ghidra; see LAN_PROTOCOL.md)
-----------------------------------------------------------------------------
Field-name hashing used by the engine:

    h = 0
    for c in name_ascii:  h = (h * 0x29 + c) & 0xFFFFFFFF

Known field names and hashes:
    "Type"       0x005b8392
    "GameId"     0xfb17484f
    "PlatformId" 0x74616c50
    "ScanId"     0x4e3f086a

A LAN discovery packet is a *field stream*, not a fixed-magic frame:

    hdr_byte                 low 7 bits = message type, bit7 = "extended"
    "GameId"     (literal or hashed)  +  dword 0x43364457   (game/app id)
    "PlatformId" (literal or hashed)  +  dword 1           (platform id)
                                  +  dword 1
    "Type"       (literal or hashed)  +  dword 0..5        (message type)
    ... payload ...

"literal" = 1 byte length + that many ASCII bytes.
"hashed"  = 4 bytes little-endian = hash(name).

The first byte of the stream is the message type; the engine then matches
"GameId", "PlatformId", "Type" in sequence (FUN_1806a4ef0 / FUN_1806a5290),
and dispatches on the type dword (0..5).

This tool:
  * parses and pretty-prints any packet matching this format,
  * can *send* a well-formed probe so a host reveals itself,
  * reports the peer address and the fields it could decode.

It is a network observer/prober only. It performs no authentication, mints no
credentials, and does not modify any game file.
"""
import argparse
import binascii
import datetime
import socket
import struct
import sys
import time

# ---------------------------------------------------------------- field coding

def field_hash(name):
    v = 0
    for c in name.encode("latin1"):
        v = (v * 0x29 + c) & 0xFFFFFFFF
    return v


HASH = {n: field_hash(n) for n in
        ("Type", "GameId", "PlatformId", "ScanId", "Port", "Version",
         "Name", "Id", "Mode", "Players", "MaxPlayers", "Map", "Address")}

# The value the engine expects immediately after the "GameId" field.
GAME_ID_VALUE = 0x43364457          # bytes "WD6C"
PLATFORM_ID_VALUE = 1


def enc_literal(name):
    b = name.encode("latin1")
    return bytes([len(b)]) + b


def enc_hashed(name):
    return struct.pack("<I", field_hash(name))


def build_packet(msg_type, game_id=GAME_ID_VALUE, platform_id=PLATFORM_ID_VALUE,
                 encoding="literal", extra=b"", hdr=None, ext=False):
    """Build a WD6C-style field stream."""
    enc = enc_literal if encoding == "literal" else enc_hashed
    out = bytearray()
    first = (msg_type & 0x7F) | (0x80 if ext else 0x00)
    if hdr is not None:
        first = hdr & 0xFF
    out.append(first)
    out += enc("GameId")
    out += struct.pack("<I", game_id & 0xFFFFFFFF)
    out += enc("PlatformId")
    out += struct.pack("<I", platform_id & 0xFFFFFFFF)
    out += struct.pack("<I", 1)
    out += enc("Type")
    out += struct.pack("<I", msg_type)
    out += extra
    return bytes(out)


# ---------------------------------------------------------------- parsing

def _try_match(buf, off, name):
    """Return (consumed, value_or_None) if `name` matches at off, else None."""
    # literal form: len byte + ascii
    if off < len(buf):
        ln = buf[off]
        if 0 < ln <= 64 and off + 1 + ln <= len(buf):
            cand = buf[off + 1: off + 1 + ln]
            if cand == name.encode("latin1"):
                return (1 + ln, "literal")
    # hashed form: 4 bytes
    if off + 4 <= len(buf):
        v = struct.unpack("<I", buf[off:off + 4])[0]
        if v == field_hash(name):
            return (4, "hashed")
    return None


def parse_packet(buf):
    """
    Best-effort decode following the engine's actual field chain.

    Engine order (from FUN_1806a4ef0 / FUN_1806a5290):
        hdr_byte
        "GameId"      + dword  (expected 0x43364457)
        "PlatformId"  + dword  (expected 1)
                      + dword  (expected 1)
        "Type"        + dword  (0..5)
        ...payload...
    Each name may appear in literal (len+ascii) or hashed (4-byte) form.
    """
    notes = []
    fields = {}
    if not buf:
        return fields, ["empty"]
    hdr = buf[0]
    fields["_hdr"] = hdr
    fields["_type_bits"] = hdr & 0x7F
    fields["_extended"] = (hdr >> 7) & 1
    notes.append("hdr=0x%02x  type_bits=%d  extended=%d"
                 % (hdr, hdr & 0x7F, (hdr >> 7) & 1))
    off = 1

    def take_name(name):
        nonlocal off
        m = _try_match(buf, off, name)
        if m is None:
            return None
        used, how = m
        off += used
        return how

    def take_dword():
        nonlocal off
        if off + 4 > len(buf):
            return None
        v = struct.unpack("<I", buf[off:off + 4])[0]
        off += 4
        return v

    def take_extra_dword():
        """A dword that may be absent; returns (value, present)."""
        nonlocal off
        if off + 4 <= len(buf):
            v = struct.unpack("<I", buf[off:off + 4])[0]
            off += 4
            return v, True
        return None, False

    # --- GameId -------------------------------------------------------------
    how = take_name("GameId")
    if how:
        v = take_dword()
        fields["GameId"] = v
        notes.append("GameId      = 0x%08X %r  [%s encoding]"
                     % (v, struct.pack("<I", v), how))
    else:
        notes.append("no 'GameId' field at offset 1 (format mismatch?)")

    # --- PlatformId ---------------------------------------------------------
    how = take_name("PlatformId")
    if how:
        v = take_dword()
        fields["PlatformId"] = v
        notes.append("PlatformId  = %d  [%s encoding]" % (v, how))
    else:
        notes.append("no 'PlatformId' field after GameId")

    # --- an unnamed dword the engine compares against 1 --------------------
    v, present = take_extra_dword()
    if present:
        fields["_unk1"] = v
        notes.append("unk dword   = %d  (engine compares to 1)" % v)

    # --- Type ---------------------------------------------------------------
    how = take_name("Type")
    if how:
        v = take_dword()
        fields["Type"] = v
        notes.append("Type        = %d  [%s encoding]" % (v, how))
    else:
        notes.append("no 'Type' field (format mismatch?)")

    # --- remaining optional fields -----------------------------------------
    for name in ("ScanId", "Version", "Port", "Name", "Id", "Mode",
                 "Players", "MaxPlayers", "Map", "Address"):
        how = take_name(name)
        if how is None:
            continue
        v = take_dword()
        fields[name] = v
        notes.append("%-11s = 0x%08X (%d)  [%s encoding]" % (name, v, v, how))

    if off < len(buf):
        fields["_payload"] = buf[off:]
        notes.append("remaining payload %d bytes: %s"
                     % (len(buf) - off, binascii.hexlify(buf[off:]).decode()))
    return fields, notes


def hexdump(b, width=16, limit=256):
    out = []
    for i in range(0, min(len(b), limit), width):
        chunk = b[i:i + width]
        hexs = " ".join("%02x" % c for c in chunk)
        text = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        out.append("    %04x  %-*s  %s" % (i, width * 3, hexs, text))
    if len(b) > limit:
        out.append("    ... (%d more bytes)" % (len(b) - limit))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Dying Light 1 LAN discovery prober")
    ap.add_argument("--listen", action="store_true")
    ap.add_argument("--port", type=int, default=26101, help="discovery port (GamePort+1)")
    ap.add_argument("--game-port", type=int, default=26100)
    ap.add_argument("--probe", action="append", default=[], help="host to probe")
    ap.add_argument("--broadcast", action="store_true")
    ap.add_argument("--msg-type", type=int, default=0, help="message type 0..5 to send")
    ap.add_argument("--encoding", default="literal", choices=["literal", "hashed"])
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--raw", default="", help="also dump these hex bytes as if received")
    args = ap.parse_args()

    print("=" * 74)
    print("Dying Light 1 LAN discovery prober (Chrome Engine 6 field protocol)")
    print("  discovery port : %d   game port: %d" % (args.port, args.game_port))
    print("  field hash     : h = h*0x29 + c")
    for n in ("Type", "GameId", "PlatformId", "ScanId"):
        print("      %-11s 0x%08x" % (n, field_hash(n)))
    print("  GameId value   : 0x%08X  ('WD6C')" % GAME_ID_VALUE)
    print("=" * 74)

    if args.raw:
        raw = binascii.unhexlify(args.raw.replace(" ", "").replace(":", ""))
        f, n = parse_packet(raw)
        print("[raw] decoded:")
        for line in n:
            print("   " + line)
        print(hexdump(raw))
        return 0

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    if args.listen:
        try:
            s.bind(("0.0.0.0", args.port))
            print("[+] listening on udp/%d" % args.port)
        except OSError as e:
            print("[-] bind udp/%d failed: %s" % (args.port, e))
            return 1

    pkt = build_packet(args.msg_type, encoding=args.encoding)
    if args.probe or args.broadcast:
        targets = [(h, args.port) for h in args.probe]
        if args.broadcast:
            targets.append(("255.255.255.255", args.port))
        for host, port in targets:
            try:
                s.sendto(pkt, (host, port))
                print("[+] sent %d-byte probe (type=%d, %s encoding) to %s:%d"
                      % (len(pkt), args.msg_type, args.encoding, host, port))
            except OSError as e:
                print("[-] send to %s failed: %s" % (host, e))
        print("    probe hex:\n%s" % hexdump(pkt))

    end = time.time() + args.timeout
    print("[+] listening for %d s ..." % args.timeout)
    got = 0
    while time.time() < end:
        s.settimeout(min(1.0, max(0.1, end - time.time())))
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break
        got += 1
        ts = datetime.datetime.now().isoformat(timespec="milliseconds")
        print("\n[%s] from %s:%d  len=%d" % (ts, addr[0], addr[1], len(data)))
        fields, notes = parse_packet(data)
        for line in notes:
            print("    " + line)
        print(hexdump(data))
    print("\n[+] done. %d packets seen." % got)
    if got == 0:
        print("    NO packets received on udp/%d." % args.port)
        print("    INTERPRETATION:")
        print("      * If the PC game was running in LAN mode and hosting, you should")
        print("        have seen its own beacons -> port or format assumption is wrong.")
        print("      * If the Xbox One emits nothing here, it has no comparable LAN")
        print("        mode, which eliminates approaches D and E entirely.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
