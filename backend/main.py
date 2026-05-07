"""
TenderAI FastAPI Backend
Provides REST API for: tenders, bidders, document upload, evaluation, reports, audit log.
"""
import json, os, uuid, sys
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.database import get_db, init_db, Tender, Bidder, Evaluation, AuditLog
from services.evaluator import (
    CriteriaExtractor, evaluate_bidder_full, extract_text_from_file, make_hash
)
from services.report_generator import generate_docx_report

app = FastAPI(title="TenderAI API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORTS_DIR = os.path.join(BASE_DIR, "..", "reports")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
os.makedirs(UPLOAD_DIR + "/tenders", exist_ok=True)
os.makedirs(UPLOAD_DIR + "/bidders", exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Init DB on startup
@app.on_event("startup")
def startup():
    init_db()

# Serve frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ── HELPERS ───────────────────────────────────────────────────────────────────
def add_audit(db: Session, tender_id, bidder_id, event_type, description, actor="system", status="info"):
    logs = db.query(AuditLog).filter(AuditLog.tender_id == tender_id).order_by(AuditLog.created_at.desc()).first()
    prev = logs.event_hash if logs else "GENESIS"
    eid = f"EVT-{uuid.uuid4().hex[:8].upper()}"
    ts = datetime.utcnow().isoformat()
    h = make_hash(eid, event_type, ts, actor, description, prev)
    log = AuditLog(
        id=eid, tender_id=tender_id, bidder_id=bidder_id,
        event_type=event_type, description=description,
        actor=actor, status=status, prev_hash=prev, event_hash=h,
        created_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()
    return log

def tender_to_dict(t: Tender) -> dict:
    try:
        criteria = json.loads(t.criteria_json or "[]")
    except:
        criteria = []
    return {
        "id": t.id, "ref": t.ref, "name": t.name, "org": t.org,
        "value": t.value, "min_turnover": t.min_turnover,
        "min_projects": t.min_projects, "emd": t.emd,
        "description": t.description, "proc_type": t.proc_type,
        "deadline": t.deadline, "criteria": criteria,
        "file_path": t.file_path,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "bidder_count": len(t.bidders) if t.bidders else 0,
        "evaluated": len(t.evaluations) > 0 if t.evaluations else False,
    }

def bidder_to_dict(b: Bidder) -> dict:
    try:
        fps = json.loads(b.file_paths or "[]")
    except:
        fps = []
    return {
        "id": b.id, "tender_id": b.tender_id,
        "company": b.company, "gstin": b.gstin, "pan": b.pan,
        "cin": b.cin, "state": b.state, "net_worth": b.net_worth,
        "turnover_21_22": b.turnover_21_22,
        "turnover_22_23": b.turnover_22_23,
        "turnover_23_24": b.turnover_23_24,
        "avg_turnover": b.avg_turnover,
        "projects": b.projects, "exp_text": b.exp_text,
        "docs_list": b.docs_list, "gstn_valid": b.gstn_valid,
        "file_paths": fps,
        "created_at": b.created_at.isoformat() if b.created_at else "",
    }


# ── HEALTH ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0", "time": datetime.utcnow().isoformat()}


# ── TENDERS ───────────────────────────────────────────────────────────────────
@app.get("/api/tenders")
def list_tenders(db: Session = Depends(get_db)):
    tenders = db.query(Tender).order_by(Tender.created_at.desc()).all()
    return [tender_to_dict(t) for t in tenders]

@app.get("/api/tenders/{tid}")
def get_tender(tid: str, db: Session = Depends(get_db)):
    t = db.query(Tender).filter(Tender.id == tid).first()
    if not t:
        raise HTTPException(404, "Tender not found")
    return tender_to_dict(t)

@app.post("/api/tenders")
async def create_tender(
    ref:          str = Form(...),
    name:         str = Form(...),
    org:          str = Form(...),
    value:        float = Form(0),
    min_turnover: float = Form(5),
    min_projects: int   = Form(3),
    emd:          float = Form(0),
    description:  str = Form(""),
    proc_type:    str = Form("Open Tender Enquiry (OTE)"),
    deadline:     str = Form(""),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # Extract text from uploaded file if provided
    extra_text = ""
    file_path_saved = ""
    if file and file.filename:
        ext = file.filename.split(".")[-1].lower()
        save_path = os.path.join(UPLOAD_DIR, "tenders", f"{uuid.uuid4().hex}.{ext}")
        content = await file.read()
        with open(save_path, "wb") as f_:
            f_.write(content)
        file_path_saved = save_path
        extra_text = extract_text_from_file(save_path)

    # Combine form description + file text
    full_text = description + "\n" + extra_text

    # Extract criteria
    extractor = CriteriaExtractor()
    criteria = extractor.extract(full_text, {
        "min_turnover": min_turnover,
        "min_projects": min_projects,
        "emd": emd
    })

    tid = "T-" + uuid.uuid4().hex[:8].upper()
    tender = Tender(
        id=tid, ref=ref, name=name, org=org, value=value,
        min_turnover=min_turnover, min_projects=min_projects, emd=emd,
        description=full_text[:5000], proc_type=proc_type, deadline=deadline,
        criteria_json=json.dumps(criteria), file_path=file_path_saved,
        created_at=datetime.utcnow()
    )
    db.add(tender)
    db.commit()
    add_audit(db, tid, None, "TENDER_INGESTED",
              f"Tender '{ref}' created — {len(criteria)} criteria extracted", status="ok")
    return tender_to_dict(tender)

@app.delete("/api/tenders/{tid}")
def delete_tender(tid: str, db: Session = Depends(get_db)):
    t = db.query(Tender).filter(Tender.id == tid).first()
    if not t:
        raise HTTPException(404, "Tender not found")
    db.delete(t)
    db.commit()
    return {"deleted": True}


# ── BIDDERS ───────────────────────────────────────────────────────────────────
@app.get("/api/tenders/{tid}/bidders")
def list_bidders(tid: str, db: Session = Depends(get_db)):
    bidders = db.query(Bidder).filter(Bidder.tender_id == tid).order_by(Bidder.created_at).all()
    return [bidder_to_dict(b) for b in bidders]

@app.get("/api/bidders/{bid}")
def get_bidder(bid: str, db: Session = Depends(get_db)):
    b = db.query(Bidder).filter(Bidder.id == bid).first()
    if not b:
        raise HTTPException(404, "Bidder not found")
    return bidder_to_dict(b)

@app.post("/api/tenders/{tid}/bidders")
async def create_bidder(
    tid:         str,
    company:     str   = Form(...),
    gstin:       str   = Form(""),
    pan:         str   = Form(""),
    cin:         str   = Form(""),
    state:       str   = Form(""),
    net_worth:   str   = Form(""),
    t_21_22:     str   = Form(""),
    t_22_23:     str   = Form(""),
    t_23_24:     str   = Form(""),
    projects:    int   = Form(0),
    exp_text:    str   = Form(""),
    docs_list:   str   = Form(""),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    tender = db.query(Tender).filter(Tender.id == tid).first()
    if not tender:
        raise HTTPException(404, "Tender not found")

    # Save uploaded files + extract text
    saved_paths = []
    extracted_texts = []
    for f in files:
        if f and f.filename:
            ext = f.filename.split(".")[-1].lower()
            save_path = os.path.join(UPLOAD_DIR, "bidders", f"{uuid.uuid4().hex}_{f.filename}")
            content = await f.read()
            with open(save_path, "wb") as fp:
                fp.write(content)
            saved_paths.append({"name": f.filename, "path": save_path})
            text = extract_text_from_file(save_path)
            if text and not text.startswith("[EXTRACTION_ERROR"):
                extracted_texts.append(text)

    # Auto-extract docs from file text if docs_list not provided
    combined_text = "\n".join(extracted_texts)
    auto_docs = []
    if combined_text:
        doc_keywords = {
            "GSTIN Certificate": ["gstin", "gst registration", "gst certificate"],
            "PAN Card": ["pan card", "permanent account number"],
            "ISO 9001:2015": ["iso 9001"],
            "NSIC Registration": ["nsic"],
            "MSME Certificate": ["msme", "udyam"],
            "Integrity Pact": ["integrity pact"],
            "Balance Sheet": ["balance sheet", "audited", "turnover"],
            "Experience Certificate": ["experience certificate", "completion certificate", "performance certificate"],
            "Non-Blacklisting Declaration": ["non-blacklisting", "blacklisted", "debarred"],
        }
        for doc_name, kws in doc_keywords.items():
            if any(kw in combined_text.lower() for kw in kws):
                auto_docs.append(doc_name)

    final_docs = docs_list
    if auto_docs and not docs_list:
        final_docs = ", ".join(auto_docs)

    # Parse numerics
    def safe_float(v):
        try: return float(v) if v else None
        except: return None

    nw  = safe_float(net_worth)
    t1  = safe_float(t_21_22)
    t2  = safe_float(t_22_23)
    t3  = safe_float(t_23_24)
    vals = [x for x in [t1,t2,t3] if x is not None]
    avg = sum(vals)/len(vals) if vals else 0

    from services.evaluator import verify_gstin_real
    gstn_result = verify_gstin_real(gstin.upper()) if gstin else {"verified": False}

    bid = "B-" + uuid.uuid4().hex[:8].upper()
    bidder = Bidder(
        id=bid, tender_id=tid,
        company=company, gstin=gstin.upper(), pan=pan.upper(), cin=cin,
        state=state, net_worth=nw,
        turnover_21_22=t1, turnover_22_23=t2, turnover_23_24=t3,
        avg_turnover=round(avg, 4),
        projects=projects, exp_text=exp_text,
        docs_list=final_docs,
        gstn_valid=gstn_result.get("verified", False),
        file_paths=json.dumps(saved_paths),
        created_at=datetime.utcnow()
    )
    db.add(bidder)
    db.commit()
    add_audit(db, tid, bid, "DOCUMENT_UPLOADED",
              f"Bidder '{company}' registered — {len(saved_paths)} file(s) uploaded", status="ok")
    return bidder_to_dict(bidder)

@app.delete("/api/bidders/{bid}")
def delete_bidder(bid: str, db: Session = Depends(get_db)):
    b = db.query(Bidder).filter(Bidder.id == bid).first()
    if not b:
        raise HTTPException(404, "Bidder not found")
    db.delete(b)
    db.commit()
    return {"deleted": True}


# ── EVALUATION ────────────────────────────────────────────────────────────────
@app.post("/api/tenders/{tid}/evaluate")
def run_evaluation(tid: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tid).first()
    if not tender:
        raise HTTPException(404, "Tender not found")

    bidders = db.query(Bidder).filter(Bidder.tender_id == tid).all()
    if not bidders:
        raise HTTPException(400, "No bidders registered for this tender")

    try:
        criteria = json.loads(tender.criteria_json or "[]")
    except:
        criteria = []

    if not criteria:
        extractor = CriteriaExtractor()
        criteria = extractor.extract(tender.description or "", {
            "min_turnover": tender.min_turnover,
            "min_projects": tender.min_projects,
            "emd": tender.emd
        })
        tender.criteria_json = json.dumps(criteria)
        db.commit()

    add_audit(db, tid, None, "EVALUATION_STARTED",
              f"Evaluation started for {tender.ref} — {len(bidders)} bidder(s)", status="info")

    results = []
    for b in bidders:
        bidder_dict = {
            "id": b.id, "company": b.company,
            "gstin": b.gstin, "pan": b.pan,
            "avg_turnover": b.avg_turnover or 0,
            "net_worth": b.net_worth,
            "projects": b.projects,
            "exp_text": b.exp_text or "",
            "docs_list": b.docs_list or "",
        }
        tender_dict = {
            "id": tender.id, "name": tender.name,
            "description": tender.description or "",
            "min_turnover": tender.min_turnover,
            "min_projects": tender.min_projects,
            "emd": tender.emd,
        }

        ev = evaluate_bidder_full(bidder_dict, tender_dict, criteria)

        # Delete previous evaluation for this bidder+tender
        db.query(Evaluation).filter(
            Evaluation.tender_id == tid,
            Evaluation.bidder_id == b.id
        ).delete()

        evaluation = Evaluation(
            id="E-" + uuid.uuid4().hex[:8].upper(),
            tender_id=tid, bidder_id=b.id,
            overall_status=ev["overall"],
            confidence=ev["confidence"],
            mandatory_pass=ev["mand_pass"],
            mandatory_total=ev["mand_total"],
            optional_score=ev["opt_score"],
            has_review=ev["has_review"],
            results_json=json.dumps(ev["results"]),
            report_json=json.dumps(ev),
            evaluated_at=datetime.utcnow()
        )
        db.add(evaluation)
        db.commit()

        add_audit(db, tid, b.id, "EVALUATION_COMPLETED",
                  f"{b.company}: {ev['overall'].upper()} "
                  f"({ev['mand_pass']}/{ev['mand_total']} mandatory, {ev['confidence']*100:.0f}% conf)",
                  actor="ai_engine",
                  status="ok" if ev["overall"]=="eligible" else "err")

        results.append({
            "bidder_id": b.id,
            "company": b.company,
            "overall": ev["overall"],
            "confidence": ev["confidence"],
            "mand_pass": ev["mand_pass"],
            "mand_total": ev["mand_total"],
            "opt_score": ev["opt_score"],
            "has_review": ev["has_review"],
            "results": ev["results"],
        })

    return {
        "tender_id": tid,
        "total": len(results),
        "eligible": sum(1 for r in results if r["overall"]=="eligible"),
        "ineligible": sum(1 for r in results if r["overall"]=="ineligible"),
        "results": results
    }

@app.get("/api/tenders/{tid}/evaluation")
def get_evaluation(tid: str, db: Session = Depends(get_db)):
    evals = db.query(Evaluation).filter(Evaluation.tender_id == tid).all()
    results = []
    for ev in evals:
        b = db.query(Bidder).filter(Bidder.id == ev.bidder_id).first()
        try:
            res = json.loads(ev.results_json or "[]")
        except:
            res = []
        results.append({
            "bidder_id": ev.bidder_id,
            "company": b.company if b else "",
            "overall": ev.overall_status,
            "confidence": ev.confidence,
            "mand_pass": ev.mandatory_pass,
            "mand_total": ev.mandatory_total,
            "opt_score": ev.optional_score,
            "has_review": ev.has_review,
            "results": res,
            "evaluated_at": ev.evaluated_at.isoformat() if ev.evaluated_at else "",
        })
    return results


# ── REPORTS ───────────────────────────────────────────────────────────────────
@app.get("/api/tenders/{tid}/report/docx")
def download_report(tid: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tid).first()
    if not tender:
        raise HTTPException(404, "Tender not found")

    evals = db.query(Evaluation).filter(Evaluation.tender_id == tid).all()
    if not evals:
        raise HTTPException(400, "No evaluations found. Run evaluation first.")

    evaluations_data = []
    for ev in evals:
        b = db.query(Bidder).filter(Bidder.id == ev.bidder_id).first()
        try:
            results = json.loads(ev.results_json or "[]")
        except:
            results = []
        evaluations_data.append({
            "bidder": bidder_to_dict(b) if b else {},
            "evaluation": {
                "overall": ev.overall_status,
                "confidence": ev.confidence,
                "mand_pass": ev.mandatory_pass,
                "mand_total": ev.mandatory_total,
                "opt_score": ev.optional_score,
                "has_review": ev.has_review,
            },
            "criteria_results": results,
        })

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_ref = tender.ref.replace("/", "-").replace(" ", "_")
    out_path = os.path.join(REPORTS_DIR, f"TenderEval_{safe_ref}_{ts}.docx")

    generate_docx_report(tender_to_dict(tender), evaluations_data, out_path)

    add_audit(db, tid, None, "REPORT_GENERATED",
              f"DOCX report generated for {tender.ref}", actor="Officer-001", status="ok")

    return FileResponse(
        path=out_path,
        filename=f"TenderEval_{safe_ref}_{ts}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# ── AUDIT LOG ─────────────────────────────────────────────────────────────────
@app.get("/api/audit")
def get_audit(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{
        "id": l.id, "tender_id": l.tender_id, "bidder_id": l.bidder_id,
        "event_type": l.event_type, "description": l.description,
        "actor": l.actor, "status": l.status,
        "prev_hash": l.prev_hash, "event_hash": l.event_hash,
        "created_at": l.created_at.isoformat() if l.created_at else "",
    } for l in logs]

@app.get("/api/audit/verify")
def verify_audit(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at).all()
    issues = []
    prev = "GENESIS"
    for log in logs:
        expected = make_hash(log.id, log.event_type,
                             log.created_at.isoformat() if log.created_at else "",
                             log.actor, log.description, log.prev_hash)
        if log.prev_hash != prev:
            issues.append(f"Chain broken at {log.id}")
        prev = log.event_hash
    return {
        "valid": len(issues) == 0,
        "total_events": len(logs),
        "issues": issues,
        "message": "✅ Audit chain intact" if not issues else f"❌ {len(issues)} issue(s)"
    }


# ── GSTN VERIFY ───────────────────────────────────────────────────────────────
@app.get("/api/verify/gstin/{gstin}")
def verify_gstin_endpoint(gstin: str):
    from services.evaluator import verify_gstin_real
    result = verify_gstin_real(gstin.upper())
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
