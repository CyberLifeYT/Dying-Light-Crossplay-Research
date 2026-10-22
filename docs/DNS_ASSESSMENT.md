# DNS Redirection — Technical Assessment (Phase 2)

## Q1. Which hostnames does the PC game contact?

**Verified by exhaustive string extraction from all three binaries.**

`engine_x64_rwdi.dll` — only 8 domain-like tokens:
```
cacerts.digicert.com, crl3.digicert.com, crl4.digicert.com, www.digicert.com   (cert validation)
graph.facebook.com, www.facebook.com                                             (legacy)
mantis.techland.pl                                                               (crash reports)
retrousb.com                                                                    (legacy)
```
`gamedll_x64_rwdi.dll`:
```
dyinglightgame.com, www.epicgames.com, www.microsoft.com, tobiigaming.com
```
Shipped config `data/restclient.scr`:
```
ProdServer("https://pls.dyinglightgame.com")
DevServer("https://plsdev.dyinglightgame.com")
```
`data/network.scr` — **dead**: AuthServer[1-9].techland.pl, GameListServer.techland.pl
are not referenced anywhere in the engine binary (verified by string search + xref).

**The EOS hostnames are NOT in the binary.** The EOS SDK (20 MB) contains
**no** `epicgames.dev`/`eos-epic.io` hostname literal. Instead:
```
FSDKConfigPlatformUpdateTask / FSDKConfigProductUpdateTask
SDKConfig_ParseConfig / SDKConfig_UpdatePlatform / SDKConfig_UpdateProduct
FHttpCompomentCommon::GetBaseURL(%s) service name not found.
FHttpCompomentCommon::GetServiceConfigName(%s) service name not found.
EpicGamesPlatform::GetBaseURL(%s) service name not found.
BaseUrl / AltBaseUrl / AltDomains / ServiceName / DeploymentId
JWKS endpoint did not return server date, using local system time
```
The SDK ships **URL paths only**, e.g. `/auth/v1/oauth/jwks`, `/auth/v1/oauth/token`,
`/epic/oauth/v2/token`, `/user/v8/product-users/search`, `/v1/graphql`,
`/api/v1/public/data/clients`, `/auth/v1/turn/credentials`, and resolves
`{serviceName}` -> `{BaseUrl}` from a **remote SDK Config service** that it
fetches at startup and refreshes on a timer.

**Consequence:** you cannot DNS-redirect "the EOS API" by guessing a hostname,
because the game does not contain one. The bootstrap name must be discovered
empirically (the DNS logger does this) — and it is a *config* endpoint whose
response drives all further endpoints.

## Q2. Can the Xbox hostnames be identified through legitimate observation?
**Yes, but only from the Xbox side of the network, and only as DNS queries.**
Options, in order of preference:
1. A DNS server on the Xbox's LAN (the console uses the LAN resolver) — logs
   the names it asks for. Requires the console's DNS to be pointed at your
   server (router DHCP, or console manual DNS setting on Xbox One).
2. Router/ISP DNS log or a pcap taken at the router (UDP/53 is plaintext).
3. Xbox One network settings allow a **custom DNS server** — this is a
   supported console feature, so this is legitimate observation of your own
   network, not circumvention.

You cannot see the console's TLS traffic, but you *can* see the names.

## Q3. Do both builds contact a common service?
**No.** This is the decisive finding.
- PC: Epic EOS services (`*.epicgames.dev` family) + `pls.dyinglightgame.com`.
- Xbox One (2016): Microsoft/Xbox Live services (`*.xboxlive.com`, `*.xbox.com`,
  `*.live.com`, `microsoft.com` family), plus *possibly* a Techland service of
  its own vintage (the 2016 Techland backend, not the 2021 `pls.` one).

The only conceivable overlap is "a Techland-operated service", and the 2016
PC and Xbox backends (`AuthServer.techland.pl` etc.) are **dead since the
2021 EOS migration**. So: **no shared service exists to redirect.**

## Q4. DNS redirection: change IP, or reimplement the service?
**Both, and the second part is the killer.**

Redirecting `pls.dyinglightgame.com` to your box would mean your box must
serve the *entire* PLS API — `/auth/login/epic/`, `/auth/logout/`,
`/rewards/currentuser/?release_level=%d`, dockets, MOTDs, events, patch
manifests — **including validating the Epic auth token** the client presents.
You cannot validate it: it is an Epic-issued token and only Epic's backend
holds the signing key. You would have to accept any token (i.e. accept
unauthenticated clients), which is a working session-broker, not a redirect.

