import json, pathlib
from bs4 import BeautifulSoup
from pypdf import PdfReader
import yaml
root=pathlib.Path("snapshots/2026/10/intake-audit-20261001")
out=pathlib.Path("audit-readable");out.mkdir(exist_ok=True)
for r in json.loads((root/"manifest.json").read_text()):
 if "path" not in r: continue
 p=pathlib.Path(r["path"])
 if p.suffix==".pdf":
  text="\n".join(page.extract_text() for page in PdfReader(p).pages)
 elif p.suffix==".html":
  s=BeautifulSoup(p.read_bytes(),"html.parser")
  for tag in s(["script","style","nav","footer","header","noscript"]):tag.decompose()
  main=None
  for sel in [".lph-article-comView", ".article-content", ".article-detail", "#paragraph", "#content", ".post-content", ".content", "article", "main"]:
   el=s.select_one(sel)
   if el and len(el.get_text())>300: main=el;break
  text=(main or s).get_text("\n",strip=True)
 else: text=p.read_text()
 (out/(str(r["index"])+".txt")).write_text(text)
events=[]
for p in pathlib.Path("events").rglob("*.yaml"):
 e=yaml.safe_load(p.read_text())
 events.append({"path":str(p),"id":e["id"],"orgs":e.get("orgs"),"title":e.get("title"),"summary":e.get("summary"),"evidence":e.get("evidence")})
(out/"existing-events.json").write_text(json.dumps(events,ensure_ascii=False,default=str))
orgs=[yaml.safe_load(p.read_text()) for p in pathlib.Path("registry/orgs").glob("*.yaml")]
(out/"existing-orgs.json").write_text(json.dumps(orgs,ensure_ascii=False,default=str))
print("Extracted",len(events),"events,",len(orgs),"orgs")

for org in orgs:
 group=[e for e in events if any(o["id"]==org["id"] for o in (e.get("orgs") or []))]
 (out/("events-"+org["id"]+".json")).write_text(json.dumps(group,ensure_ascii=False,default=str))
