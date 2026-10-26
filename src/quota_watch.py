# -*- coding: utf-8 -*-
"""R49i grantwatch2: 5-min sampler through a fixed clean exit (VPS 8893), auto-burst when the free pool reopens."""
import os, sys, json, time, re, random, string, requests
R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
B = "https://seedance2-5.com"
FP = os.environ.get("S25_FRESH_PROXY", "http://127.0.0.1:8893")
PX = {"http": FP, "https": FP}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
      "Content-Type": "application/json", "Origin": B, "Referer": B + "/en/sign-up"}
STATE = os.path.join(R, "_r49_s25_farm_accounts.json")
LOG = os.path.join(R, "_r49_s25_grantwatch2.log")
JSN = os.path.join(R, "_r49_s25_grantwatch2.jsonl")
DOMS = ["mailto.plus", "fexbox.org", "fextemp.com", "any.pink"]
CYCLE = int(os.environ.get("S25_CYCLE", "300"))
BURST = int(os.environ.get("S25_BURST", "20"))


def log(*a):
    s = " ".join(str(x) for x in a)
    try:
        print(s, flush=True)
    except Exception:
        print(s.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%m-%d %H:%M:%S] ") + s + "\n")
    except Exception:
        pass


def jrec(d):
    try:
        with open(JSN, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    except Exception:
        pass


def rnd(n):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def wait_link(em, timeout=100):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            j = requests.get("https://tempmail.plus/api/mails", params={"email": em, "limit": 20}, proxies=PX, timeout=25).json()
        except Exception:
            continue
        for mm in (j.get("mail_list") or []):
            mid = mm.get("mail_id") or mm.get("id")
            try:
                dd = requests.get("https://tempmail.plus/api/mails/" + str(mid), params={"email": em}, proxies=PX, timeout=25).json()
            except Exception:
                continue
            s = json.dumps(dd, ensure_ascii=False)
            m = re.search(r"https://seedance2-5\.com/api/auth/verify-email[^\"\s<\\]+", s)
            if m:
                return m.group(0).replace("\\u0026", "&")
    return None


def add_state(rec):
    try:
        A = json.load(open(STATE, encoding="utf-8-sig"))
        if any(x.get("email") == rec["email"] for x in A):
            return False
        A.append(rec)
        tmp = STATE + ".tmp"
        json.dump(A, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, STATE)
        log("STATE+", rec["email"], "credits", rec.get("credits"))
        return True
    except Exception as e:
        log("add_state ERR", type(e).__name__, str(e)[:80]); return False


def one_signup(tag="sample"):
    dom = DOMS[random.randrange(len(DOMS))]
    em = "s25" + rnd(10) + "@" + dom
    pw = "Pz!" + rnd(11)
    s = requests.Session(); s.proxies = PX
    try:
        r = s.post(B + "/api/auth/sign-up/email", json={"email": em, "password": pw, "name": "F"}, headers=UA, timeout=45)
    except Exception as e:
        log(tag, "signup ERR", type(e).__name__, str(e)[:60]); return None
    if r.status_code != 200:
        log(tag, "signup", r.status_code, (r.text or "")[:80]); return None
    time.sleep(3)
    try:
        s.post(B + "/api/auth/send-verification-email", json={"email": em, "callbackURL": "/"}, headers=UA, timeout=30)
    except Exception:
        pass
    link = wait_link(em)
    if link:
        try: s.get(link, headers={"User-Agent": UA["User-Agent"]}, timeout=30)
        except Exception: pass
        time.sleep(3)
    s2 = requests.Session(); s2.proxies = PX
    try:
        r2 = s2.post(B + "/api/auth/sign-in/email", json={"email": em, "password": pw}, headers=UA, timeout=45)
    except Exception as e:
        log(tag, "signin ERR", type(e).__name__); return None
    if r2.status_code != 200:
        log(tag, "signin", r2.status_code, (r2.text or "")[:80]); return None
    try:
        c = s2.post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=30)
        cr = (c.json().get("data") or {}).get("remainingCredits")
    except Exception:
        cr = None
    log(tag, em, "credits", cr)
    jrec({"ev": tag, "email": em, "credits": cr, "ts": int(time.time()), "proxy": FP})
    rec = {"email": em, "password": pw, "cookies": s2.cookies.get_dict(), "credits": cr,
           "node": "VPS-" + FP.split("//")[-1], "ts": int(time.time()), "wave": 9 if cr == 40 else 0}
    if cr == 40:
        add_state(rec)
    return rec


def recheck(n=3):
    try:
        A = json.load(open(STATE, encoding="utf-8-sig"))
    except Exception:
        return
    pool = [x for x in A if (x.get("credits") or 0) == 0 and x.get("email") and x.get("password")][-n:]
    for a in pool:
        s = requests.Session(); s.proxies = PX
        try:
            r = s.post(B + "/api/auth/sign-in/email", json={"email": a["email"], "password": a["password"]}, headers=UA, timeout=40)
        except Exception:
            continue
        if r.status_code == 200:
            try:
                c = s.post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=25)
                cr = (c.json().get("data") or {}).get("remainingCredits")
            except Exception:
                cr = None
            log("recheck", a["email"], "credits", cr)
            jrec({"ev": "recheck", "email": a["email"], "credits": cr, "ts": int(time.time())})
        time.sleep(3)


def fexpost_probe():
    try:
        A = json.load(open(STATE, encoding="utf-8-sig"))
        cand = [x for x in A if x.get("credits") == 40 and x.get("email", "").endswith("fexpost.com")]
        if not cand:
            return
        a = cand[int(time.time() / 1800) % len(cand)]
        s = requests.Session(); s.proxies = PX
        try:
            r = s.post(B + "/api/auth/sign-in/email", json={"email": a["email"], "password": a["password"]}, headers=UA, timeout=40)
        except Exception as e:
            log("fexpost ERR", type(e).__name__); return
        log("fexpost", a["email"], r.status_code)
        if r.status_code == 200:
            try: os.remove(os.path.join(R, "_r49_s25_login_down.json"))
            except Exception: pass
            log("*** FEXPOST RECOVERED ***", a["email"])
            jrec({"ev": "fexpost_recovered", "email": a["email"], "ts": int(time.time())})
            a["cookies"] = s.cookies.get_dict()
            try:
                c = s.post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=25)
                log("fexpost credits", (c.text or "")[:80])
            except Exception:
                pass
    except Exception as e:
        log("fexpost outer ERR", type(e).__name__)


def main():
    log("== grantwatch2 start cycle", CYCLE, "burst", BURST, "proxy", FP)
    n = 0
    while True:
        n += 1
        rec = one_signup("sample")
        if rec and rec.get("credits") == 40:
            log("*** POOL OPEN -> burst", BURST, "***")
            zeros = 0
            for i in range(BURST):
                r2 = one_signup("burst%d" % i)
                if r2 and r2.get("credits") == 40:
                    zeros = 0
                else:
                    zeros += 1
                    if zeros >= 3:
                        log("burst stop: 3 zeros"); break
                time.sleep(12)
        if n % 6 == 1:
            recheck(3)
            fexpost_probe()
        log("== cycle", n, "done, sleep", CYCLE)
        time.sleep(CYCLE)


if __name__ == "__main__":
    main()
