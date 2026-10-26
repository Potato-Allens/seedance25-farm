# Pitfalls ? the expensive lessons

## 1. PowerShell: `-Include` without a wildcard `-Path` returns everything

```powershell
# WRONG ? returns the entire tree, not just mp4
Get-ChildItem -LiteralPath $dir -Recurse -Include *.mp4
```

`-Include` is only applied when `-Path` itself contains a wildcard. With `-LiteralPath` it is
silently ignored. One such command enumerated **35,404 files / 8.07 GB** and moved them one by one
into a flat archive directory; the source disk dropped to 0.00 GB free. Recovery took an hour of
index rebuilding.

Always:

```powershell
Get-ChildItem -LiteralPath $dir -Recurse -Filter *.mp4
# or
Get-ChildItem -LiteralPath $dir -Recurse | Where-Object Extension -eq '.mp4'
```

## 2. `Start-Process -ArgumentList` splits paths containing spaces or parentheses

```powershell
# WRONG ? path with ( ) or spaces is chopped into pieces
Start-Process python -ArgumentList @('-u', $scriptPath)
# python: can't find '__main__' module in 'D:\1\OpenAI.Codex_26.715.3651.0_x64('

# RIGHT ? one single string
Start-Process python -ArgumentList "-u `"$scriptPath`""
```

## 3. Killing a batch of PowerShell processes can kill your own shell

`Stop-Process` over a filtered list may include the ancestor of the current shell; the session
then dies with `exit -1`. Start the replacement process first, then stop the old ones, or kill by
exact PID after checking `ParentProcessId`.

## 4. Clash: one selector, many consumers

All Clash instances share the same proxy group. `PUT /proxies/<group> {"name": ...}` from a
registration script therefore **changes the exit for every other task**, including the CDP browser.
A dead node (e.g. one that only throws `SSLError`) will silently break generation for everyone.
Health-check a node (`GET /api/auth/ok` through the proxy) before keeping it.

## 5. `SSLError` usually means the proxy node is dead, not the site

When sign-in starts failing with `Max retries exceeded ? SSLError`, switch a known-good node first.
The tell: `/api/auth/ok` through the same proxy also fails, while a direct request succeeds.

## 6. ffmpeg encoder strings identify the assembler

`encoder=Lavf58.76.100` = the streaming CDN; `Lavf63.1.102` = local ffmpeg 9.0.2.
When auditing ?is this file native or assembled??, the encoder metadata answers it without
re-encoding anything.

## 7. Vercel edge hides the origin region

`x-vercel-id: hnd1::iad1::?` means ?Tokyo edge, US-East function?. Changing your exit IP in Asia
does not change the function region, so region-specific outages cannot be dodged by switching nodes.

## 8. A blocked mail domain is not a rate limit

`422 FAILED_TO_CREATE_USER` on signup + `500` on sign-in (with a correct password, while a wrong
password still returns 401) means the domain is refused ? back off is useless, change the domain.
Keep `domain_probe.py` in the loop, because this can happen overnight.

## 9. Disposable-mail domains share one MX

`fexpost.com`, `mailto.plus`, `fexbox.org`, `fextemp.com`, `any.pink`, `merepost.com`,
`rover.info`, `mailbox.in.ua` all resolve to `mx.fex.plus`. A ban is per domain name, not per MX,
so a spare domain is a one-line change ? but keep several.

## 10. Session cookies die silently

`GET /api/auth/get-session` answering `200 null` **and** returning
`Set-Cookie: ?=; Max-Age=0` means the session record is gone (expired or secret rotated).
Do not keep injecting a dead cookie into the browser; re-sign-in first (`S25_RELOGIN=1`).

## 11. Never trust a cached cookie file

Cookies captured at sign-up time go stale; the generation worker must refresh them at the start
of each job. That is what `_persist_state()` plus the `500`-cooldown in `gen_one.py` implement:
refresh ? on 500 write `login_down.json` ? stay quiet for `S25_LOGIN_COOLDOWN` seconds instead of
hammering the auth endpoint into a 429.