Redirecting an EOS endpoint is worse: the EOS SDK verifies TLS
(CRYPT32 11 imports, WINTRUST 1, Secur32 5) and the EOS backend issues
signed, session-bound material (EOS lobbies contain a `ProductUserId` bound
to the Epic account; EOS P2P connections are authorized by Epic). Standing in
for it means forging Epic-signed session state, which is both
cryptographically infeasible and not something I will help with.

**And critically: DNS redirection only changes where the PC's *own* service
calls go. It cannot make the Xbox console call anything different.** The
console resolves Microsoft hostnames via the Xbox's own resolution path and
validates Microsoft's TLS. A DNS server cannot redirect a name the console
never asks for, and cannot redirect one it asks for without breaking TLS
validation (Xbox One pins the Microsoft trust chain; there's no supported
proxy-install path for it).

## Q5. Could a custom DNS server direct both platforms to a compatible broker?
**No.** For the reasons above: the two platforms ask for *different names*
pointing at *different vendors*, and you cannot present a valid Microsoft
certificate for Xbox Live endpoints, nor a valid Epic certificate for EOS.
The only DNS-based approach that works is one where **both** sides already
speak a protocol you can speak. That is exactly the LAN path (§Q8).

## Q6. Could a proxy translate EOS sessions to Xbox sessions?
**Not at the EOS layer.** EOS P2P is an Epic-operated transport: the client
sends to Epic's relay/NAT-traversal infrastructure, which forwards to the
peer. There is no client-visible plaintext stream to translate — you would
have to terminate EOS P2P (requires Epic-side cooperation) or relay it
(which the SDK already does, correctly).
**At the LAN layer, yes** — and that is the recommended direction (§Q8).

## Q7. Certificates, TLS, platform auth, signed requests
**All four are present and all four are blockers for redirection.**
- EOS SDK imports: `WINHTTP` (TLS), `CRYPT32` (11), `WINTRUST` (1),
  `Secur32` (5), `bcrypt` (1). The library *validates* the server chain.
- The EOS SDK verifies its own config response (JWKS handling; `VerifyIdToken:
  Failed because SDK config did not become ready`).
- EOS auth is a bearer token bound to an Epic account
  (`EOS_Auth_CopyUserAuthToken`, `auth_session_ticket`).
- Xbox One: platform-signed console, Microsoft account tokens, console TLS
  trust store, and the console *additionally* refuses unknown CAs.

**Therefore: DNS redirection cannot bypass authentication on either side, and
cannot make the two backends interoperate.**

## Q8. Would DNS help with matchmaking only, leaving gameplay incompatible?
**Yes — and that is exactly the shape of the problem.**
DNS can, at most, redirect the PC's *Techland* service (PLS) — which is
live-service only (dockets, MOTDs, rewards, patches) and **carries no
matchmaking or gameplay traffic at all** (verified: matchmaking is 100% EOS
Lobby, gameplay is 100% EOS P2P). So DNS redirection of the PC side would
affect a service that isn't part of the crossplay problem.

Even a perfect DNS-level session broker would leave:
- identity namespaces disjoint (Epic ProductUserId vs Xbox Live XUID),
- EOS P2P vs Xbox networking,
- `Net::Repl` REPL_VERSION=5 vs the Xbox 2016 build's version,
- 33 message types / 16 compression variants that must match exactly.

**Conclusion: DNS redirection is a dead end for this project.** It is a
*measurement* tool (excellent for enumerating what the game contacts), not a
*solution* mechanism. Its legitimate use is intelligence-gathering, and the
DNS logger is built and tested for exactly that.

## What actually works instead
The LAN path bypasses **every** platform backend:
- raw UDP, connectionless, no platform login involved,
- Chrome Engine "WD6C" field protocol, **fully decoded** this session,
- selectable in-game: `&GameVisibilityArea_Lan_&`, `MenuSelectGameType`,
- `CLobby::CreateScanner` selects the LAN scanner for scanner type 1/2.

=> The only credible route to PC<->Xbox is **D/E (LAN discovery bridge) and/or
F (gameplay protocol translation) on top of the LAN path**, not A/B/C.
