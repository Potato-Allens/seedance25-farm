# Protocol reference ? Seedance 2.5 (seedance2-5.com)

All endpoints live under `https://seedance2-5.com` and are served by a Next.js app on Vercel
(`server: Vercel`, `x-matched-path: /api/auth/[...all]` for the auth routes).
Auth is [better-auth](https://www.better-auth.com/) with the email/password provider;
the session cookie is `__Secure-better-auth.session_token` (HttpOnly, Secure, SameSite=Lax).

---

## 1. Auth flow (as of 2026-10-26)

```
sign-up/email  ??? 200 {token:null, user:{emailVerified:false}}
      ?
      ?? (unverified) sign-in/email  ??? 403 EMAIL_NOT_VERIFIED      ? no session
      ?
      ?? send-verification-email ??? mail with
            https://seedance2-5.com/api/auth/verify-email?token=<jwt>
                ?
                ?? GET that URL ??? 200 (emailVerified=true)
                        ?
                        ?? sign-in/email ??? 200 {token, user:{emailVerified:true}}
                                              + Set-Cookie __Secure-better-auth.session_token
```

### 1.1 `POST /api/auth/sign-up/email`

```json
{"email":"s25xxxxxxxxxx@mailto.plus","password":"Pz!xxxxxxxxxxx","name":"F"}
```

`200`:

```json
{"token":null,
 "user":{"name":"F","email":"?","emailVerified":false,"image":null,
         "createdAt":"2026-10-26T08:38:34.404Z","updatedAt":"?","utmSource":"","ip":"69.33.182.248",
         "locale":"en","id":"706b23a6-?"}}
```

Failure modes actually observed:

| Status | Body | Meaning |
|---|---|---|
| 422 | `{"message":"Failed to create user","code":"FAILED_TO_CREATE_USER"}` | email domain rejected (disposable-domain block) |
| 400 | `{"message":"Missing CAPTCHA response"}` | the same rejection surfaced through the captcha branch |
| 429 | `{"message":"Too many requests. Please try again later."}` | per-IP rate limit |

### 1.2 `POST /api/auth/sign-in/email`

```json
{"email":"?","password":"?"}
```

Body is exactly three fields (`callbackURL` is optional); **no captcha token is sent by the UI** ?
the sign-in page chunk contains no `turnstile`/`captcha` string at all.

| Status | Body | Meaning |
|---|---|---|
| 200 | `{"redirect":false,"token":"<32 chars>","user":{?}}` | session issued (cookie in `Set-Cookie`) |
| 401 | `{"message":"Invalid email or password","code":"INVALID_EMAIL_OR_PASSWORD"}` | password checked and rejected |
| 403 | `{"message":"Email not verified","code":"EMAIL_NOT_VERIFIED"}` | password OK, verification missing |
| 429 | `{"message":"Too many requests?"}` | throttle |
| **500** | *(empty body, 0 bytes, no content-type)* | password OK, then an unhandled exception ? observed only for accounts on a blocked mail domain |

### 1.3 `GET /api/auth/get-session`

With a dead/rotated cookie the server answers `200` and body `null`, and **clears** the cookies:

```
set-cookie: __Secure-better-auth.session_token=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax
```

That `null` + `Max-Age=0` pair is the cheapest way to tell ?session expired? from ?account banned?.

### 1.4 Not available

`/api/auth/sign-in/magic-link`, `/api/auth/email-otp/send-verification-otp`,
`/api/auth/sign-in/email-otp`, `/api/auth/forget-password` ? **404** (plugins disabled).
`/api/auth/sign-in/social` ? 200 with a Google OAuth URL (unusable without Google accounts).

---

## 2. Account & config endpoints

### 2.1 `POST /api/user/get-user-credits`

```json
{}
```

```json
{"code":0,"message":"ok","data":{"remainingCredits":40}}
```

Without a session: `{"code":-1,"message":"no auth, please sign in"}`.

### 2.2 `POST /api/user/get-user-info`

```json
{"code":0,"message":"ok","data":{
  "email":"?","emailVerified":true,"utmSource":"","ip":"69.33.182.248","locale":"en",
  "id":"?","isAdmin":false,
  "credits":{"remainingCredits":0},
  "hasActiveSubscription":false,"currentSubscriptionProductId":null,
  "hasFastQueueAccess":false,"hasPaidGenerationAccess":false,"hasDownloadAccess":false}}
```

### 2.3 `POST /api/config/get-configs`

```json
{"code":0,"message":"ok","data":{
  "email_auth_enabled":"true","email_verification_enabled":"true",
  "google_auth_enabled":"true","google_one_tap_enabled":"true",
  "google_client_id":"?apps.googleusercontent.com",
  "google_ads_id":"AW-?","google_ads_signup_label":"?","google_ads_first_image_label":"?",
  "google_ads_first_video_label":"?","google_ads_begin_checkout_label":"?","google_ads_purchase_label":"?",
  "default_payment_provider":"dodo","dodo_enabled":"true"}}
```

Note `email_verification_enabled` ? when this flips to `true` (it did on 2026-10-26), unverified
accounts stop getting sessions.

---

## 3. Generation

### 3.1 `POST /api/ai/generate`

Headers: `Content-Type: application/json`, `Origin`/`Referer` set to the site,
`Idempotency-Key: c25-<unixtime>-<rand32>`.

```json
{"scene":"text-to-video",
 "provider":"seedance-lite",
 "model":"seedance-2.5-lite",
 "prompt":"A slow aerial push over a glacier at dawn",
 "turnstileToken":"<value of [name=cf-turnstile-response]>",
 "mediaType":"video",
 "options":{"aspect_ratio":"16:9","resolution":"720p","duration":4,"watermark_enabled":true},
 "count":1,
 "quotedCostCredits":40}
```

`data.batchId` is what you poll. The request is rejected without a Turnstile token, which is why
this call is made from **inside the page** (`fetch` in the browser context) rather than from Python.

### 3.2 `POST /api/ai/batch`

```json
{"batchId":"?"}
```

```json
{"data":{"tasks":[{"status":"success",
  "taskInfo":"{\"videos\":[{\"videoUrl\":\"https://?\"}]}"}]}}
```

`status` is one of `pending` / `running` / `success` / `failed` / `canceled`.
The video URL is a CDN link; `GET` it with the site `Referer` header.

### 3.3 Storage helpers (seen in the bundle, not needed for text-to-video)

`/api/storage/presign-media`, `/api/storage/complete-media`, `/api/storage/abandon-media`,
`/api/storage/upload-image`, `/api/storage/upload-media`, `/api/surveys/?`.

---

## 4. Models, resolutions, pricing

Read from the front-end bundle and confirmed by real jobs:

| Model id | Resolutions | Duration (s) | Notes |
|---|---|---|---|
| `seedance-2.5` | 480p / 720p / 1080p | 4 ? 30 | paid path (`provider: "evolink"` on the sibling site) |
| `seedance-2.5-lite` | 720p / 1080p | 4 ? 30 | what the free 40 credits buy |

1080p balance deltas (measured, not from the pricing page):

| Duration | Credits | Credits/s |
|---|---|---|
| 4 s | 130 | 32.5 |
| 8 s | 260 | 32.5 |
| 20 s | 651 | 32.55 |
| 30 s | 976 | 32.53 |

The marketing page states `Total duration ? 30s` ? consistent with the measured ceiling.

---

## 5. Account record schema (`state/accounts.json`)

```json
{
  "email": "s25xxxxxxxxxx@mailto.plus",
  "password": "Pz!xxxxxxxxxxx",
  "node": "VPS-8893",
  "credits": 40,
  "cookies": {"__Secure-better-auth.session_token": "?"},
  "ts": 1793005469,
  "wave": 9
}
```

`credits == 40` is the only field the consumer filters on; `wave` is bookkeeping.
`cookies` can always be regenerated with `POST /api/auth/sign-in/email`, which is what
`gen_one.py` does when `S25_RELOGIN=1`.

---

## 6. Error-code quick table

| Code | Where | Interpretation |
|---|---|---|
| `INVALID_EMAIL_OR_PASSWORD` | sign-in | 401, password wrong (account exists) |
| `EMAIL_NOT_VERIFIED` | sign-in | 403, verify the mailbox first |
| `FAILED_TO_CREATE_USER` | sign-up | 422, domain rejected or DB-side refusal |
| `Missing CAPTCHA response` | sign-up | 400, same rejection through the captcha branch |
| `code: -1 / no auth` | any `/api/user/*` | cookie missing or session revoked |
| 429 | all auth routes | per-IP throttle, back off ? 60 s |
| 500 + empty body | sign-in | password OK but an unhandled server-side check failed |
