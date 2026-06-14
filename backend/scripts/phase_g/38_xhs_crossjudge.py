import json, re, urllib.request, time
from concurrent.futures import ThreadPoolExecutor, as_completed
def gv(k):
    for line in open('.env.local'):
        if line.startswith(k+'='): return line.split('=',1)[1].strip().strip('"').strip("'")
BASE=gv('RESUME_COPILOT_LLM_BASE_URL'); KEY=gv('RESUME_COPILOT_LLM_API_KEY')
pairs=json.load(open('/tmp/xhs_ablation_in.json'))[:35]
SYS='你是岗位推荐相关性精排器。给"岗位对学生的fit"打0-100分,按职能/方向是否对口,不看公司名气。只输出JSON {"score":int}。'
def score(p, ev):
    u=f"学生:{p['persona']}\n意图:{p['query']}\n岗位:{p['company']} | {p['title']}\nJD:{p['jd'][:300]}"
    if ev: u+=f"\n\n参考情报:\n{ev}"
    body=json.dumps({'model':'deepseek-v4-flash','messages':[{'role':'system','content':SYS},{'role':'user','content':u}],'temperature':0,'max_tokens':2000}).encode()
    req=urllib.request.Request(BASE.rstrip('/')+'/chat/completions',data=body,headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json','User-Agent':'Mozilla/5.0'},method='POST')
    for _ in range(3):
        try:
            r=json.load(urllib.request.urlopen(req,timeout=60)); m=re.search(r'\{.*\}',r['choices'][0]['message']['content'],re.S)
            return max(0,min(100,int(json.loads(m.group(0))['score'])))
        except Exception: time.sleep(2)
    return None
def one(p):
    return {'company':p['company'][:12],'none':score(p,''),'company_ev':score(p,p['ev_company']),'generic':score(p,p['ev_generic'])}
out=[]
with ThreadPoolExecutor(max_workers=6) as ex:
    for f in as_completed([ex.submit(one,p) for p in pairs]): out.append(f.result())
import statistics as st
def delta(arm): return [r[arm]-r['none'] for r in out if r[arm] is not None and r['none'] is not None]
print(f"deepseek-flash 跨判官 {len(out)} 样本:")
for arm in ['company_ev','generic']:
    d=delta(arm); 
    print(f"  {arm:10s} 平均delta {sum(d)/len(d):+.2f} | 平均|delta| {sum(abs(x) for x in d)/len(d):.2f} | 动≥5: {sum(1 for x in d if abs(x)>=5)}/{len(d)}")
json.dump(out, open('/tmp/xhs_crossjudge_out.json','w'), ensure_ascii=False, indent=1)
