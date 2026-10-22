#!/usr/bin/env python3
"""
dl_xbox_dns.py — Observe which hostnames the Xbox console resolves.

FIXED DESIGN (why the first version saw nothing)
------------------------------------------------
1. The console's custom-DNS setting accepts an **IP address only** — there is
   no port field. The console therefore sends queries to **UDP/53** (and
   possibly TCP/53) on that address. The previous version listened on 5353
   and could never have received a query.
2. Windows Defender Firewall drops inbound UDP/53 by default.
3. Binding UDP/53 on Windows requires an **elevated** process.

So this version:
  * binds UDP/53 *and* TCP/53 (some resolvers fall back to TCP),
  * can install the required inbound firewall rule for you,
  * can re-launch itself elevated automatically,
  * has a --selftest mode so you can prove reachability from another device
    BEFORE involving the console,
  * prints the exact LAN IP you must type into the console.

OBSERVATION ONLY. It forwards queries upstream and logs them. It does not
impersonate any service, does not forge credentials, does not modify the
console, and does not intercept TLS.

USAGE (cmd.exe syntax; PowerShell works too)
---------------------------------------------
  REMEMBER: in cmd.exe use  type  not  Read

  :: 1) self-test that the server works at all (no console needed)
  python dl_xbox_dns.py --selftest

  :: 2) run it (auto-elevates; adds the firewall rule)
  python dl_xbox_dns.py --log xbox_dns.log

  :: 3) on the console: Settings -> Network -> Advanced -> DNS -> Manual
  ::    enter this PC's LAN IP (printed at startup)
  ::    then: Settings -> Network -> Advanced -> Test connection
  ::    (this forces a DNS resolution immediately — much faster than
  ::     waiting for the game to resolve something)
  ::    and/or launch Dying Light and browse menus / start matchmaking

  :: 4) read the log
  type xbox_dns.log
"""
import argparse
import ctypes
import datetime
import os
import socket
import struct
import subprocess
import sys
import threading
import time

IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------- DNS codec

def parse_name(data, off):
    labels = []
    jumped = False
    orig = off
    while True:
        if off >= len(data):
            raise ValueError("truncated name")
        ln = data[off]
        if ln == 0:
            off += 1
            if not jumped:
                orig = off
            break
        if ln & 0xC0 == 0xC0:
            ptr = struct.unpack("!H", data[off:off + 2])[0] & 0x3FFF
            if not jumped:
                orig = off + 2
            off = ptr
            jumped = True
            continue
        off += 1
        labels.append(data[off:off + ln].decode("latin1", "replace"))
        off += ln
        if not jumped:
            orig = off
    return (".".join(labels) + "." if labels else "."), orig


def enc_name(name):
    out = b""
    for l in name.rstrip(".").split("."):
        if l:
            b = l.encode("latin1", "replace")[:63]
            out += bytes([len(b)]) + b
    return out + b"\x00"


def build_error(query, rcode=3):
    tid = query[0:2]
    flags = struct.unpack("!H", query[2:4])[0]
    qd = struct.unpack("!H", query[4:6])[0]
    h = tid + struct.pack("!HHHHH", 0x8000 | (flags & 0x0100) | 0x0080 | rcode, qd, 0, 0, 0)
    off = 12
    for _ in range(qd):
        _, off = parse_name(query, off)
        off += 4
    return h + query[12:off]


def upstream(qname, qtype, server, timeout=4.0):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        q = struct.pack("!HHHHHH", 0x4321, 0x0100, 1, 0, 0, 0)
        q += enc_name(qname) + struct.pack("!HH", qtype, 1)
        s.sendto(q, (server, 53))
        data, _ = s.recvfrom(4096)
        s.close()
        return data
    except Exception:
        return None


# --------------------------------------------------------------- classification

BUCKETS = [
    ("XBOX",  ("xboxlive.com", "xbox.com", "live.com", "xboxservices.com",
               "msftauth.net", "xsts", "xboxgamercard", "party.xboxlive",
               "parties.xboxlive", "xbl")),
    ("EPIC",  ("epicgames.dev", "epicgames.com", "eos-epic", "epicgames.cn",
               "account-public-service")),
    ("TECH",  ("techland.pl", "dyinglightgame.com", "4a-games.com",
               "techland.com", "ntechland.com", "techland-pub", "warnerbros")),
    ("MSFT-GEN", ("microsoft.com", "azure.com", "msft.com", "office.com",
                  "windows.net", "akamaized.net", "azureedge.net", "trafficmanager")),
    ("GOOGLE", ("google.com", "gstatic.com", "googleapis.com", "googlesyndication")),
]


def classify(name):
    n = name.lower()
    for label, keys in BUCKETS:
        for k in keys:
            if k in n:
                return label
    return "OTHER"


# --------------------------------------------------------------- state

