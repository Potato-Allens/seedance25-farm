# -*- coding: utf-8 -*-
"""R49g: does a fresh exit IP still get the 40-credit signup grant? One signup per node."""
import os, sys, json, time, re, random, string, requests
R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
B = "https://seedance2-5.com"
API = os.environ.get("S25_CLASH_API", "http://127.0.0.1:9097")
PU = os.environ.get("S25_PROXY", "http://127.0.0.1:7897")
PX = {"http": PU, "https": PU}
SEC = os.environ.get("CLASH_SECRET", "")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
      "Content-Type": "application/json", "Origin": B, "Referer": B + "/en/sign-up"}
N = int(os.environ.get("S25_N", "6"))
DOMS = ["mailto.plus", "fexbox.org", "fextemp.com", "any.pink"]
LOG = os.path.join(R, "_r49_s25_nodecredit.log")
OUT = os.path.join(R, "_r49_s25_nodecredit.json")

def log(*a):
    s = " ".join(str(x) for x in a)
    try:
        print(s, flush=True)
    except Exception:
        print(s.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("[%H:%M:%S] ") + s + "\n")

def rnd(n):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def pick_nodes():
    ctl = requests.Session(); ctl.headers["Authorization"] = "Bearer " + SEC
    allp = ctl.get(API + "/proxies/Kuromis", timeout=15).json()["all"]
    nodes = [n for n in allp if re.search(r"\d{2}$", n)]
    try:
        A = json.load(open(os.path.join(R, "_r49_s25_farm_accounts.json"), encoding="utf-8-sig"))
    except Exception:
        A = []
    last = {}
    for a in A:
        nd = a.get("node"); ts = a.get("ts") or 0
        if nd: last[nd] = max(last.get(nd, 0), ts)
    now = time.time()
    scored = sorted(nodes, key=lambda n: last.get(n, 0))
    return ctl, [(n, (now - last[n]) / 3600 if n in last else 999) for n in scored]

def wait_link(em, timeout=120):
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

def one_node(ctl, node):
    dom = DOMS[int(time.time()) % len(DOMS)]
    em = "s25" + rnd(10) + "@" + dom
    pw = "Pz!" + rnd(11)
    rec = {"node": node, "email": em, "password": pw, "ts": int(time.time())}
    try:
        ctl.put(API + "/proxies/Kuromis", json={"name": node}, timeout=15)
    except Exception as e:
        rec["err"] = "switch:" + type(e).__name__; return rec
    time.sleep(2.5)
    s = requests.Session(); s.proxies = PX
    try:
        r = s.post(B + "/api/auth/sign-up/email", json={"email": em, "password": pw, "name": "F"}, headers=UA, timeout=40)
    except Exception as e:
        rec["err"] = "signup:" + type(e).__name__; return rec
    rec["signup"] = r.status_code
    if r.status_code != 200:
        rec["body"] = (r.text or "")[:120]; return rec
    time.sleep(3)
    try:
        s.post(B + "/api/auth/send-verification-email", json={"email": em, "callbackURL": "/"}, headers=UA, timeout=30)
    except Exception:
        pass
    link = wait_link(em)
    rec["link"] = bool(link)
    if link:
        try:
            s.get(link, headers={"User-Agent": UA["User-Agent"]}, timeout=30)
        except Exception:
            pass
        time.sleep(3)
    s2 = requests.Session(); s2.proxies = PX
    try:
        r2 = s2.post(B + "/api/auth/sign-in/email", json={"email": em, "password": pw}, headers=UA, timeout=40)
        rec["signin"] = r2.status_code
    except Exception as e:
        rec["signin"] = "ERR:" + type(e).__name__
    if rec.get("signin") == 200:
        rec["cookies"] = s2.cookies.get_dict()
        try:
            c = s2.post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=30)
            rec["credits"] = (c.json().get("data") or {}).get("remainingCredits")
        except Exception:
            rec["credits"] = None
    return rec

def main():
    ctl, nodes = pick_nodes()
    todo = [n for n, age in nodes if age > 2.0][:N]
    log("== candidates", len(todo), "first:", todo[:3])
    out = []
    for nd in todo:
        rec = one_node(ctl, nd)
        out.append(rec)
        log("RESULT", nd, "signup", rec.get("signup"), "signin", rec.get("signin"), "credits", rec.get("credits"), rec.get("err", ""))
        try:
            json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
        time.sleep(10)
    hit = [r for r in out if r.get("credits") == 40]
    log("== done hits", len(hit), "/", len(out))

if __name__ == "__main__":
    main()
