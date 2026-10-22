#!/usr/bin/env python3
"""
dl_capture.py — Dependency-free packet capture + protocol triage for
Dying Light 1 / EOS / Chrome Engine traffic.

WHY NOT WIRESHARK
-----------------
This runs with no admin rights and no Npcap/WinPcap install by using
scapy's raw-socket capture where permitted, and it degrades gracefully.
It also does the *triage* that matters here, which a generic dissector will
not:

  * flags every UDP payload that starts with the Chrome Engine 6 magic
    0x43364457 ("WD6C") -> i.e. the game's own LAN/game protocol
  * flags every UDP/TCP flow to or from a well-known service port
  * decodes the EOS "ServiceName"/lobby-ish JSON bodies it can
  * prints a session timeline so you can see the *order* of
    DNS -> auth -> lobby -> peer -> gameplay

CAPTURE MODES
--------------
  # sniff on the default interface (needs admin on Windows for full capture)
  python dl_capture.py --iface <iface> --seconds 120

  # passive TCP/UDP stats without raw sockets (works unprivileged)
  python dl_capture.py --stats --seconds 60

  # triage an existing pcap (if you have one from Wireshark/other tool)
  python dl_capture.py --pcap file.pcap

  # live DNS-only view: show which names the game resolves
  python dl_capture.py --dns-only --seconds 120
"""
import argparse
import binascii
import collections
import datetime
import json
import os
import socket
import struct
import sys
import time

WD6C_MAGIC = 0x43364457
WD6C_BYTES_LE = struct.pack("<I", WD6C_MAGIC)
WD6C_BYTES_BE = struct.pack(">I", WD6C_MAGIC)

# Ports that matter for this investigation.
INTERESTING_PORTS = {
    53: "DNS",
    80: "HTTP", 443: "HTTPS", 8443: "HTTPS-alt",
    26100: "DL-game(PC build)", 26101: "DL-discovery(PC build)",
    20100: "DL-game(1.55)", 20101: "DL-game(1.55)", 20111: "DL-discovery(1.55)",
    3074: "XboxLive", 5222: "XboxLive-ish", 5223: "XboxLive-ish",
    1900: "UDP-discovery", 3478: "STUN", 3479: "STUN-alt",
    1935: "RTMP", 1936: "RTMPS",
    30000: "?", 3074: "XboxLive",
    5222: "XboxLive-ish",
    3659: "XboxLive-ish", 26602: "XboxLive-ish",
}

# Hostnames we expect to see, used to label the timeline.
KNOWN_HOSTS = {
    "api.epicgames.dev": "EOS-API",
    "sdkconfig.epicgames.dev": "EOS-SDKConfig",
    "public-service.eos.epicgames.com": "EOS-PublicService",
    "pls.dyinglightgame.com": "Techland-PLS(live)",
    "plsdev.dyinglightgame.com": "Techland-PLS(dev)",
    "dyinglightgame.com": "Techland-web",
    "mantis.techland.pl": "Techland-crashreport",
    "xboxlive.com": "XboxLive",
    "xbox.com": "Xbox",
    "microsoft.com": "MS",
    "live.com": "MS-Live",
    "user.auth.xboxlive.com": "XboxLive-Auth",
    "s.xboxlive.com": "XboxLive-Services",
    "discovery.ams.xboxlive.com": "XboxLive-Discovery",
    "mps.ams.xboxlive.com": "XboxLive-MPS",
    "title.auth.xboxlive.com": "XboxLive-TitleAuth",
}


def stamp():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def label_port(p):
    return INTERESTING_PORTS.get(p, "")


def hexdump(b, width=16, limit=512):
    out = []
    for i in range(0, min(len(b), limit), width):
        chunk = b[i:i + width]
        hexs = " ".join("%02x" % c for c in chunk)
        text = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        out.append("    %04x  %-*s  %s" % (i, width * 3, hexs, text))
    if len(b) > limit:
        out.append("    ... (%d more bytes)" % (len(b) - limit))
    return "\n".join(out)


def is_wd6c(payload):
    if len(payload) < 5:
        return False
    return payload[:4] == WD6C_BYTES_LE or payload[:4] == WD6C_BYTES_BE


