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

from . import paper, tender, wechat

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


def _evidence(draft: dict, art: dict) -> dict:
    """按来源等级出不同形状的 evidence。

    公开来源给 URL 加快照；一手来源两样都没有，改为交代渠道类型与获取日期。
    """
    retrieved = draft.get("retrieved") or datetime.now(CST).strftime("%Y-%m-%d")
    if draft.get("tier") == "first-party":
        ev = {"tier": "first-party", "method": draft.get("method") or "", "retrieved": retrieved}
        if draft.get("note"):
            ev["note"] = draft["note"]
        return ev
    return {
        "url": art.get("url") or draft.get("manual_url") or "",
        "publisher": art.get("account") or draft.get("publisher") or "",
        "tier": draft.get("tier") or "official",
        "retrieved": retrieved,
        "snapshot": draft.get("snapshot") or "",
    }


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
        "evidence": [_evidence(draft, art)],
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
    if draft.get("counterparties"):
        event["counterparties"] = [c for c in draft["counterparties"] if str(c).strip()]
    if draft.get("amount"):
        event["amount"] = draft["amount"]

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
    kind: str = "wechat"          # wechat | tender | paper


@app.post("/api/parse")
def api_parse(payload: ParseIn) -> JSONResponse:
    source = payload.source.strip()
    if not source:
        raise HTTPException(400, "内容为空")
    if payload.kind == "tender":
        return _parse_tender(source)
    if payload.kind == "paper":
        return _parse_paper(source)

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


def _parse_tender(source: str) -> JSONResponse:
    """招投标公告转草稿。

    中标人自动匹配到 registry 只给候选、不自动绑定——认错主体比没认出来更糟。
    采购人按约定进 counterparties 纯文本，不建实体。
    """
    t = tender.parse(source)
    art = wechat.Article(title=t.project or "招投标公告", html=source)
    snapshot = (
        wechat.save_snapshot(ROOT, art, t.date, prefix="tender")
        if source.lstrip().startswith("<")
        else ""
    )

    candidates = tender.match_orgs(t.winner, load_orgs_full())
    orgs = [{"id": candidates[0]["id"], "role": "supplier"}] if len(candidates) == 1 else []

    draft = {
        "id": uuid.uuid4().hex[:12],
        "created": datetime.now(CST).isoformat(timespec="seconds"),
        "kind": "tender",
        "article": {
            "url": "",
            "title": t.project or "招投标公告",
            "account": t.agent or "",
            "published": t.date,
            "published_basis": "stated" if t.date else "",
            "body": t.text,
            "images": [],
            "warnings": t.warnings
            + ([f"中标人「{t.winner}」匹配到多个主体，需人工选定" ] if len(candidates) > 1 else [])
            + ([f"中标人「{t.winner}」在 registry 里没有对应主体，需先建条目" ]
               if t.winner and not candidates else []),
        },
        "snapshot": snapshot,
        "date": t.date,
        "date_precision": t.date_precision or "day",
        "date_basis": "stated",
        "title_zh": t.project or "",
        "summary_zh": _tender_summary(t),
        "type": "procurement",
        "tier": "primary",           # 招标公告是一手文件
        "corroboration": "single",
        "orgs": orgs,
        "counterparties": [t.buyer] if t.buyer else [],
        "axes": {},
        "status": "draft",
        "org_candidates": candidates,
        "winner_raw": t.winner,
    }
    if t.amount_value is not None:
        draft["amount"] = {"value": t.amount_value, "currency": t.amount_currency}
        draft["amount_raw"] = t.amount_raw
    save_draft(draft)
    return JSONResponse({"draft": draft, "extract": t.summary_dict()})


