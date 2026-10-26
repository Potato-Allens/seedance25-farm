# -*- coding: utf-8 -*-
import asyncio,os,json,sys,time,requests,subprocess
from patchright.async_api import async_playwright
R = os.environ.get('S25_STATE_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state')
os.makedirs(R, exist_ok=True)
B="https://seedance2-5.com"
OUTDIR=os.environ.get("S25_OUT") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"out")
os.makedirs(OUTDIR,exist_ok=True)
CDP=os.environ.get("S25_CDP","http://127.0.0.1:9333")
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36","Content-Type":"application/json","Origin":B,"Referer":B+"/text-to-video"}
STATE=os.path.join(R,'_r49_s25_farm_accounts.json')
LOCK=os.path.join(R,'_r49_s25_state.lock')

def _lock_get(timeout=20):
    t0=time.time()
    while time.time()-t0<timeout:
        try:
            fd=os.open(LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.close(fd); return True
        except Exception:
            time.sleep(0.5)
    return False

def _lock_drop():
    try: os.remove(LOCK)
    except Exception: pass

def _persist_state(acct):
    if not _lock_get(): print('persist:lock-timeout',flush=True); return
    try:
        A=json.load(open(STATE,encoding='utf-8-sig'))
        hit=0
        for x in A:
            if x.get('email')==acct.get('email'):
                x['cookies']=acct['cookies']; hit+=1
        if hit:
            tmp=STATE+'.tmp'
            json.dump(A,open(tmp,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
            os.replace(tmp,STATE)
        print('persist:cookies',acct.get('email'),'hit',hit,flush=True)
    except Exception as e:
        print('persist ERR',type(e).__name__,str(e)[:80],flush=True)
    finally:
        _lock_drop()

async def gen(acct_file,prompt,tag):
    acct=json.load(open(acct_file,encoding='utf-8-sig'))
    FLAG=os.path.join(R,'_r49_s25_login_down.json')
    if os.environ.get("S25_RELOGIN","1")=="1" and acct.get("email") and acct.get("password"):
        try:
            _f=json.load(open(FLAG,encoding='utf-8'))
            if time.time()-float(_f.get('ts') or 0) < float(os.environ.get("S25_LOGIN_COOLDOWN","1200")):
                print("relogin:cooldown",_f.get('code'),flush=True); return None
        except Exception: pass
        px=os.environ.get("S25_RELOGIN_PROXY") or "http://127.0.0.1:7897"
        try:
            s0=requests.Session(); s0.proxies={"http":px,"https":px}
            rr=s0.post(B+"/api/auth/sign-in/email",json={"email":acct["email"],"password":acct["password"]},headers=UA,timeout=40)
            print("relogin",rr.status_code,(rr.text or "")[:80].replace("\n"," "),flush=True)
            if rr.status_code==500:
                try: json.dump({"ts":time.time(),"code":500,"email":acct.get("email")},open(FLAG,'w',encoding='utf-8'))
                except Exception: pass
                return None
            if rr.status_code==200:
                try: os.remove(FLAG)
                except Exception: pass
            if rr.status_code==200 and s0.cookies.get_dict():
                acct["cookies"]=s0.cookies.get_dict()
                json.dump(acct,open(acct_file,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
                _persist_state(acct)
        except Exception as e:
            print("relogin ERR",type(e).__name__,str(e)[:100],flush=True)
    ck=acct["cookies"]
    bid=None
    async with async_playwright() as pw:
        b=await pw.chromium.connect_over_cdp(CDP)
        ctx=b.contexts[0]
        # only remove auth cookies, keep cf_clearance/__cf_bm so Turnstile can load
        for _n in list(ck.keys()):
            try: await ctx.clear_cookies(name=_n)
            except Exception as e: print("ckclear",_n,type(e).__name__,flush=True)
        await ctx.add_cookies([{"name":k,"value":v,"domain":"seedance2-5.com","path":"/","secure":True,"httpOnly":False,"sameSite":"Lax"} for k,v in ck.items()])
        pg=[p for p in ctx.pages if "seedance2-5.com" in p.url]
        pg=pg[0] if pg else await ctx.new_page()
        holder={}
        async def on_resp(r):
            if "/api/ai/generate" in r.url and r.request.method=="POST":
                try: holder["body"]=r.request.post_data
                except Exception: pass
                try: holder["t"]=await r.text()
                except Exception: pass
        pg.on("response",lambda r: asyncio.create_task(on_resp(r)))
        try:
            await pg.goto(B+"/",wait_until="domcontentloaded",timeout=60000)
            await pg.evaluate("()=>{try{localStorage.clear();sessionStorage.clear();}catch(e){}}")
        except Exception as e: print("storageclear",e,flush=True)
        await pg.goto(B+"/text-to-video",wait_until="domcontentloaded",timeout=60000)
        await pg.wait_for_timeout(7000)
        await pg.keyboard.press("Escape")
        await pg.evaluate("""()=>{document.querySelectorAll('[data-slot=dialog-overlay],[data-slot=dialog-content]').forEach(e=>e.remove());
          const bs=[...document.querySelectorAll('button')];
          for(const b of bs){const t=(b.innerText||"").trim(); if(t==='取消'||t==='Cancel'){try{b.click()}catch(e){}}}}""")
        cred=await pg.evaluate("""async()=>{const r=await fetch('/api/user/get-user-credits',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});return (await r.text());}""")
        print("credits",cred[:100],flush=True)
        try:
            if json.loads(cred).get("data",{}).get("remainingCredits",0)<40:
                print("skip:no-credits",flush=True); return None
        except Exception: pass
        # wait for turnstile token, click "Try again" if widget errored
        tok=0
        for _attempt in range(3):
            for _w in range(8):
                tok=int(await pg.evaluate("()=>{const i=document.querySelector('[name=cf-turnstile-response]');return i?i.value.length:0;}") or 0)
                if tok>50: break
                await pg.wait_for_timeout(4000)
            if tok>50: break
            clicked=await pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(e=>/Try again/i.test(e.innerText));if(b){b.click();return true}return false;}""")
            print("retry_click",_attempt,clicked,flush=True)
            if not clicked: break
            await pg.wait_for_timeout(8000)
        print("turnstile_len",tok,flush=True)
        if tok<=50:
            await pg.screenshot(path=os.path.join(R,f'_r49_fail_{tag}.png')); return None
        v=await pg.evaluate("""(p)=>{
          const ta=document.querySelector('#studio-prompt');
          if(!ta) return 'no-ta';
          ta.focus();
          const proto=ta.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
          Object.getOwnPropertyDescriptor(proto,'value').set.call(ta,p);
          ta.dispatchEvent(new Event('input',{bubbles:true}));
          ta.dispatchEvent(new Event('change',{bubbles:true}));
          return ta.value.length;
        }""",prompt)
        print("promptlen",v,flush=True)
        if os.environ.get("S25_RES"):
            await pg.evaluate("""(r)=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText.trim()===r);if(b)b.click();}""",os.environ["S25_RES"])
            await pg.wait_for_timeout(1200)
        if os.environ.get("S25_WM")=="0":
            await pg.evaluate("""()=>{const s=[...document.querySelectorAll('[role=switch]')].find(e=>e.getAttribute('aria-label')==='Watermark');if(s&&s.getAttribute('aria-checked')==='true')s.click();}""")
            await pg.wait_for_timeout(1200)
        if os.environ.get("S25_RES") or os.environ.get("S25_WM"):
            print("post",await pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText.includes('Generate 1 video'));return b?b.innerText:null;}"""),flush=True)
        st=None
        for _k in range(10):
            await pg.wait_for_timeout(1500)
            st=await pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText.includes('Generate 1 video'));return b?{dis:b.disabled,t:b.innerText}:null;}""")
            if st and not st["dis"]: break
        print("btn",st,flush=True)
        if st and not st["dis"]:
            await pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')].find(e=>e.innerText.includes('Generate 1 video'));if(b&&!b.disabled)b.click();}""")
            for i in range(15):
                await pg.wait_for_timeout(2000)
                if holder.get("t"): break
            print("reqbody",(holder.get("body") or "")[:400],flush=True)
            print("gen",(holder.get("t") or "")[:160],flush=True)
            try: bid=json.loads(holder["t"])["data"]["batchId"]
            except Exception: bid=None
        if not bid:
            # fallback: build the same body the UI would send and POST it from page context
            tokv=await pg.evaluate("()=>{const i=document.querySelector('[name=cf-turnstile-response]');return i?i.value:'';}")
            if len(tokv or '')<=50:
                print("fallback:no-token",flush=True)
                await pg.screenshot(path=os.path.join(R,f'_r49_fail_{tag}.png')); return None
            body={"scene":"text-to-video","provider":"seedance-lite","model":"seedance-2.5-lite",
                  "prompt":prompt,"turnstileToken":tokv,"mediaType":"video",
                  "options":{"aspect_ratio":"16:9","resolution":"720p","duration":4,"watermark_enabled":True},
                  "count":1,"quotedCostCredits":40}
            ik="c25-%d-%d"%(int(time.time()),int.from_bytes(os.urandom(4),'big'))
            res=await pg.evaluate("""async (a)=>{try{const r=await fetch('/api/ai/generate',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':a.ik},body:JSON.stringify(a.b)});return r.status+'|'+await r.text();}catch(e){return '0|'+e.message;}}""",{"ik":ik,"b":body})
            print("fallback",(res or '')[:220],flush=True)
            try: bid=json.loads(res.split('|',1)[1])["data"]["batchId"]
            except Exception:
                await pg.screenshot(path=os.path.join(R,f'_r49_fail_{tag}.png')); return None
    s=requests.Session(); s.cookies.update(ck)
    pend=os.environ.get('S25_PEND') or os.path.join(R,'_r49_s25_pending.json')
    try: P=json.load(open(pend,encoding='utf-8'))
    except Exception: P=[]
    P.append({"email":acct.get("email"),"batch":bid,"tag":tag,"ts":int(time.time())})
    json.dump(P,open(pend,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    url=None
    for i in range(200):
        try:
            rr=s.post(B+"/api/ai/batch",json={"batchId":bid},headers=UA,timeout=40)
            j=rr.json(); t=j["data"]["tasks"][0]
        except Exception as e:
            body=""
            try: body=rr.text[:160]
            except Exception: pass
            print("pollerr",i,type(e).__name__,body.replace("\n"," "),flush=True)
            if "Batch not found" in body: return None
            time.sleep(8); continue
        st=t.get("status")
        print(i,st,flush=True)
        if st=="success":
            ti=t.get("taskInfo"); ti=json.loads(ti) if isinstance(ti,str) else ti
            url=ti["videos"][0]["videoUrl"]; break
        if st in ("failed","canceled"): print(json.dumps(t)[:300]); return None
        time.sleep(6)
    if not url: return None
    full=url if url.startswith("http") else B+url
    out=os.path.join(OUTDIR,f"{tag}_{bid[:8]}_720p_4s.mp4")
    for k in range(14):
        try:
            rr=s.get(full,headers={"User-Agent":UA["User-Agent"],"Referer":UA["Referer"]},timeout=120)
            if rr.status_code==200 and len(rr.content)>10000:
                open(out,"wb").write(rr.content); break
        except Exception as e:
            print("dlerr",k,type(e).__name__,flush=True)
        time.sleep(6)
    if not os.path.exists(out):
        print("dlfail",full,flush=True); return None
    print("saved",out,os.path.getsize(out),flush=True)
    print(subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,r_frame_rate:format=duration,size","-of","default=nw=1",out],capture_output=True,text=True).stdout,flush=True)
    # ledger
    led=os.environ.get('S25_LEDGER') or os.path.join(R,'_r49_s25_ledger.json')
    try: L=json.load(open(led,encoding='utf-8'))
    except Exception: L=[]
    L.append({"email":acct.get("email"),"batch":bid,"file":out,"bytes":os.path.getsize(out),"ts":int(time.time())})
    try:
        P=[x for x in json.load(open(pend,encoding='utf-8')) if x.get("batch")!=bid]
        json.dump(P,open(pend,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    except Exception: pass
    json.dump(L,open(led,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    return out
if __name__=="__main__":
    print(asyncio.run(gen(sys.argv[1],sys.argv[2],sys.argv[3])))

