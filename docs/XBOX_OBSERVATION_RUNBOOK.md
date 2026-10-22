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

---

# MEASUREMENT 1 — What does the console resolve? (U1)

## Step 1 — start the observer (as Administrator)

Right-click → **Run as administrator**:

```
C:\Users\cyber\AppData\Local\Temp\opencode\run_xbox_dns.cmd
```

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

---

# READING THE RESULTS

## Measurement 1
| If you see... | Meaning | Consequence |
|---|---|---|
| **`TECH`** (techland.pl, dyinglightgame.com) | A Techland service is in the console's path | **Best outcome** — a shared *vendor* meeting point that doesn't require touching the console. |
| **`EPIC`** (epicgames.dev) | The console was updated to EOS | **Transformative** — shared transport; only identity + `REPL_VERSION` remain. |
| only `XBOX`/`MSFT-GEN` | Purely Microsoft-stack | Session is Microsoft-operated; a PC client needs an Xbox Live identity **and a title-scoped session token** it cannot obtain. Approaches collapse. |
