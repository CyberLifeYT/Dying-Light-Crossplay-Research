"""Phase-marked DNS observer for the Xbox (v2).  Run from an *Administrator* prompt.

The console's DNS is set to this PC. Every query is forwarded upstream and answered normally;
the only change to answers is that TTLs are capped (default 10 s) so the console re-resolves
names in each phase instead of serving them from its cache. Logged per query: time, phase,
client, name, type, class, answer IPs/CNAMEs. No other traffic is seen or touched.

usage:  python xbox_dns_phased2.py [--client 192.168.0.195] [--ttl 10] [--upstream 1.1.1.1]
        [--port 53] [--no-firewall] [--log ..\\logs\\xbox_dns_<time>.tsv]
Press ENTER to advance phases, Ctrl+C to stop (prints per-phase summary).
Adds an inbound firewall rule for the port while running and removes it on exit.
"""
import argparse, datetime, os, socket, struct, subprocess, sys, threading

PHASES = [
    "0 baseline: console freshly booted (full shutdown), dashboard only, DL1 NOT running / not in Quick Resume",
    "1 launch: DL1 started, until title screen",
    "2 menu: main menu, idle ~1 min",
    "3 online menu: co-op / online menu opened",
    "4 host: hosting a co-op game",
    "5 join: searching for / joining a public game",
    "6 play: in a co-op game with someone",
    "7 quit: back to dashboard",
]
RULE = "DL-XboxDNS2"
HERE = os.path.dirname(os.path.abspath(__file__))


def classify(n):
    n = n.lower().rstrip(".")
    for tag, keys in (("EPIC", ("epicgames", "eos-epic", "epicgames.dev", "on.epicgames.com")),
                      ("TECH", ("dyinglight", "techland")),
                      ("XBOX", ("xboxlive.com", "xbox.com", "xboxab.com", "gamepass")),
                      ("MSFT", ("microsoft.com", "live.com", "msftncsi", "windowsupdate", "azure", "msedge"))):
        if any(k in n for k in keys):
            return tag
    return "OTHER"


# ---------- minimal DNS parsing ----------
def read_name(buf, off):
    labels, jumped, end = [], False, None
    for _ in range(128):
        ln = buf[off]
        if ln == 0:
            off += 1
            break
        if ln & 0xC0 == 0xC0:
            if not jumped:
                end = off + 2
            off = ((ln & 0x3F) << 8) | buf[off + 1]
            jumped = True
            continue
        labels.append(buf[off + 1:off + 1 + ln].decode("ascii", "replace"))
        off += 1 + ln
    return ".".join(labels), (end if jumped else off)


def clamp_and_extract(resp, max_ttl):
    """Return (patched response, [answer strings]). Only TTL fields are modified."""
    out = bytearray(resp)
    qd, an, ns, ar = struct.unpack("!4H", resp[4:12])
    off = 12
    for _ in range(qd):
        _, off = read_name(resp, off)
        off += 4
    answers = []
    for i in range(an + ns + ar):
        _, off = read_name(resp, off)
        rtype, _rclass, ttl, rdlen = struct.unpack("!HHIH", resp[off:off + 10])
        if rtype != 41 and ttl > max_ttl:                      # never touch OPT pseudo-record
            struct.pack_into("!I", out, off + 4, max_ttl)
        rd = off + 10
        if i < an:
            if rtype == 1 and rdlen == 4:
                answers.append(socket.inet_ntop(socket.AF_INET, resp[rd:rd + 4]))
            elif rtype == 28 and rdlen == 16:
                answers.append(socket.inet_ntop(socket.AF_INET6, resp[rd:rd + 16]))
            elif rtype == 5:
                answers.append("CNAME " + read_name(resp, rd)[0])
        off = rd + rdlen
    return bytes(out), answers