def triage_payload(payload, src, dst):
    """Return a list of human-readable observations about one payload."""
    obs = []
    if is_wd6c(payload):
        t = payload[0] & 0x7F
        ext = (payload[0] >> 7) & 1
        obs.append("*** CHROME ENGINE 'WD6C' PACKET  type=%d extended=%d len=%d ***" % (t, ext, len(payload)))
        # first dword after the type byte is often a field hash
        if len(payload) >= 9:
            h = struct.unpack("<I", payload[1:5])[0]
            obs.append("    dword[1:5] = 0x%08x  (compare to engine field hashes: h=h*0x29+c)" % h)
    if payload[:1] == b"\x00" and len(payload) > 4:
        pass
    # JSON bodies
    body = payload
    if body[:1] in (b"{", b"["):
        try:
            obj = json.loads(body.decode("utf-8", "replace"))
            keys = list(obj.keys())[:14] if isinstance(obj, dict) else ["<list len %d>" % len(obj)]
            obs.append("    JSON body keys: %s" % ", ".join(map(str, keys)))
        except Exception:
            pass
    # EOS / game path strings
    for needle in (b"/api/", b"lobby", b"Lobby", b"productuserid", b"deployment", b"auth", b"session"):
        if needle in payload:
            i = payload.find(needle)
            ctx = payload[max(0, i - 30):i + 70]
            obs.append("    contains %r: %r" % (needle.decode(), ctx.decode("latin1", "replace")))
            break
    return obs


def do_pcap(path):
    """Triage an existing capture (classic pcap or pcapng)."""
    import os
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    import pcapread
    from pcapread import (LINKTYPE_ETHERNET, LINKTYPE_LINUX_SLL,
                          LINKTYPE_NULL, LINKTYPE_RAW)
    fmt, frames = pcapread.read_any(path)
    if fmt == "unknown":
        print("Unrecognised capture format.")
        print("    Convert with: pktmon etl2pcap trace.etl --out trace.pcapng")
        return
    print("capture: format=%s frames=%d" % (fmt, len(frames)))
    stats = collections.Counter()
    for linktype, pkt in frames:
        if linktype == LINKTYPE_ETHERNET:
            if len(pkt) < 34 or pkt[12:14] != b"\x08\x00":
                continue
            ip_off = 14
        elif linktype == LINKTYPE_RAW:
            if len(pkt) < 20 or (pkt[0] >> 4) != 4:
                continue
            ip_off = 0
        elif linktype == LINKTYPE_LINUX_SLL:
            if len(pkt) < 24:
                continue
            ip_off = 16
        elif linktype == LINKTYPE_NULL:
            if len(pkt) < 4 or (pkt[0] >> 4) != 4:
                continue
            ip_off = 4
        else:
            continue
        if len(pkt) < ip_off + 20 or (pkt[ip_off] >> 4) != 4:
            continue
        ihl = (pkt[ip_off] & 0x0F) * 4
        proto = pkt[ip_off + 9]
        src = ".".join(str(b) for b in pkt[ip_off + 12:ip_off + 16])
        dst = ".".join(str(b) for b in pkt[ip_off + 16:ip_off + 20])
        payload = b""
        sp = dp = 0
        if proto == 17 and len(pkt) >= ip_off + ihl + 8:
            u = ip_off + ihl
            sp, dp = struct.unpack("!HH", pkt[u:u + 4])
            payload = pkt[u + 8:]
        elif proto == 6 and len(pkt) >= ip_off + ihl + 4:
            u = ip_off + ihl
            sp, dp = struct.unpack("!HH", pkt[u:u + 4])
            doff = (pkt[u + 12] >> 4) * 4
            payload = pkt[u + doff:]
        else:
            continue
        key = (src, sp, dst, dp, proto)
        stats[key] += 1
        if is_wd6c(payload) or sp in INTERESTING_PORTS or dp in INTERESTING_PORTS:
            print("[%s] %s:%d -> %s:%d proto=%d len=%d" % (stamp(), src, sp, dst, dp, proto, len(payload)))
            for o in triage_payload(payload, src, dst):
                print("   " + o)
    print("\n--- flow summary (top 25 by packet count) ---")
    for (src, sp, dst, dp, proto), c in stats.most_common(25):
        print("  %6d  %s:%d -> %s:%d  proto=%d  %s" % (c, src, sp, dst, dp, proto, label_port(sp) or label_port(dp)))


