# -*- coding: utf-8 -*-
"""Probe which temp-mail domains still pass signup -> verify -> signin on seedance2-5.com."""
import os, sys, json, time, re, random, string, requests
R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
B = "https://seedance2-5.com"
PU = os.environ.get("S25_PROXY", "http://127.0.0.1:7897")
PX = {"http": PU, "https": PU}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
      "Content-Type": "application/json", "Origin": B, "Referer": B + "/en/sign-up"}
OUT = os.path.join(R, "_r49_s25_domainprobe.json")

def rnd(n):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def post(s, path, body, timeout=45):
    try:
        r = s.post(B + path, json=body, headers=UA, timeout=timeout)
        return r.status_code, (r.text or "")[:300]
    except Exception as e:
        return 0, type(e).__name__ + ":" + str(e)[:120]

def wait_link(em, timeout=150):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            j = requests.get("https://tempmail.plus/api/mails", params={"email": em, "limit": 20},
                             proxies=PX, timeout=25).json()
        except Exception:
            continue
        for mm in (j.get("mail_list") or []):
            mid = mm.get("mail_id") or mm.get("id")
            try:
                dd = requests.get("https://tempmail.plus/api/mails/" + str(mid), params={"email": em},
                                  proxies=PX, timeout=25).json()
            except Exception:
                continue
            s = json.dumps(dd, ensure_ascii=False)
            m = re.search(r"https://seedance2-5\.com/api/auth/verify-email[^\"\s<\\]+", s)
            if m:
                return m.group(0).replace("\\u0026", "&")
    return None

def one(domain, proxy_port):
    px = {"http": "http://127.0.0.1:%d" % proxy_port, "https": "http://127.0.0.1:%d" % proxy_port}
    em = "s25" + rnd(10) + "@" + domain
    pw = "Pz!" + rnd(11)
    s = requests.Session(); s.proxies = px
    rec = {"domain": domain, "email": em, "password": pw}
    sc, body = post(s, "/api/auth/sign-up/email", {"email": em, "password": pw, "name": "F"})
    rec["signup"] = [sc, body[:200]]
    print("[%s] signup %s %s" % (domain, sc, body[:160].replace("\n", " ")), flush=True)
    if sc != 200:
        return rec
    time.sleep(6)
    sc2, body2 = post(s, "/api/auth/sign-in/email", {"email": em, "password": pw})
    rec["signin_pre"] = [sc2, body2[:200]]
    print("[%s] signin-before-verify %s %s" % (domain, sc2, body2[:120].replace("\n", " ")), flush=True)
    time.sleep(4)
    sc3, body3 = post(s, "/api/auth/send-verification-email", {"email": em, "callbackURL": "/"})
    rec["sendverify"] = [sc3, body3[:200]]
    print("[%s] send-verify %s %s" % (domain, sc3, body3[:120].replace("\n", " ")), flush=True)
    link = wait_link(em)
    rec["link"] = bool(link)
    print("[%s] mail link %s" % (domain, bool(link)), flush=True)
    if link:
        try:
            rr = s.get(link, headers={"User-Agent": UA["User-Agent"]}, timeout=30, allow_redirects=True)
            rec["verify_click"] = [rr.status_code, rr.url[:160]]
            print("[%s] verify click %s %s" % (domain, rr.status_code, rr.url[:100]), flush=True)
        except Exception as e:
            print("[%s] verify ERR %s" % (domain, type(e).__name__), flush=True)
        time.sleep(5)
    s2 = requests.Session(); s2.proxies = px
    sc4, body4 = post(s2, "/api/auth/sign-in/email", {"email": em, "password": pw})
    rec["signin_post"] = [sc4, body4[:200]]
    print("[%s] signin-after-verify %s %s" % (domain, sc4, body4[:140].replace("\n", " ")), flush=True)
    if sc4 == 200:
        rec["cookies"] = s2.cookies.get_dict()
        c = s2.post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=30)
        rec["credits"] = [c.status_code, (c.text or "")[:160]]
        print("[%s] credits %s %s" % (domain, c.status_code, (c.text or "")[:120]), flush=True)
    return rec

def main():
    doms = [x.strip() for x in (sys.argv[1] if len(sys.argv) > 1 else "mailto.plus,fexbox.org,fextemp.com,any.pink").split(",") if x.strip()]
    port = int(os.environ.get("S25_PORT", "7897"))
    out = []
    for i, d in enumerate(doms):
        try:
            out.append(one(d, port))
        except Exception as e:
            print("[%s] FATAL %s %s" % (d, type(e).__name__, str(e)[:100]), flush=True)
            out.append({"domain": d, "error": type(e).__name__})
        try:
            json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
        time.sleep(15)
    print("done", json.dumps([{k: v for k, v in r.items() if k in ("domain", "signup", "signin_pre", "signin_post")} for r in out], ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