class Obs:
    def __init__(self, logpath, upstream_dns):
        self.logpath = logpath
        self.upstream = upstream_dns
        self.fh = open(logpath, "a", encoding="utf-8", buffering=1)
        self.lock = threading.Lock()
        self.counts = {}
        self.names = set()
        self.total = 0

    def record(self, client, proto, qname, qtype, verdict):
        cls = classify(qname)
        with self.lock:
            self.total += 1
            self.counts[cls] = self.counts.get(cls, 0) + 1
            self.names.add(qname.lower())
            self.fh.write("%s\t%s\t%s\t%s\t%d\t%s\t%s\n" % (
                datetime.datetime.now().isoformat(timespec="milliseconds"),
                client, proto, qname, qtype, cls, verdict))

    def close(self):
        self.fh.close()


# --------------------------------------------------------------- servers

def udp_server(obs, bind_ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_ip, port))
    print("[+] UDP/%d listening on %s" % (port, bind_ip))
    while True:
        try:
            data, client = s.recvfrom(4096)
        except OSError:
            break
        def responder(reply, _client, _s=s):
            _s.sendto(reply, _client)
        handle_query(obs, data, client, "UDP", responder)
    s.close()


def tcp_server(obs, bind_ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_ip, port))
    s.listen(16)
    print("[+] TCP/%d listening on %s" % (port, bind_ip))
    while True:
        try:
            c, client = s.accept()
        except OSError:
            break
        threading.Thread(target=tcp_handle, args=(obs, c, client), daemon=True).start()
    s.close()


