# -*- coding: utf-8 -*-
"""Continuous consumer: pick any account with 40 credits not yet in ledger, generate one clip.
Serial single-channel, refreshes the account pool every cycle so newly registered wave accounts are picked up.
Env: S25_START_AT=HH:MM  S25_CDP  S25_LEDGER  S25_PEND  S25_RES  S25_WM  S25_MAX_ATTEMPTS=2
"""
import os, sys, json, time, asyncio, datetime, zlib

R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
sys.path.insert(0, R)
from _r49_s25_gen_one import gen

STATE = os.path.join(R, '_r49_s25_farm_accounts.json')
LED = os.environ.get('S25_LEDGER') or os.path.join(R, '_r49_s25_ledger.json')
TMP = os.path.join(R, '_r49_s25_tmp_consumer.json')
START_AT = os.environ.get('S25_START_AT', '').strip()
MAX_ATT = int(os.environ.get('S25_MAX_ATTEMPTS', '2'))
SPLIT_MOD = int(os.environ.get('S25_SPLIT_MOD', '1'))
SPLIT_REM = int(os.environ.get('S25_SPLIT_REM', '0'))
CLAIM = os.environ.get('S25_CLAIMS') or os.path.join(R, '_r49_s25_claims.json')
SKIP_CLAIMS = [x.strip() for x in os.environ.get('S25_SKIP_CLAIMS', '').split(',') if x.strip()]
ORDER = os.environ.get('S25_ORDER', 'asc')

PROMPTS = [
 "A cinematic macro shot of a hummingbird hovering beside a red camellia, dew drops, golden backlight, shallow depth of field",
 "Aerial shot over a misty mountain valley at sunrise, layers of clouds, golden light raking across pine forests, slow forward glide",
 "A lantern-lit night market in the rain, steam from food stalls, reflections in puddles, slow tracking shot, warm and cool contrast",
 "A lone astronaut walking across a black volcanic beach at dusk, bioluminescent waves, wide anamorphic frame, slow push-in",
 "Time-lapse of storm clouds rolling over a desert mesa, lightning illuminating the canyon walls, dramatic scale",
 "Close-up of a barista pouring latte art in a sunlit cafe, steam curling, shallow depth of field, warm film tones",
 "A vintage train crossing a stone viaduct in autumn fog, red leaves drifting, slow aerial orbit",
 "Underwater shot of a sea turtle gliding through sunbeams in a kelp forest, particles floating, serene pacing",
 "A neon-lit cyberpunk street from above at night, rain, umbrellas, holographic signs, slow crane down",
 "Frost crystals forming on a window at dawn, macro lens, soft blue light, extremely shallow depth of field",
 "A dancer silhouetted against a giant moon, desert dust swirling, slow motion, high contrast",
 "A paper boat drifting down a rain-filled gutter, city lights bokeh, low angle, gentle tracking",
]


def jload(p, d):
    try:
        return json.load(open(p, encoding='utf-8-sig'))
    except Exception:
        return d


def jsave(p, v):
    t = p + '.tmp'
    with open(t, 'w', encoding='utf-8') as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    os.replace(t, p)


def done_set():
    d = set()
    import glob as _g
    for p in _g.glob(os.path.join(R, '_r49_s25_ledger*.json')) + _g.glob(os.path.join(R, 'ledger*.json')):
        for x in jload(p, []):
            if x.get('email'):
                d.add(x['email'])
    return d


def cooled_domains():
    import glob as _g
    out = set()
    now = time.time()
    for p in _g.glob(os.path.join(R, '_r49_s25_login_down_*.json')):
        try:
            f = json.load(open(p, encoding='utf-8'))
            if now - float(f.get('ts') or 0) < float(os.environ.get('S25_LOGIN_COOLDOWN', '1200')):
                out.add(os.path.basename(p)[len('_r49_s25_login_down_'):-5])
        except Exception:
            pass
    return out


def main():
    if START_AT:
        hh, mm = [int(x) for x in START_AT.split(':')]
        now = datetime.datetime.now()
        tgt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if tgt <= now:
            tgt += datetime.timedelta(days=1)
        w = (tgt - now).total_seconds()
        print("waiting %.0fs until %s" % (w, tgt), flush=True)
        time.sleep(max(0, w))

    att = {}
    claims = set(jload(CLAIM, []))
    n = 0
    idle = 0
    while True:
        A = jload(STATE, [])
        done = done_set() | claims
        for _f in SKIP_CLAIMS:
            done |= set(jload(_f, []))
        cool = cooled_domains()
        todo = [a for a in A if (a.get('credits') or 0) >= 40 and a.get('email') and a['email'] not in done
                and att.get(a['email'], 0) < MAX_ATT
                and a['email'].split('@')[-1] not in cool
                and (zlib.crc32(a['email'].encode()) % SPLIT_MOD) == SPLIT_REM]
        if not todo:
            idle += 1
            print("idle", idle, "state", len(A), "done", len(done), flush=True)
            time.sleep(60)
            continue
        if ORDER == 'desc':
            todo.sort(key=lambda z: (z.get('ts') or 0), reverse=True)
        idle = 0
        a = todo[0]
        em = a['email']
        n += 1
        tag = "c25_%03d" % n
        print("### gen", tag, em, a.get('node'), flush=True)
        jsave(TMP, a)
        claims.add(em)
        jsave(CLAIM, sorted(claims))
        att[em] = att.get(em, 0) + 1
        p = PROMPTS[n % len(PROMPTS)]
        try:
            out = asyncio.run(gen(TMP, p, tag))
            print("### result", tag, em, out, flush=True)
        except Exception as e:
            print("### ERR", tag, em, type(e).__name__, str(e)[:160], flush=True)
            out = None
        if out:
            print('### ok', tag, os.path.getsize(out) if os.path.exists(out) else -1, flush=True)
        claims.discard(em)
        jsave(CLAIM, sorted(claims))
        time.sleep(5)


if __name__ == '__main__':
    main()