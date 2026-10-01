import concurrent.futures, json, pathlib, urllib.request, time
urls=json.loads(pathlib.Path("evidence-urls.json").read_text())
root=pathlib.Path("snapshots/2026/10/identity-followup-20261001")
root.mkdir(parents=True,exist_ok=True)
def get(pair):
 i,url=pair
 result={"index":i,"url":url}
 try:
  req=urllib.request.Request(url,headers={"User-Agent":"embodied-industry-db evidence verification"})
  with urllib.request.urlopen(req,timeout=35) as r:
   data=r.read(5000001)
   result.update(status=r.status,final_url=r.url,content_type=r.headers.get("Content-Type",""))
  if len(data)>5000000: raise ValueError("source over 5 MB")
  suffix=".pdf" if data.startswith(b"%PDF") else ".json" if "json" in result["content_type"] else ".md" if "/raw/" in url else ".html"
  path=root/(str(i)+suffix)
  path.write_bytes(data)
  result.update(path=str(path),bytes=len(data))
 except Exception as e: result["error"]=str(e)
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 results=list(pool.map(get,enumerate(urls)))
(root/"manifest.json").write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False))


from bs4 import BeautifulSoup
from pypdf import PdfReader
out=pathlib.Path("audit-followup");out.mkdir(exist_ok=True)
for r in results:
 if "path" not in r: continue
 p=pathlib.Path(r["path"])
 if p.suffix==".pdf": text="\n".join(page.extract_text() or "" for page in PdfReader(p).pages)
 else:
  soup=BeautifulSoup(p.read_bytes(),"html.parser")
  for e in soup(["script","style","nav","header"]):e.decompose()
  text=soup.get_text("\n",strip=True)
 (out/(str(r["index"])+".txt")).write_text(text)
import yaml
(out/"registry-main.json").write_text(json.dumps([yaml.safe_load(p.read_text()) for p in pathlib.Path("registry/orgs").glob("*.yaml")],ensure_ascii=False))

import re
asset=root/"13.html"
if asset.exists():
 s=asset.read_text()
 s=re.sub(r"\\u([0-9a-fA-F]{4})",lambda m:chr(int(m.group(1),16)),s)
 keys=["广州灵境","FlexPhysics","FlatWorld","StateLeWM","huggingface.co","github.com","关于","仿真数据"]
 found=[]
 for k in keys:
  for m in list(re.finditer(re.escape(k),s))[:12]:found.append({"key":k,"context":s[max(0,m.start()-200):m.end()+650]})
 (out/"flex-asset-excerpts.json").write_text(json.dumps(found,ensure_ascii=False))
