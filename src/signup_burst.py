# -*- coding: utf-8 -*-
"""R49j wave9: parallel signup harvest through the fixed VPS exit (8893), aimed at the early-morning free-pool window."""
import os, sys, json, time, re, random, string, datetime, threading, queue, requests
R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
B = "https://seedance2-5.com"
FP = os.environ.get("S25_FRESH_PROXY", "http://127.0.0.1:8893")
PX = {"http": FP, "https": FP}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
      "Content-Type": "application/json", "Origin": B, "Referer": B + "/en/sign-up"}
STATE = os.path.join(R, "_r49_s25_farm_accounts.json")
LOG = os.path.join(R, "_r49_s25_wave9.log")
JSN = os.path.join(R, "_r49_s25_wave9.jsonl")
DOMS = ["mailto.plus", "fexbox.org", "fextemp.com", "any.pink"]
THREADS = int(os.environ.get("S25_THREADS", "3"))
CAP = int(os.environ.get("S25_CAP", "200"))
GAP = float(os.environ.get("S25_GAP", "6"))
START_AT = os.environ.get("S25_START_AT", "").strip()
STOP_AFTER_ZERO = int(os.environ.get("S25_STOP_ZERO", "5"))

lock = threading.Lock()
stats = {"ok": 0, "zero": 0, "forty": 0, "fail": 0, "zero_streak": 0, "stop": False}


def log(*a, **kw):
    s = " ".join(str(x) for x in a)
    with lock:
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
    with lock:
        try:
            with open(JSN, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        except Exception:
            pass


def rnd(n):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def add_state(rec):
    with lock:
        try:
            A = json.load(open(STATE, encoding="utf-8-sig"))
            if any(x.get("email") == rec["email"] for x in A):
                return
            A.append(rec)
            tmp = STATE + ".tmp"
            json.dump(A, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, STATE)
        except Exception as e:
            log("add_state ERR", type(e).__name__, str(e)[:60])


def wait_link(em, timeout=110):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(4)
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


def worker(idx, q):
    while not stats["stop"]:
        try:
            q.get_nowait()
        except queue.Empty:
            return
        dom = DOMS[random.randrange(len(DOMS))]
        em = "s25" + rnd(10) + "@" + dom
        pw = "Pz!" + rnd(11)
        s = requests.Session(); s.proxies = PX
        try:
            r = s.post(B + "/api/auth/sign-up/email", json={"email": em, "password": pw, "name": "F"}, headers=UA, timeout=45)
        except Exception as e:
            with lock:
                stats["fail"] += 1
            log("w%d signup ERR" % idx, type(e).__name__)
            time.sleep(GAP); continue
        if r.status_code != 200:
            with lock:
                stats["fail"] += 1
            log("w%d signup %s %s" % (idx, r.status_code, (r.text or "")[:60]))
            time.sleep(GAP); continue
        time.sleep(2)
        try:
            s.post(B + "/api/auth/send-verification-email", json={"email": em, "callbackURL": "/"}, headers=UA, timeout=30)
        except Exception:
            pass
        link = wait_link(em)
        if link:
            try: s.get(link, headers={"User-Agent": UA["User-Agent"]}, timeout=30)
            except Exception: pass
            time.sleep(2)
        s2 = requests.Session(); s2.proxies = PX
        try:
            r2 = s2.post(B + "/api/auth/sign-in/email", json={"email": em, "password": pw}, headers=UA, timeout=45)
        except Exception:
            r2 = None
        if r2 is None or r2.status_code != 200:
            with lock:
                stats["fail"] += 1
            log("w%d signin %s" % (idx, getattr(r2, "status_code", "ERR")))
            time.sleep(GAP); continue
        try:
            c = s2.post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=25)
            cr = (c.json().get("data") or {}).get("remainingCredits")
        except Exception:
            cr = None
        rec = {"email": em, "password": pw, "cookies": s2.cookies.get_dict(), "credits": cr,
               "node": "VPS-8893", "ts": int(time.time()), "wave": 9 if cr == 40 else 0}
        try:
            jrec(rec)
        except Exception:
            pass
        if cr == 40:
            try: add_state(rec)
            except Exception as e: log("add_state ERR", type(e).__name__)
        with lock:
            stats["ok"] += 1
            if cr == 40:
                stats["forty"] += 1; stats["zero_streak"] = 0
            else:
                stats["zero"] += 1; stats["zero_streak"] += 1
                if stats["zero_streak"] >= STOP_AFTER_ZERO and stats["forty"] == 0:
                    stats["stop"] = True
        log("w%d %s credits %s" % (idx, em, cr))
        time.sleep(GAP)


def main():
    if START_AT:
        hh, mm = [int(x) for x in START_AT.split(':')]
        now = datetime.datetime.now()
        tgt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if tgt <= now:
            tgt += datetime.timedelta(days=1)
        w = (tgt - now).total_seconds()
        log("waiting %.0fs until %s" % (w, tgt))
        time.sleep(max(0, w))
    log("== wave9 start threads", THREADS, "cap", CAP, "proxy", FP)
    q = queue.Queue()
    for i in range(CAP):
        q.put(i)
    ts = [threading.Thread(target=worker, args=(i, q), daemon=True) for i in range(THREADS)]
    for t in ts: t.start()
    for t in ts: t.join()
    log("== wave9 done", json.dumps(stats))


if __name__ == "__main__":
    main()
