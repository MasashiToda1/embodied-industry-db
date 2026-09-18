"""具身产业库入库后台。

粘 URL 或整页 HTML 进来，解出微信文章，存快照，生成待审事件草稿。
审过之后才写进 events/。草稿不进 git。

    make serve        # 或 .venv/bin/python -m ingest.server
    http://127.0.0.1:8790
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from . import wechat

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
CST = timezone(timedelta(hours=8))

app = FastAPI(title="具身产业库入库后台")


# ---------------------------------------------------------------- 词表与名单

def load_vocab() -> dict:
    axes = {}
    for name in ("tech", "data", "business"):
        doc = yaml.safe_load((ROOT / f"vocab/axes-{name}.yaml").read_text())
        for axis in doc["axes"]:
            axes[axis["field"]] = {
                "zh": axis["zh"],
                "group": name,
                "multi": axis.get("multi", False),
                "values": [{"id": v["id"], "zh": v["zh"]} for v in axis["values"]],
            }
    enums = yaml.safe_load((ROOT / "vocab/enums.yaml").read_text())
    return {"axes": axes, "enums": enums}


def load_orgs() -> list[dict]:
    folder = ROOT / "registry/orgs"
    out = []
    if folder.exists():
        for path in sorted(folder.glob("*.yaml")):
            doc = yaml.safe_load(path.read_text()) or {}
            names = doc.get("names") or {}
            out.append({"id": doc.get("id"), "zh": names.get("zh") or doc.get("id")})
    return out


# ---------------------------------------------------------------- 草稿存取

def draft_path(did: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8,32}", did):
        raise HTTPException(400, "草稿 id 不合法")
    return DRAFTS / f"{did}.json"


def list_drafts() -> list[dict]:
    DRAFTS.mkdir(exist_ok=True)
    items = []
    for path in sorted(DRAFTS.glob("*.json"), reverse=True):
        items.append(json.loads(path.read_text()))
    return items


def save_draft(draft: dict) -> None:
    DRAFTS.mkdir(exist_ok=True)
    draft_path(draft["id"]).write_text(
        json.dumps(draft, ensure_ascii=False, indent=2)
    )


# ---------------------------------------------------------------- 事件写出

def slugify(text: str) -> str:
    """只留 ASCII。事件 id 会进文件名和 URL，中文在跨平台和链接编码上都是雷。"""
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text or "")
    return re.sub(r"-+", "-", text).strip("-").lower()[:40]


def build_event(draft: dict) -> dict:
    """草稿转事件 YAML 结构。字段顺序刻意固定，方便 diff 阅读。"""
    art = draft["article"]
    date = draft.get("date") or art.get("published") or ""
    basis = draft.get("date_basis") or art.get("published_basis") or "stated"

    primary = (draft.get("orgs") or [{}])[0].get("id", "org")
    # 中文标题 slug 化后基本是空的，退回「类型 + 短随机」保证 id 唯一且可读
    tail = slugify(draft.get("slug") or art.get("title", ""))
    if not tail:
        tail = f"{draft.get('type') or 'event'}-{draft['id'][:4]}"
    eid = draft.get("event_id") or f"evt-{date}-{primary}-{tail}"

    event: dict = {
        "id": eid,
        "date": date,
        "date_precision": draft.get("date_precision") or "day",
        "type": draft.get("type") or "statement",
        "orgs": [
            {"id": o["id"], "role": o.get("role") or "subject"}
            for o in draft.get("orgs") or []
            if o.get("id")
        ],
        "title": {"zh": draft.get("title_zh") or art.get("title", "")},
        "summary": {"zh": draft.get("summary_zh") or ""},
        "evidence": [
            {
                "url": art.get("url") or draft.get("manual_url") or "",
                "publisher": art.get("account") or draft.get("publisher") or "",
                "tier": draft.get("tier") or "official",
                "retrieved": draft.get("retrieved") or datetime.now(CST).strftime("%Y-%m-%d"),
                "snapshot": draft.get("snapshot") or "",
            }
        ],
        "corroboration": draft.get("corroboration") or "single",
    }

    if basis != "stated":
        event["date_basis"] = basis
        event["date_as_stated"] = draft.get("date_as_stated") or ""

    if draft.get("title_en"):
        event["title"]["en"] = draft["title_en"]
    if draft.get("summary_en"):
        event["summary"]["en"] = draft["summary_en"]
    if draft.get("datasets"):
        event["datasets"] = draft["datasets"]

    axes = {k: v for k, v in (draft.get("axes") or {}).items() if v}
    if axes:
        event["axes"] = axes
    return event


def write_event(event: dict) -> str:
    date = str(event["date"])
    year = date[:4]
    month = date[5:7] if len(date) >= 7 and date[5:7].isdigit() else "00"
    folder = ROOT / "events" / year / month
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{event['id']}.yaml"
    if path.exists():
        raise HTTPException(409, f"事件已存在：{path.relative_to(ROOT)}")
    path.write_text(
        yaml.safe_dump(event, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return str(path.relative_to(ROOT))


# ---------------------------------------------------------------- 接口

class ParseIn(BaseModel):
    source: str
    is_url: bool | None = None


@app.post("/api/parse")
def api_parse(payload: ParseIn) -> JSONResponse:
    source = payload.source.strip()
    if not source:
        raise HTTPException(400, "内容为空")

    art = wechat.load(source, payload.is_url)
    snapshot = ""
    if art.html:
        snapshot = wechat.save_snapshot(ROOT, art, art.published)

    draft = {
        "id": uuid.uuid4().hex[:12],
        "created": datetime.now(CST).isoformat(timespec="seconds"),
        "article": {
            "url": art.url,
            "title": art.title,
            "account": art.account,
            "account_id": art.account_id,
            "published": art.published,
            "published_basis": art.published_basis,
            "body": art.body,
            "images": art.images,
            "warnings": art.warnings,
        },
        "snapshot": snapshot,
        "date": art.published,
        "date_precision": "day" if art.published else "",
        "date_basis": art.published_basis or "stated",
        "title_zh": art.title,
        "type": "statement",
        "tier": "official",
        "corroboration": "single",
        "orgs": [],
        "axes": {},
        "status": "draft",
    }
    save_draft(draft)
    return JSONResponse({"draft": draft, "extract": art.summary_dict()})


@app.get("/api/bootstrap")
def api_bootstrap() -> dict:
    vocab = load_vocab()
    return {
        "orgs": load_orgs(),
        "axes": vocab["axes"],
        "event_types": vocab["enums"]["event_types"],
        "org_roles": vocab["enums"]["org_roles"],
        "source_tiers": vocab["enums"]["source_tiers"],
        "corroboration": vocab["enums"]["corroboration"],
        "date_precision": vocab["enums"]["date_precision"],
        "date_basis": vocab["enums"]["date_basis"],
    }


@app.get("/api/drafts")
def api_drafts() -> dict:
    return {"drafts": list_drafts()}


@app.patch("/api/drafts/{did}")
def api_update(did: str, payload: dict) -> dict:
    path = draft_path(did)
    if not path.exists():
        raise HTTPException(404, "草稿不存在")
    draft = json.loads(path.read_text())
    for key, value in payload.items():
        if key in ("id", "created", "article", "snapshot"):
            continue
        draft[key] = value
    save_draft(draft)
    return {"draft": draft, "preview": yaml.safe_dump(build_event(draft), allow_unicode=True, sort_keys=False)}


@app.get("/api/drafts/{did}/preview")
def api_preview(did: str) -> dict:
    path = draft_path(did)
    if not path.exists():
        raise HTTPException(404, "草稿不存在")
    draft = json.loads(path.read_text())
    return {"yaml": yaml.safe_dump(build_event(draft), allow_unicode=True, sort_keys=False)}


@app.post("/api/drafts/{did}/approve")
def api_approve(did: str) -> dict:
    path = draft_path(did)
    if not path.exists():
        raise HTTPException(404, "草稿不存在")
    draft = json.loads(path.read_text())

    missing = []
    if not draft.get("date"):
        missing.append("date")
    if not draft.get("orgs"):
        missing.append("orgs（至少一个主体）")
    if not draft.get("snapshot"):
        missing.append("snapshot")
    if not (draft["article"].get("url") or draft.get("manual_url")):
        missing.append("来源 URL（粘贴 HTML 时需手填原文链接）")
    if missing:
        raise HTTPException(400, "还差：" + "、".join(missing))

    event = build_event(draft)
    rel = write_event(event)
    path.unlink()
    return {"written": rel, "event_id": event["id"]}


@app.delete("/api/drafts/{did}")
def api_delete(did: str) -> dict:
    path = draft_path(did)
    if path.exists():
        path.unlink()
    return {"deleted": did}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8790)


if __name__ == "__main__":
    main()