class Observer:
    def __init__(self, a):
        self.a, self.phase, self.lock = a, 0, threading.Lock()
        self.seen = {}                                          # name -> first phase
        self.per_phase = {i: [] for i in range(len(PHASES))}
        os.makedirs(os.path.dirname(os.path.abspath(a.log)), exist_ok=True)
        self.fh = open(a.log, "a", encoding="utf-8", buffering=1)
        self.fh.write("# time\tphase\tclient\tproto\tname\tqtype\tclass\trcode\tanswers\n")

    def mark(self, i):
        with self.lock:
            self.phase = i
            self.fh.write("%s\tPH%d\t-\t-\t#PHASE %s\n" % (now(), i, PHASES[i]))

    def forward(self, query):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(4)
        try:
            s.sendto(query, (self.a.upstream, 53))
            return s.recv(4096)
        finally:
            s.close()

    def handle(self, query, client, proto):
        try:
            name, off = read_name(query, 12)
            qtype = struct.unpack("!H", query[off:off + 2])[0]
        except Exception:
            return None
        try:
            resp = self.forward(query)
            if resp[2] & 0x02 and proto == "UDP":               # truncated: pass through untouched
                patched, answers = resp, ["<truncated>"]
            else:
                patched, answers = clamp_and_extract(resp, self.a.ttl)
            rcode = resp[3] & 0x0F
        except Exception as e:
            patched, answers, rcode = None, ["<upstream error %s>" % e], -1
        if self.a.client in (None, client):
            cls = classify(name)
            with self.lock:
                self.fh.write("%s\tPH%d\t%s\t%s\t%s\t%d\t%s\t%d\t%s\n" % (
                    now(), self.phase, client, proto, name, qtype, cls, rcode, ",".join(answers)))
                if name.lower() not in self.seen:
                    self.seen[name.lower()] = self.phase
                    self.per_phase[self.phase].append((cls, name))
                    if cls != "OTHER" or self.a.verbose:
                        print("  [PH%d new] %-5s %s" % (self.phase, cls, name))
        return patched

    def summary(self):
        lines = ["", "=== first appearance of each name, by phase ==="]
        for i, p in enumerate(PHASES):
            items = sorted(self.per_phase[i])
            lines.append("-- %s  (%d new)" % (p, len(items)))
            lines += ["     %-5s %s" % it for it in items]
        text = "\n".join(lines)
        print(text)
        self.fh.write("\n".join("# " + l for l in lines) + "\n")
        self.fh.close()


def now():
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def udp_loop(obs, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", port))
    while True:
        data, addr = s.recvfrom(4096)
        def work(d=data, a=addr):
            r = obs.handle(d, a[0], "UDP")
            if r:
                s.sendto(r, a)
        threading.Thread(target=work, daemon=True).start()


def tcp_loop(obs, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", port))
    s.listen(16)
    while True:
        c, addr = s.accept()
        def work(c=c, a=addr):
            try:
                ln = struct.unpack("!H", c.recv(2))[0]
                q = b""
                while len(q) < ln:
                    q += c.recv(ln - len(q))
                # TCP: ask upstream over UDP; fine for observation purposes
                r = obs.handle(q, a[0], "TCP")
                if r:
                    c.sendall(struct.pack("!H", len(r)) + r)
            except Exception:
                pass
            finally:
                c.close()
        threading.Thread(target=work, daemon=True).start()


def firewall(add, port):
    subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=" + RULE],
                   capture_output=True)
    if add:
        for proto in ("UDP", "TCP"):
            subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", "name=" + RULE,
                            "dir=in", "action=allow", "protocol=" + proto, "localport=%d" % port,
                            "remoteip=localsubnet"], capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default=None, help="only log this source IP (e.g. 192.168.0.195)")
    ap.add_argument("--ttl", type=int, default=10)
    ap.add_argument("--upstream", default="1.1.1.1")
    ap.add_argument("--port", type=int, default=53)
    ap.add_argument("--no-firewall", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="also print OTHER-class names live")
    ap.add_argument("--log", default=os.path.join(HERE, "..", "logs",
                    datetime.datetime.now().strftime("xbox_dns_%Y%m%d_%H%M%S.tsv")))
    a = ap.parse_args()

    if not a.no_firewall:
        firewall(True, a.port)
    obs = Observer(a)
    try:
        threading.Thread(target=udp_loop, args=(obs, a.port), daemon=True).start()
        threading.Thread(target=tcp_loop, args=(obs, a.port), daemon=True).start()
    except OSError as e:
        print("[-] cannot bind port %d: %s (run as Administrator?)" % (a.port, e))
        return 1
    print("DNS observer v2 on UDP/TCP %d, upstream %s, TTL cap %ds, log %s"
          % (a.port, a.upstream, a.ttl, os.path.abspath(a.log)))
    print("client filter: %s\n" % (a.client or "none (all clients logged)"))
    for p in PHASES:
        print("   " + p)
    obs.mark(0)
    print("\n>>> PHASE 0 started. Press ENTER when you begin each next phase. Ctrl+C to finish.")
    try:
        for i in range(1, len(PHASES)):
            input()
            obs.mark(i)
            print(">>> PHASE %s" % PHASES[i])
        print("[all phases done - Ctrl+C to finish]")
        threading.Event().wait()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        obs.summary()
        if not a.no_firewall:
            firewall(False, a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