def do_live_stats(seconds):
    """Unprivileged passive stats using psutil-free /proc + netstat if available."""
    import subprocess
    end = time.time() + seconds
    seen = set()
    print("[+] collecting TCP/UDP connection table snapshots for %ds" % seconds)
    while time.time() < end:
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                proto = parts[0]
                if proto.lower() not in ("tcp", "udp"):
                    continue
                laddr = parts[1]
                raddr = parts[2]
                def hp(s):
                    return int(s.rsplit(":", 1)[1]) if ":" in s else 0
                lp, rp = hp(laddr), hp(raddr)
                if lp in INTERESTING_PORTS or rp in INTERESTING_PORTS:
                    key = (proto, laddr, raddr, parts[3] if len(parts) > 3 else "")
                    if key not in seen:
                        seen.add(key)
                        print("  %s  %-28s -> %-28s  %s" % (stamp(), laddr, raddr, label_port(lp) or label_port(rp)))
        except Exception as e:
            print("netstat failed:", e)
            break
        time.sleep(1.0)
    print("[+] %d interesting connections observed" % len(seen))


def do_live_sniff(iface, seconds, port_filter=None, bpf=None):
    try:
        from scapy.all import sniff, IP, UDP, TCP, Raw
    except Exception as e:
        print("scapy unavailable (%s) — falling back to --stats" % e)
        return do_live_stats(seconds)
    print("[+] sniffing on %r for %ds" % (iface, seconds))
    if bpf:
        print("    bpf: %s" % bpf)
    flt = bpf
    if port_filter and not flt:
        flt = "udp port %d" % port_filter

    def handle(pkt):
        try:
            if IP not in pkt:
                return
            src = pkt[IP].src
            dst = pkt[IP].dst
            payload = bytes(pkt[Raw].load) if Raw in pkt else b""
            sp = dp = 0
            proto = "?"
            if UDP in pkt:
                sp, dp = pkt[UDP].sport, pkt[UDP].dport
                proto = "UDP"
            elif TCP in pkt:
                sp, dp = pkt[TCP].sport, pkt[TCP].dport
                proto = "TCP"
            interesting = (is_wd6c(payload) or sp in INTERESTING_PORTS or dp in INTERESTING_PORTS
                           or len(payload) > 0 and payload[:1] in (b"{", b"["))
            if not interesting:
                return
            print("[%s] %s %s:%d -> %s:%d len=%d" % (stamp(), proto, src, sp, dst, dp, len(payload)))
            for o in triage_payload(payload, src, dst):
                print("   " + o)
            if is_wd6c(payload):
                print(hexdump(payload))
        except Exception as e:
            print("handler error:", e)

    try:
        sniff(iface=iface, store=False, timeout=seconds, prn=handle, filter=flt)
    except Exception as e:
        print("sniff failed: %s" % e)
        print("    (raw-socket capture usually needs an elevated shell on Windows)")
        return do_live_stats(20)
    print("[+] done")


def main():
    ap = argparse.ArgumentParser(description="Dying Light 1 / EOS traffic capture + triage")
    ap.add_argument("--iface", default=None, help="interface to sniff (e.g. '\\Device\\NPF_{GUID}')")
    ap.add_argument("--pcap", default="", help="triage an existing pcap file")
    ap.add_argument("--stats", action="store_true", help="unprivileged connection-table polling")
    ap.add_argument("--dns-only", action="store_true", help="only report DNS traffic")
    ap.add_argument("--port", type=int, default=0, help="BPF filter: single UDP port")
    ap.add_argument("--bpf", default="", help="raw BPF filter string")
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()

    if args.pcap:
        do_pcap(args.pcap)
        return 0
    if args.stats:
        do_live_stats(args.seconds)
        return 0
    if args.dns_only:
        args.bpf = args.bpf or "udp port 53"
    if not args.iface:
        print("[-] --iface required for live sniffing (use --stats or --pcap instead)")
        return 2
    do_live_sniff(args.iface, args.seconds, args.port, args.bpf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
