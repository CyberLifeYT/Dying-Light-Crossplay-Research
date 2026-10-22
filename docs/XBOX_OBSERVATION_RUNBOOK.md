# Xbox Internet-Session Observation — User Runbook (CORRECTED)

**Read this first:** the first attempt failed for a *tool* reason, not a console
reason. Everything below is tested (9/9 regression tests pass).

---
## WHAT WAS BROKEN AND IS NOW FIXED

| Problem | Detail | Status |
|---|---|---|
| **Wrong port** | The console's custom-DNS setting takes an **IP address only** — there is no port field. The console sends queries to **UDP/53**. The first tool listened on **5353** and could never have seen a query. | **Fixed** — now binds UDP/53 + TCP/53 |
| **No reply sent** | The observer parsed and logged queries but **never replied**. Any resolver would have timed out. | **Fixed** |
| **TCP path corrupt** | The 2-byte TCP length prefix was concatenated into the DNS message. | **Fixed** |
| **Firewall** | Windows Defender drops inbound UDP/53 by default. | **Fixed** — rule added automatically |
| **Privileges** | Binding 53 needs Administrator. | **Fixed** — auto-elevates, or use `run_xbox_dns.cmd` |
| **cmd vs PowerShell** | `Read` is a PowerShell cmdlet. In cmd.exe use **`type`**. | noted below |

---
# MEASUREMENT 1 — What does the console resolve? (U1)

## Step 1 — start the observer (as Administrator)

Right-click → **Run as administrator**:

```
C:\Users\cyber\AppData\Local\Temp\opencode\run_xbox_dns.cmd
```

It prints your LAN IPs. **Use `192.168.0.17`** (WiFi).
`26.172.116.150` is a Radmin VPN adapter and `192.168.137.1` is a
direct-Ethernet link — neither is right for a console on your WiFi.

## Step 2 — point the console at it

On the **Xbox Series X**:
```
Settings -> Network -> Advanced -> DNS -> Manual
```
Enter `192.168.0.17` (no port).

Then force a resolution immediately:
```
Settings -> Network -> Advanced -> Test connection
```

Then also launch Dying Light -> menus -> matchmaking -> create a co-op session.
Leave the console running ~5 minutes.

## Step 3 — read the log

In cmd.exe:      `type xbox_dns.log`
In PowerShell:   `Get-Content xbox_dns.log`

## Step 4 — restore the console's DNS to **Automatic**.

---
# MEASUREMENT 2 — Where does the console's gameplay traffic go? (U2)

**This is the feasibility kill-switch.** It does *not* depend on Measurement 1
working, so run it even if you get nothing from the DNS observer.

## Option A — pktmon capture (built into Windows, no Wireshark)

Right-click -> **Run as administrator**:

```
C:\Users\cyber\AppData\Local\Temp\opencode\capture_xbox.cmd
```

1. It starts capturing.
2. On the console: start a co-op session with a friend and **actually play**
   for a minute or two (so gameplay traffic flows).
3. Come back and press ENTER to stop.
4. It converts to `xbox_trace.pcapng` and auto-runs the triage.

## Option B — router capture
Capture at the router (or mirror the console's switch port), save as
`xbox_session.pcap` or `.pcapng`, then:
```powershell
python dl_session_probe.py --pcap xbox_session.pcapng
```

## Option C — connection table, no pcap
On a PC on the console's LAN, with the console in an active session:
```powershell
python dl_session_probe.py --stats --seconds 300
```

## Option D — router connection log (no capture at all)
Export the router's per-device connection log and:
```powershell
python dl_session_probe.py --logfile router-connections.txt
```
(Handles `ip:port -> ip:port`, `src= dst= dport=`, and columnar formats.)

---
# READING THE RESULTS

## Measurement 1
| If you see... | Meaning | Consequence |
|---|---|---|
| **`TECH`** (techland.pl, dyinglightgame.com) | A Techland service is in the console's path | **Best outcome** — a shared *vendor* meeting point that doesn't require touching the console. |
| **`EPIC`** (epicgames.dev) | The console was updated to EOS | **Transformative** — shared transport; only identity + `REPL_VERSION` remain. |
| only `XBOX`/`MSFT-GEN` | Purely Microsoft-stack | Session is Microsoft-operated; a PC client needs an Xbox Live identity **and a title-scoped session token** it cannot obtain. Approaches collapse. |
| nothing | see Troubleshooting | — |

## Measurement 2
| Observation | Meaning | Consequence |
|---|---|---|
| High-volume **UDP** to a **non-Microsoft** IP | Gameplay is **peer-to-peer** | A PC-side bridge is *conceivable*. Next blocker = replication protocol. |
| Everything on **TCP/443** to **Microsoft** IPs | Gameplay is **Microsoft-relayed over TLS** | **PROJECT DEAD.** The payload is never visible to any PC-side component; no bridge or translator can exist. |
| Console reaches a **TECH** IP for session data + gameplay is direct UDP | Vendor session service + P2P gameplay | Best case — a PC-side re-implementation of that session service becomes the approach. |

---
# TROUBLESHOOTING "still no queries"

1. **Is it elevated?** `run_xbox_dns.cmd` prints `[+] Administrator: OK`.
2. **Same subnet?** Check the console's IP in `Settings -> Network -> Advanced
   -> Network Status`; it should be `192.168.0.x`.
3. **Prove the path without the console** — from a **phone** on the same
   Wi-Fi: set its DNS to `192.168.0.17` and browse. If the phone resolves,
   the path is fine and the issue is the console. If the phone fails, it's
   your firewall/isolation.
4. **Firewall rule present?** In an Administrator cmd:
   ```
   netsh advfirewall firewall show rule name="DL-XboxDNS-In-UDP"
   ```
   If missing:
   ```
   netsh advfirewall firewall add rule name="DL-XboxDNS-In-UDP" dir=in action=allow protocol=UDP localport=53 profile=any
   netsh advfirewall firewall add rule name="DL-XboxDNS-In-TCP" dir=in action=allow protocol=TCP localport=53 profile=any
   ```
5. **Console ignoring the custom DNS?** Some builds resolve game traffic
   internally. If the console clearly has Internet but DNS shows nothing,
   its game traffic doesn't use the system resolver -> fall back to
   **Measurement 2**, which doesn't depend on the resolver at all.

---
# WHAT TO SEND BACK

1. `xbox_dns.log` — the whole file.
2. The `dl_session_probe.py` output, plus `xbox_trace.pcapng` /
   `xbox_session.pcap` if you got one.
3. `pc_dns.log` + PC-side `dl_capture.py --stats` output (optional reference).
4. Three answers:
   - **Are you and the Xbox on the same LAN, or in different cities?**
     (Different cities => U2 is almost certainly "relayed" => project dead.
     Knowing this early is worth a lot.)
   - Can your router capture or mirror a device's traffic? (yes/no)
   - Does your Xbox friend also have a PC?
     (**If yes, you can make a PC<->PC session today** — official EOS crossplay
     Steam<->Epic<->GoG — a working reference to diff the console against, and
     a real fallback for the two of you.)