def recv_all(sock, n):
    """Read exactly n bytes (TCP is a stream; recv may return short)."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def tcp_handle(obs, c, client):
    try:
        c.settimeout(8)
        hdr = recv_all(c, 2)
        if len(hdr) < 2:
            return
        ln = struct.unpack("!H", hdr)[0]
        # NOTE: the 2-byte length prefix is NOT part of the DNS message.
        data = recv_all(c, ln)
        if len(data) < 12:
            return
        def responder(reply, _client, _c=c):
            _c.sendall(struct.pack("!H", len(reply)) + reply)
        handle_query(obs, data, client, "TCP", responder)
    except Exception:
        pass
    finally:
        try:
            c.close()
        except Exception:
            pass


def handle_query(obs, data, client, proto, responder):
    """
    Parse one query, forward it upstream, and reply to the client.

    `responder(reply_bytes)` is how the reply gets back to the requester:
    a sendto() for UDP, a socket write for TCP.
    """
    if len(data) < 12:
        return
    try:
        flags = struct.unpack("!H", data[2:4])[0]
        if flags & 0x8000:
            return
        qd = struct.unpack("!H", data[4:6])[0]
        if not qd:
            return
        off = 12
        qname, off = parse_name(data, off)
        qtype, qclass = struct.unpack("!HH", data[off:off + 4])
    except Exception:
        return
    res = upstream(qname, qtype, obs.upstream)
    cls = classify(qname)
    if res:
        # preserve the client's transaction id
        reply = data[0:2] + res[2:]
        verdict = "ok"
    else:
        reply = build_error(data)
        verdict = "upstream-fail"
    obs.record(client[0], proto, qname, qtype, verdict)
    try:
        responder(reply, client)
    except Exception as e:
        obs.record(client[0], proto, qname, qtype, "send-fail:%s" % e)
    print("    %-8s %-46s %-9s %s" % (client[0], qname[:46], cls, verdict), flush=True)


# --------------------------------------------------------------- helpers

def is_admin():
    if not IS_WINDOWS:
        return os.geteuid() == 0
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_elevated(args):
    """Re-run this script elevated via PowerShell Start-Process -Verb RunAs."""
    if not IS_WINDOWS:
        return False
    exe = sys.executable
    script = os.path.abspath(__file__)
    cmd = [exe, script] + args
    arglist = []
    for c in cmd[1:]:
        arglist.append('"%s"' % c if " " in c else c)
    ps = "Start-Process -FilePath '%s' -ArgumentList %s -Verb RunAs" % (exe, ",".join(arglist))
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
        return True
    except Exception as e:
        print("[-] elevation failed: %s" % e)
        return False


def add_firewall_rule(port):
    if not IS_WINDOWS:
        return
    names = ["DL-XboxDNS-In-UDP", "DL-XboxDNS-In-TCP"]
    for n in names:
        subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule",
                        "name=%s" % n],
                       capture_output=True)
    for proto, n in (("UDP", names[0]), ("TCP", names[1])):
        r = subprocess.run(
            ["netsh", "advfirewall", "firewall", "add", "rule",
             "name=%s" % n, "dir=in", "action=allow",
             "protocol=%s" % proto, "localport=%d" % port, "profile=any"],
            capture_output=True, text=True)
        print("[%s] firewall rule %s" % ("+" if r.returncode == 0 else "!", n))


def remove_firewall_rules():
    if not IS_WINDOWS:
        return
    for n in ("DL-XboxDNS-In-UDP", "DL-XboxDNS-In-TCP"):
        subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule",
                        "name=%s" % n], capture_output=True)


def lan_ips():
    out = []
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-NetIPAddress -AddressFamily IPv4 | "
                              "Where-Object {$_.IPAddress -notlike '127.*' -and "
                              "$_.IPAddress -notlike '169.254*'} | "
                              "Select-Object -ExpandProperty IPAddress"],
                             capture_output=True, text=True, timeout=20)
        out = [x.strip() for x in res.stdout.split() if x.strip()]
    except Exception:
        pass
    if not out:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 53))
            out = [s.getsockname()[0]]
            s.close()
        except Exception:
            pass
    return out


def selftest(port):
    """Prove the server works and is reachable from this host."""
    print("=" * 74)
    print("SELFTEST — verifying the DNS observer works")
    print("=" * 74)
    print("LAN IPs on this machine: %s" % ", ".join(lan_ips()))
    obs = Obs("selftest_dns.log", "1.1.1.1")
    t = threading.Thread(target=udp_server, args=(obs, "127.0.0.1", port), daemon=True)
    t.start()
    time.sleep(0.7)
    # local query
    q = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    q += enc_name("api.epicgames.dev") + struct.pack("!HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
    s.sendto(q, ("127.0.0.1", port))
    try:
        d, _ = s.recvfrom(4096)
        print("[+] local UDP query answered: %d bytes, rcode=%d, answers=%d"
              % (len(d), struct.unpack("!H", d[2:4])[0] & 0xF,
                 struct.unpack("!H", d[6:8])[0]))
        ok = True
    except Exception as e:
        print("[-] local UDP query FAILED: %s" % e)
        ok = False
    s.close()
    obs.close()
    print()
    print("NEXT:")
    print("  1) run the real thing:  python dl_xbox_dns.py --log xbox_dns.log")
    print("  2) from ANOTHER device on the same LAN (a phone is fine) set its")
    print("     DNS to this PC's IP and confirm name resolution works.")
    print("     If it does, the console will work too.")
    print("  3) then set the console's DNS to that IP.")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Observe Xbox console DNS queries")
    ap.add_argument("--listen", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=53,
                    help="MUST be 53: the console's DNS setting has no port field")
    ap.add_argument("--upstream", default="1.1.1.1")
    ap.add_argument("--log", default="xbox_dns.log")
    ap.add_argument("--duration", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-firewall", action="store_true")
    ap.add_argument("--no-elevate", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.port)

    if args.port == 53 and not is_admin() and not args.no_elevate:
        print("[!] Binding port 53 requires Administrator. Re-launching elevated...")
        argv = [a for a in sys.argv[1:] if a not in ("--no-elevate",)]
        if relaunch_elevated(argv):
            return 0
        print("[-] Could not elevate. Run this from an Administrator cmd.exe instead:")
        print("    (right-click Command Prompt -> Run as administrator)")
        return 1

    if args.port == 53 and not args.no_firewall:
        add_firewall_rule(args.port)

    print("=" * 74)
    print("Dying Light crossplay — Xbox console DNS observer")
    print("=" * 74)
    print("port     : %d  (UDP + TCP)" % args.port)
    print("upstream : %s" % args.upstream)
    print("log      : %s" % args.log)
    ips = lan_ips()
    print("LAN IPs  : %s" % ", ".join(ips))
    print()
    print(">>> ON THE CONSOLE (Xbox Series X):")
    print("    Settings -> Network -> Advanced -> DNS -> Manual")
    for ip in ips:
        print("        enter: %s" % ip)
    print("    then Settings -> Network -> Advanced -> Test connection")
    print("    (forces an immediate DNS resolution)")
    print("    and/or launch Dying Light and start matchmaking")
    print()
    print(">>> read the log afterwards with:   type %s" % args.log)
    print("    (in PowerShell: Get-Content %s)" % args.log)
    print()

    obs = Obs(args.log, args.upstream)
    threads = []
    try:
        t = threading.Thread(target=udp_server, args=(obs, args.listen, args.port), daemon=True)
        t.start()
        threads.append(t)
        t2 = threading.Thread(target=tcp_server, args=(obs, args.listen, args.port), daemon=True)
        t2.start()
        threads.append(t2)
        time.sleep(0.5)
        print("    %-8s %-46s %-9s %s" % ("CLIENT", "NAME", "CLASS", "RESULT"))
        print("    " + "-" * 78)
        end = time.time() + args.duration if args.duration else None
        while True:
            time.sleep(1.0)
            if end and time.time() > end:
                break
    except KeyboardInterrupt:
        print("\n[+] stopping")
    finally:
        obs.close()
        if args.port == 53 and not args.no_firewall:
            remove_firewall_rules()

    print("\n[+] %d queries, %d unique names" % (obs.total, len(obs.names)))
    for k, v in sorted(obs.counts.items(), key=lambda kv: -kv[1]):
        print("    %-9s %d" % (k, v))
    print("\n[+] KEY QUESTION:")
    print("    Any TECH or EPIC classification?")
    print("      TECH -> a Techland service is in the console's path (very")
    print("              interesting: potential shared meeting point)")
    print("      EPIC -> the console may already use EOS (would change the")
    print("              whole project)")
    print("      only XBOX/MSFT -> the console is purely Microsoft-stack")
    print("\n[+] share: %s" % os.path.abspath(args.log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
