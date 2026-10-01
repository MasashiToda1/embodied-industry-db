import concurrent.futures, json, pathlib, urllib.request, time
urls=json.loads(pathlib.Path("evidence-urls.json").read_text())
root=pathlib.Path("snapshots/2026/10/intake-audit-20261001")
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
