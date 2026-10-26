# -*- coding: utf-8 -*-
"""Wave-3 registrations for seedance2-5.com.
Serial node switching (Clash selector is global) + parallel 3 signups / 3 mail waits per node.
Writes records with wave=3 into the main farm state, appends blocked nodes for audit.
Env: S25_START_AT=HH:MM  S25_PER=3  S25_ROUNDS=2  S25_NODES="A|B"  S25_MAXNODE=40  S25_TAG=wave3
"""
import os, sys, json, time, re, random, string, datetime
import requests
import concurrent.futures as cf

R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
STATE = os.path.join(R, '_r49_s25_farm_accounts.json')
BLOCK = os.path.join(R, '_r49_s25_wave3_blocked.json')
API = os.environ.get("S25_CLASH_API", "http://127.0.0.1:9097"); SEC = os.environ.get("CLASH_SECRET", "")
B = "https://seedance2-5.com"
PU = os.environ.get("S25_PROXY", "http://127.0.0.1:7897")
PX = {"http": PU, "https": PU}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
      "Content-Type": "application/json", "Origin": B, "Referer": B + "/"}
ctl = requests.Session(); ctl.headers["Authorization"] = "Bearer " + SEC

WAVE = int(os.environ.get('S25_WAVE', '3'))
PER = int(os.environ.get('S25_PER', '3'))
ROUNDS = int(os.environ.get('S25_ROUNDS', '2'))
MAXNODE = int(os.environ.get('S25_MAXNODE', '40'))
START_AT = os.environ.get('S25_START_AT', '').strip()


def rnd(n):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def load():
    try:
        return json.load(open(STATE, encoding='utf-8-sig'))
    except Exception:
        return []


def save(L):
    t = STATE + '.tmp'
    with open(t, 'w', encoding='utf-8') as f:
        json.dump(L, f, ensure_ascii=False, indent=1)
    os.replace(t, STATE)


def load_block():
    try:
        return json.load(open(BLOCK, encoding='utf-8'))
    except Exception:
        return {}


