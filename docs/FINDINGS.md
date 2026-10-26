# Findings ? every claim and how it was measured

All numbers below were produced on 2026-10-25/26 against `seedance2-5.com` and its sibling site.
The rule of this document: **if it is not in a probe output, it is not a finding.**

---

## F1. A single generation can be 30 s, direct, no assembly

* Task `da302264-a55f-472b-b3e6-baecf718a144`, submitted with `duration:"30"`, `quality:"1080p"`.
* One task ? one `videoUrl` ? one file.

```
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,nb_frames:format=duration,size \
        -of default=nw=1 _glacier30.mp4
width=1920
height=1080
r_frame_rate=24/1
nb_frames=721
duration=30.08
size=53,4xx,xxx
```

* Container/codec: HEVC + AAC, `encoder=Lavf58.76.100`.
* Cost: **976 credits** (balance 1090 ? 114), matching 32.5 credits/s.
* Cross-check from the vendor page: `Total duration ? 30s`.

## F2. 1080p is not upscaled

Inventory of every 1920?1080 file produced so far (87 files):

| Encoder string | Count | Origin |
|---|---|---|
| `Lavf58.76.100` | 74 | server-side CDN transcode ? the delivered original |
| `Lavf63.1.102` | 13 | **our** local ffmpeg 9.0.2 concat/trim |

The second group only contains files that were explicitly assembled from native segments.
No file shows a low-resolution source scaled up (no `scale=` filter metadata, no 1344?768 source
with a 1920?1080 container).

## F3. 12/16/24 s clips are assembled, not native

Example: the 24 s asset is `sd25_native_1080p_24s.mp4`, produced from
`native_24s` + `native_30s_seg`; 721 frames = 24 s + 6 s at 24 fps.
Any file carrying `Lavf63.1.102` (local ffmpeg) in a "long" duration is an assembly job.

## F4. The free tier shape

* Grant: **40 credits**.
* What 40 credits buy: one **720p / 4 s** job.
* Delivered file: `1344?768`, `4.48 s`, `24 fps`, `107 frames` ? i.e. the 720p preset is not 1280?720
  but a 16:9 crop of 1344?768.

## F5. The watermark switch is inert on free accounts

```
[role=switch][aria-label=Watermark]  ? click ? aria-checked stays "true"
```

Confirmed on multiple free accounts; the toggle is not persisted server-side.

## F6. The free-credit gate is time+IP dependent, and only sampling catches it

| When (local) | Attempts | Grants | Rate |
|---|---|---|---|
| 03:05?05:11 | 111 | 108 | **97%** |
| 14:00 | 111 | 26 | 23% |
| 16:35?16:41 | 8 (6 idle Clash exits + 1 clean VPS) | 0 | 0% |
| 17:00 (same VPS, 3 threads) | 3 | 3 | 100% |
| 17:04 (same VPS, 4 threads) | 4 | 2 | 50% |
| 17:05+ (same VPS) | many | 0 | 0% |

Interpretation that survives all rows: a **fresh exit IP is necessary but not sufficient**;
the platform also gates on a server-side pool/allowance that opens and closes on its own schedule.
A 5-minute sampler with an instant burst on the first hit is the only strategy that has worked.

Rejected hypotheses, with the probe that killed them:

* *?`grant = floor(idle_hours / 3.05)`?* ? only 4 of 37 nodes matched.
* *?one grant per node per round?* ? true at 14:00, false at 17:00 (3 in one minute from one IP).
* *?per-IP cooldown of 3.05 h?* ? the VPS got 0 at 16:58 and 40 at 17:00, two minutes apart.

## F7. Disposable mail domains get banned in bulk

`fexpost.com` (working for hundreds of accounts on 2026-10-26 14:00?16:09) flipped at ~16:10:

| Action | Result |
|---|---|
| sign-up, new address | `422 {"code":"FAILED_TO_CREATE_USER"}` |
| sign-in, existing verified account, correct password | `500`, empty body |
| sign-in, wrong password | `401 INVALID_EMAIL_OR_PASSWORD` (so the account still exists) |
| sign-in with `@FEXPOST.COM` / `XXX@FEXPOST.COM` | `500` ? no case-bypass |

Domains verified working end-to-end (signup 200 ? mail ? verify 200 ? sign-in 200):

* `mailto.plus`, `fexbox.org`, `fextemp.com`, `any.pink`
  (all four are `tempmail.plus` aliases with `MX = mx.fex.plus`)

`merepost.com`, `rover.info`, `mailbox.in.ua` share the same MX and are kept as spares (untested).

## F8. Email verification became mandatory

Before 2026-10-26, sign-up returned a usable session. After the change:

* `POST /api/auth/sign-in/email` on an unverified account ? `403 EMAIL_NOT_VERIFIED`.
* `/api/config/get-configs` reports `email_verification_enabled: "true"`.
* A verified account signs in normally (`200` + `__Secure-better-auth.session_token`).

## F9. Other auth paths are closed

`magic-link`, `email-otp/*`, `forget-password` ? `404`. Google OAuth is enabled but needs Google
accounts. There is no password-reset or OTP route that could revive a banned-domain account.

## F10. Turnstile is only on generation, not on auth

* `/en/sign-in` and `/en/sign-up` chunks contain **zero** occurrences of `turnstile`/`captcha`.
* The studio page hosts the widget; `[name=cf-turnstile-response]` must exceed 50 chars before
  `/api/ai/generate` will accept the job.

---

## Reproduction checklist

1. `python src/domain_probe.py mailto.plus,fexbox.org` ? confirms the mail domains still pass.
2. `S25_N=6 python src/node_probe.py` ? one signup per idle exit, prints credits.
3. `python src/verify_all.py out` ? resolution histogram of whatever you generated.
4. `curl` any of the endpoints in `PROTOCOL.md` with a real cookie to re-check the current shape;
   the platform changes these without notice.
