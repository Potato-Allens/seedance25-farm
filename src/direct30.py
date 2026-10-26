# -*- coding: utf-8 -*-
import json,os,sys,time
import httpx
B="https://seeddance.ai"
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36","Content-Type":"application/json","Origin":B,"Referer":B+"/"}
OUT=os.environ.get("S25_OUT") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"out")
os.makedirs(OUT,exist_ok=True)
P=os.path.dirname(os.path.abspath(__file__))
email,pw,tag,prompt,dur = sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5]
LOG=open(os.path.join(P,"direct_%s.log"%tag),"a",encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s,flush=True); LOG.write(time.strftime("%H:%M:%S ")+s+"\n"); LOG.flush()
c=httpx.Client(headers=UA,timeout=90,follow_redirects=True)
log("signin",c.post(B+"/api/auth/sign-in/email",json={"email":email,"password":pw}).status_code)
log("bal0",c.post(B+"/api/user/get-user-credits",json={}).text[:80])
body={"mediaType":"video","scene":"text-to-video","provider":"evolink","model":"seedance-2.5-text-to-video","prompt":prompt,
      "options":{"aspect_ratio":"16:9","duration":dur,"quality":"1080p","generate_audio":True,"web_search":False},"credits":1,"isPublic":False}
d=None
for a in range(15):
    r=c.post(B+"/api/ai/generate",json=body); t=r.text
    log("submit",a,t[:170])
    try: d=json.loads(t)["data"]; log("COST",d.get("costCredits")); break
    except Exception: time.sleep(40)
if d:
    for i in range(150):
        time.sleep(10)
        try: x=c.get(B+"/api/ai/tasks/"+d["id"]).json()["data"]
        except Exception: continue
        if i%6==0: log("poll",i,x.get("status"))
        if x.get("status") in ("success","failed"):
            log("final",x.get("status"),x.get("errorMessage"))
            if x.get("status")=="success":
                u=json.loads(x["taskInfo"])["videos"][0]["videoUrl"]
                fn=os.path.join(OUT,"_%s.mp4"%tag)
                with httpx.stream("GET",u,headers={"User-Agent":UA["User-Agent"]},timeout=900) as r2, open(fn,"wb") as o:
                    for ch in r2.iter_bytes(1<<20): o.write(ch)
                json.dump(x,open(os.path.join(OUT,"_%s_task.json"%tag),"w"),indent=1)
                log("saved",os.path.getsize(fn))
            break
log("bal1",c.post(B+"/api/user/get-user-credits",json={}).text[:80])