def save_block(d):
    with open(BLOCK, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def leaves():
    allp = ctl.get(API + "/proxies/Kuromis", timeout=15).json()["all"]
    ex = [x.strip() for x in os.environ.get("S25_EXCLUDE", "").split("|") if x.strip()]
    out = [n for n in allp if re.search(r"\d{2}$", n)]
    return [n for n in out if not any(e in n for e in ex)]


def wait_mail(em, timeout=150):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(4)
        try:
            j = requests.get("https://tempmail.plus/api/mails", params={"email": em, "limit": 20}, timeout=25).json()
        except Exception:
            continue
        for mm in (j.get("mail_list") or []):
            mid = mm.get("mail_id") or mm.get("id")
            try:
                dd = requests.get("https://tempmail.plus/api/mails/" + str(mid), params={"email": em}, timeout=25).json()
            except Exception:
                continue
            s = json.dumps(dd, ensure_ascii=False)
            m = re.search(r"https://seedance2-5\.com/api/auth/verify-email[^\"\s<\\]+", s)
            if m:
                return m.group(0).replace("\\u0026", "&")
    return None


def do_node(node, n):
    """Register up to n accounts on node. Returns (status, recs)."""
    ctl.put(API + "/proxies/Kuromis", json={"name": node}, timeout=15)
    time.sleep(1.5)
    doms = [x.strip() for x in (os.environ.get("S25_DOMAIN") or "mailto.plus").split(",") if x.strip()]
    ems = ["s25" + rnd(10) + "@" + doms[i % len(doms)] for i in range(n)]
    pws = ["Pz!" + rnd(11) for _ in range(n)]
    ss = []
    for _ in ems:
        s = requests.Session(); s.proxies = PX
        ss.append(s)

    def su(i):
        try:
            r = ss[i].post(B + "/api/auth/sign-up/email",
                           json={"email": ems[i], "password": pws[i], "name": "F"}, headers=UA, timeout=40)
            return i, r.status_code, r.text[:300]
        except Exception as e:
            return i, 0, type(e).__name__

    with cf.ThreadPoolExecutor(max_workers=n) as ex:
        res = list(ex.map(su, range(n)))
    limit = any("ACCOUNT_LIMIT" in (t or "") for _, _, t in res)
    ok = [i for i, sc, t in res if sc == 200]
    if not ok:
        return ("limit" if limit else "fail"), []

    def sv(i):
        try:
            ss[i].post(B + "/api/auth/send-verification-email", json={"email": ems[i], "callbackURL": "/"}, headers=UA, timeout=30)
        except Exception:
            pass
        return i

    with cf.ThreadPoolExecutor(max_workers=len(ok)) as ex:
        list(ex.map(sv, ok))

    with cf.ThreadPoolExecutor(max_workers=len(ok)) as ex:
        links = dict(zip(ok, ex.map(lambda i: wait_mail(ems[i]), ok)))

    out = []
    for i in ok:
        link = links.get(i)
        if not link:
            print("  no-link", ems[i][:14], flush=True)
            continue
        try:
            ss[i].get(link, headers={"User-Agent": UA["User-Agent"]}, timeout=30)
        except Exception:
            pass
        try:
            r2 = ss[i].post(B + "/api/auth/sign-in/email", json={"email": ems[i], "password": pws[i]}, headers=UA, timeout=30)
            if r2.status_code != 200:
                print("  login", r2.status_code, ems[i][:14], flush=True)
                continue
            c = ss[i].post(B + "/api/user/get-user-credits", json={}, headers=UA, timeout=25)
            cr = c.json().get("data", {}).get("remainingCredits")
        except Exception as e:
            print("  post-err", type(e).__name__, flush=True)
            continue
        rec = {"email": ems[i], "password": pws[i], "node": node, "credits": cr,
               "cookies": ss[i].cookies.get_dict(), "ts": int(time.time()),
               "wave": WAVE if cr == 40 else 0}
        out.append(rec)
        print("  OK", ems[i], cr, flush=True)
    return "ok", out


def node_age(L, node):
    ts = [a.get('ts') or 0 for a in L if a.get('node') == node]
    return (time.time() - max(ts)) / 3600 if ts else 999


def main():
    plan = '--plan' in sys.argv
    if START_AT and not plan:
        hh, mm = [int(x) for x in START_AT.split(':')]
        now = datetime.datetime.now()
        tgt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if tgt <= now:
            tgt += datetime.timedelta(days=1)
        wait = (tgt - now).total_seconds()
        print("waiting %.0fs until %s" % (wait, tgt), flush=True)
        time.sleep(max(0, wait))

    L = load()
    nodes = leaves()
    if os.environ.get('S25_NODES'):
        want = [x.strip() for x in os.environ['S25_NODES'].split('|') if x.strip()]
        nodes = [n for n in nodes if n in want or any(n.endswith(w) for w in want)]
    used = {a.get('node') for a in L}
    nodes = [n for n in nodes if n in used][:MAXNODE]
    if plan:
        nodes.sort(key=lambda n: -node_age(L, n))
        print("nodes", len(nodes), "state", len(L), flush=True)
        for n in nodes:
            have = sum(1 for a in L if a.get('node') == n and a.get('wave') == WAVE)
            print("  %-26s age=%5.2fh have=%d" % (n, node_age(L, n), have), flush=True)
        return

    min_age = float(os.environ.get('S25_MIN_AGE', '3.1'))
    horizon_h = float(os.environ.get('S25_HORIZON', '3'))
    abort_after = int(os.environ.get('S25_ABORT_AFTER_ZERO', '2'))
    idle_sleep = float(os.environ.get('S25_IDLE_SLEEP', '300'))
    deadline = time.time() + horizon_h * 3600
    blk = load_block()
    zero_streak = 0
    print("nodes", len(nodes), "state", len(L), "min_age", min_age, flush=True)

    while time.time() < deadline:
        L = load()
        todo = []
        for n in nodes:
            have = sum(1 for a in L if a.get('node') == n and a.get('wave') == WAVE)
            if have >= PER:
                continue
            age = node_age(L, n)
            if age < min_age:
                continue
            todo.append((n, PER - have, age))
        todo.sort(key=lambda x: -x[2])
        if not todo:
            if not nodes:
                print("no nodes selected", flush=True); return
            nxt = min(node_age(L, n) for n in nodes)
            print("idle: none eligible (best age %.2fh), sleeping %.0fs" % (nxt, idle_sleep), flush=True)
            time.sleep(idle_sleep)
            continue
        print("== pass todo", len(todo), flush=True)
        for k, (node, need, age) in enumerate(todo):
            if time.time() > deadline:
                break
            print("== %d/%d %s need=%d age=%.2fh" % (k + 1, len(todo), node, need, age), flush=True)
            try:
                st, recs = do_node(node, need)
            except Exception as e:
                st, recs = "err:" + type(e).__name__, []
            print("  ->", st, len(recs), flush=True)
            if recs:
                L2 = load()
                have = {a['email'] for a in L2}
                L2 += [r for r in recs if r['email'] not in have]
                save(L2)
            if st == "limit":
                blk[node] = {"ts": int(time.time()), "why": "ACCOUNT_LIMIT"}
                save_block(blk)
            good = [r for r in recs if (r.get('credits') or 0) >= 40]
            if recs and not good:
                zero_streak += 1
                print("  zero-streak", zero_streak, flush=True)
                if abort_after and zero_streak >= abort_after:
                    rs=float(os.environ.get("S25_RETRY_SLEEP","900"))
                    print("SOFT-ABORT: consecutive zero-credit nodes -> window not reset, sleep %.0fs and retry" % rs, flush=True)
                    save_block(blk)
                    zero_streak=0
                    time.sleep(rs)
                    break
            elif good:
                zero_streak = 0
            time.sleep(float(os.environ.get('S25_DELAY', '2')))
    L = load()
    print("DONE total", len(L), "wave3", sum(1 for a in L if a.get('wave') == WAVE), flush=True)


if __name__ == '__main__':
    main()