def _parse_paper(source: str) -> JSONResponse:
    """论文转草稿。轴取值只给候选并附原文片段，由人确认。"""
    p = paper.load(source)
    kw = paper.load_keywords(ROOT)
    blob = f"{p.title} {p.abstract}"
    candidates = paper.extract_axes(blob, kw)

    # ⚠️ 只拿作者串匹配，绝不拿摘要正文匹配。
    # 摘要里的「deployment on a Unitree G1」说的是论文用了谁家硬件，
    # 不是论文由谁所写。混在一起会把高校论文记成本体厂商的技术信号。
    org_hits = paper.match_orgs(" ".join(p.authors), load_orgs_full())
    # 单独算一次「摘要里提到哪些主体」，只作提示，不参与主体判定
    mentioned = [
        h for h in paper.match_orgs(blob, load_orgs_full())
        if h["id"] not in {x["id"] for x in org_hits}
    ]

    art = wechat.Article(title=p.title, html=p.html, url=p.url)
    snapshot = wechat.save_snapshot(ROOT, art, p.published, prefix="arxiv") if p.html else ""

    warnings = list(p.warnings)
    if not org_hits:
        warnings.append(
            "作者里没匹配到 registry 主体。arXiv 元数据不含机构字段，所以必须人工判定作者归属；"
            "若这篇确实只有高校参与，就不该入库——本库只收产业主体"
        )
    if mentioned:
        names = "、".join(f"{h['zh']}（{h['matched']}）" for h in mentioned)
        warnings.append(
            f"摘要里提到了 {names}，但那是论文用了谁家硬件或工具，不等于论文由谁所写，别直接当主体"
        )
    if candidates:
        warnings.append(
            "轴取值是关键词候选，不是结论：命中可能来自相关工作而非本文方法，逐条看片段再确认"
        )
    warnings.append("论文的轴信号弱于产品发布——它说明团队研究过什么，不说明产品里跑什么")

    draft = {
        "id": uuid.uuid4().hex[:12],
        "created": datetime.now(CST).isoformat(timespec="seconds"),
        "kind": "paper",
        "article": {
            "url": p.url,
            "title": p.title,
            "account": "arXiv" if p.arxiv_id else "",
            "published": p.published,
            "published_basis": "stated" if p.published else "",
            "body": p.abstract,
            "images": [],
            "warnings": warnings,
        },
        "snapshot": snapshot,
        "date": p.published,
        "date_precision": "day" if p.published else "",
        "date_basis": "stated",
        "title_zh": p.title,
        "summary_zh": "",
        "type": "publication",
        "tier": "primary",           # 论文是一手文件
        "corroboration": "single",
        # 论文一律不自动填主体：作者机构靠文本猜不可靠，猜错就是把别人的论文
        # 记成某家公司的技术信号，比留空糟得多。
        "orgs": [],
        "axes": {},
        "axis_candidates": candidates,
        "org_candidates": org_hits,
        "orgs_mentioned": mentioned,
        "arxiv_id": p.arxiv_id,
        "status": "draft",
    }
    save_draft(draft)
    return JSONResponse({"draft": draft, "extract": p.summary_dict()})


def _tender_summary(t: tender.Tender) -> str:
    """只陈述公告写了什么，不加判断。"""
    parts = []
    if t.winner:
        parts.append(f"{t.winner}中标")
    if t.project:
        parts.append(t.project)
    if t.amount_value is not None:
        parts.append(f"金额 {t.amount_raw}")
    if t.project_no:
        parts.append(f"项目编号 {t.project_no}")
    return "，".join(parts) + ("。" if parts else "")


def load_orgs_full() -> list[dict]:
    """带别名的主体名单，供中标人匹配用。"""
    folder = ROOT / "registry/orgs"
    out = []
    if folder.exists():
        for path in sorted(folder.glob("*.yaml")):
            doc = yaml.safe_load(path.read_text()) or {}
            names = doc.get("names") or {}
            out.append({
                "id": doc.get("id"),
                "zh": names.get("zh"),
                "en": names.get("en"),
                "aliases": names.get("aliases") or [],
            })
    return out


@app.get("/api/bootstrap")
def api_bootstrap() -> dict:
    vocab = load_vocab()
    return {
        "orgs": load_orgs(),
        "axes": vocab["axes"],
        "event_types": vocab["enums"]["event_types"],
        "org_roles": vocab["enums"]["org_roles"],
        "source_tiers": vocab["enums"]["source_tiers"],
        "first_party_methods": vocab["enums"]["first_party_methods"],
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

    # 一手来源给不出 URL 和快照，改为必须交代渠道与获取日期
    if draft.get("tier") == "first-party":
        if not draft.get("method"):
            missing.append("method（一手来源必须交代渠道类型）")
        if not draft.get("retrieved"):
            missing.append("retrieved（获取日期）")
    else:
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
    import os

    import uvicorn

    # 默认只听本机。换机器或要从手机访问时用环境变量覆盖，不必改代码。
    host = os.environ.get("EID_HOST", "127.0.0.1")
    port = int(os.environ.get("EID_PORT", "8790"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
