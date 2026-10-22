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

**The EOS hostnames are NOT in the binary.** The EOS SDK contains
**no** `epicgames.dev`/`eos-epic.io` hostname literal. Instead:
```
FSDKConfigPlatformUpdateTask / FSDKConfigProductUpdateTask
SDKConfig_ParseConfig / SDKConfig_UpdatePlatform / SDKConfig_UpdateProduct
FHttpCompomentCommon::GetBaseURL(%s) service name not found.
EpicGamesPlatform::GetBaseURL(%s) service name not found.
BaseUrl / AltBaseUrl / AltDomains / ServiceName / DeploymentId
JWKS endpoint did not return server date, using local system time
```

The SDK resolves `{serviceName}` -> `{BaseUrl}` from a **remote SDK Config service** that it
fetches at startup and refreshes on a timer.

**Consequence:** you cannot DNS-redirect "the EOS API" by guessing a hostname,
because the game does not contain one. The bootstrap name must be discovered
empirically (the DNS logger does this) — and it is a *config* endpoint whose
response drives all further endpoints.

## Q2. Can the Xbox hostnames be identified through legitimate observation?
**Yes, but only from the Xbox side of the network, and only as DNS queries.**

## Q3. Do both builds contact a common service?
**No.** This is the decisive finding.
- PC: Epic EOS services (`*.epicgames.dev` family) + `pls.dyinglightgame.com`.
- Xbox One (2016): Microsoft/Xbox Live services (`*.xboxlive.com`, `*.xbox.com`,
  `*.live.com`, `*.microsoft.com` family), plus *possibly* a Techland service of
  its own vintage (the 2016 Techland backend, not the 2021 `pls.` one).

## Q4. DNS redirection: change IP, or reimplement the service?
**Both, and the second part is the killer.**

## Q5. Could a custom DNS server direct both platforms to a compatible broker?
**No.**

## Q6. Could a proxy translate EOS sessions to Xbox sessions?
**Not at the EOS layer.** EOS P2P is an Epic-operated transport. At the LAN
layer, yes.

## Q7. Certificates, TLS, platform auth, signed requests
**All four are present and all four are blockers for redirection.**

## Q8. Could a proxy translate EOS sessions to Xbox sessions?
**Yes — and that is exactly the shape of the problem.**

**Conclusion: DNS redirection is a dead end for this project.** It is a
*measurement* tool, not a *solution* mechanism.

## What actually works instead
The LAN path bypasses **every** platform backend.