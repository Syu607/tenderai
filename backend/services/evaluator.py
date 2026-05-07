"""
Evaluation Service
Handles all AI evaluation logic: criteria extraction, document OCR,
data normalisation, rule-based evaluation, confidence scoring, explainability.
"""
import re, json, hashlib
from datetime import datetime
from typing import List, Dict, Optional


# ── GSTN API (Real endpoint — falls back to format validation) ────────────────
import requests

GSTN_API_URL = "https://api.gst.gov.in/commonapi/v1.1/taxpayerDetails"
GSTN_HEADERS = {}   # Add real headers when you get API credentials

def verify_gstin_real(gstin: str) -> dict:
    """
    Attempts real GSTN API call. Falls back to format validation.
    To enable real API: set GSTN_HEADERS with clientid and Authorization token.
    """
    if not gstin or len(gstin) != 15:
        return {"verified": False, "status": "FORMAT_INVALID", "source": "format_check"}

    valid_format = bool(re.match(r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$', gstin.upper()))
    if not valid_format:
        return {"verified": False, "status": "FORMAT_INVALID", "gstin": gstin, "source": "format_check"}

    # Try real GSTN API if credentials are set
    if GSTN_HEADERS.get("clientid"):
        try:
            resp = requests.get(
                GSTN_API_URL,
                headers=GSTN_HEADERS,
                params={"action": "TP", "gstin": gstin},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                sts = data.get("data", {}).get("sts", "").upper()
                return {
                    "verified": sts == "ACT",
                    "status": sts,
                    "legal_name": data.get("data", {}).get("lgnm", ""),
                    "trade_name": data.get("data", {}).get("tradeNam", ""),
                    "state": data.get("data", {}).get("pradr", {}).get("addr", {}).get("stcd", ""),
                    "source": "gstn_api"
                }
        except Exception:
            pass  # Fall back to format validation

    # Format-only validation (mock active/inactive based on test data)
    MOCK_STATUS = {
        "27AABCT3518Q1ZO": {"verified": True,  "status": "ACTIVE", "legal_name": "TECHVISION DEFENCE SYSTEMS PVT LTD"},
        "07AABCB4421R1Z3": {"verified": True,  "status": "ACTIVE", "legal_name": "BHARAT OPTICS AND SECURITY LTD"},
    }
    if gstin.upper() in MOCK_STATUS:
        return {**MOCK_STATUS[gstin.upper()], "source": "mock_db"}

    return {
        "verified": valid_format,
        "status": "ACTIVE" if valid_format else "FORMAT_INVALID",
        "source": "format_validation",
        "note": "Real GSTN API not configured — format validated only"
    }


# ── DOCUMENT TEXT EXTRACTION ──────────────────────────────────────────────────
def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from uploaded files.
    Supports: .txt, .pdf (via pdfplumber), .docx (via python-docx)
    """
    ext = file_path.lower().split(".")[-1]
    try:
        if ext == "txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif ext == "pdf":
            import pdfplumber
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            return "\n".join(text_parts)

        elif ext in ("docx", "doc"):
            from docx import Document
            doc = Document(file_path)
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            parts.append(cell.text)
            return "\n".join(parts)

    except Exception as e:
        return f"[EXTRACTION_ERROR: {str(e)}]"

    return ""


# ── CRITERIA EXTRACTOR ────────────────────────────────────────────────────────
class CriteriaExtractor:
    MANDATORY_MARKERS = [
        r"\bshall\b", r"\bmust\b", r"\brequired\b", r"\bmandatory\b",
        r"summarily rejected", r"failing which", r"will not be considered",
        r"liable to be rejected", r"prerequisite"
    ]
    OPTIONAL_MARKERS = [
        r"\bdesirable\b", r"\bpreferable\b", r"\bmay\b", r"\boptional\b",
        r"if available", r"wherever applicable"
    ]

    def extract(self, text: str, overrides: dict = {}) -> list:
        criteria = []
        n = 1

        def is_mandatory(ctx):
            ctx_lower = ctx.lower()
            for p in self.MANDATORY_MARKERS:
                if re.search(p, ctx_lower):
                    return True
            return False

        # Financial — turnover from overrides
        if overrides.get("min_turnover"):
            criteria.append({
                "id": f"FIN-{n:03d}", "cat": "financial", "mandatory": True,
                "desc": f"Minimum annual turnover ≥ ₹{overrides['min_turnover']} Crore (last 3 financial years)",
                "threshold": overrides["min_turnover"], "unit": "crore", "op": ">="
            }); n += 1

        # Parse text for additional criteria
        patterns = [
            (r'net\s+worth.{0,50}positive',           "financial",   True,  "Positive net worth as on 31 March (last FY)"),
            (r'EMD.{0,80}(?:Rs\.?|₹|\d)',             "financial",   True,  f"EMD of ₹{overrides.get('emd',200000):,.0f} must be submitted"),
            (r'similar\s+(works?|orders?|projects?)',  "experience",  True,  f"At least {overrides.get('min_projects',3)} similar works in last 7 financial years"),
            (r'GSTIN|GST\s+registr',                   "compliance",  True,  "Valid GSTIN registration certificate mandatory"),
            (r'PAN\s+(card|number)',                    "compliance",  True,  "PAN card copy is mandatory"),
            (r'NSIC|DGS&D',                            "compliance",  False, "NSIC/DGS&D registration (EMD exemption if applicable)"),
            (r'ISO\s+9001',                             "compliance",  False, "ISO 9001:2015 certification (desirable)"),
            (r'MSME|Udyam',                             "compliance",  False, "MSME/Udyam registration certificate (if applicable)"),
            (r'liquidation|winding.?up|insolvency',    "legal",       True,  "Not under liquidation/insolvency (self-declaration)"),
            (r'integrity\s+pact',                      "legal",       True,  "Signed Integrity Pact mandatory"),
            (r'blacklist|debarr',                      "legal",       True,  "Non-blacklisting self-declaration mandatory"),
        ]

        seen_descs = set(c["desc"] for c in criteria)
        for pattern, cat, mandatory_default, desc in patterns:
            if not text or re.search(pattern, text, re.IGNORECASE):
                if desc not in seen_descs:
                    ctx_match = re.search(pattern, text or "", re.IGNORECASE)
                    ctx = text[max(0,(ctx_match.start()-150)):ctx_match.end()+150] if ctx_match and text else ""
                    is_mand = is_mandatory(ctx) if ctx else mandatory_default
                    criteria.append({
                        "id": f"{cat[:3].upper()}-{n:03d}", "cat": cat,
                        "mandatory": is_mand or mandatory_default,
                        "desc": desc, "threshold": None, "unit": None, "op": None
                    })
                    seen_descs.add(desc)
                    n += 1

        # Always ensure GSTIN + PAN
        for cid, ccat, cdesc in [
            ("COM-GST","compliance","Valid GSTIN registration certificate mandatory"),
            ("COM-PAN","compliance","PAN card copy is mandatory"),
        ]:
            if cdesc not in seen_descs:
                criteria.append({"id": cid, "cat": ccat, "mandatory": True, "desc": cdesc,
                                  "threshold": None, "unit": None, "op": None})

        return criteria


# ── DATA NORMALIZER ───────────────────────────────────────────────────────────
UNIT_SCALE = {
    "crore":1e7,"crores":1e7,"cr":1e7,
    "lakh":1e5,"lakhs":1e5,"lac":1e5,"l":1e5,
    "thousand":1e3,"k":1e3,
    "million":1e6,"mn":1e6,"m":1e6,
    "billion":1e9,"bn":1e9,
    "rupees":1,"inr":1,"rs":1
}

def normalize_currency(text: str) -> Optional[float]:
    """Convert any Indian currency text to INR float."""
    pattern = r'(?:Rs\.?\s*|INR\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(crore|crores|cr|lakh|lakhs?|lac|thousand|million|mn|billion|bn|k|l|m)?\b'
    m = re.search(pattern, str(text), re.IGNORECASE)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "rupees").lower().strip()
    return num * UNIT_SCALE.get(unit, 1.0)


# ── SEMANTIC SIMILARITY ───────────────────────────────────────────────────────
DOMAIN_SYNONYMS = [
    ["night vision","thermal imaging","nvg","infrared","ir camera","night sight","monocular","binocular","optic","optical"],
    ["defence","defense","military","armed forces","paramilitary","crpf","bsf","itbp","army","navy","police","security","cisf","ssb"],
    ["supply","procurement","delivery","provision","furnishing","manufacture"],
    ["surveillance","cctv","camera","monitoring","tracking"],
    ["software","system","platform","application","it solution"],
]

def semantic_similarity(text1: str, text2: str) -> float:
    t1, t2 = text1.lower(), text2.lower()
    words1 = set(re.findall(r'\b\w{3,}\b', t1))
    words2 = set(re.findall(r'\b\w{3,}\b', t2))
    union = words1 | words2
    intersect = words1 & words2
    sim = len(intersect) / max(len(union), 1)
    for group in DOMAIN_SYNONYMS:
        if any(t in t1 for t in group) and any(t in t2 for t in group):
            sim = min(sim + 0.2, 1.0)
    return sim


# ── CORE EVALUATOR ────────────────────────────────────────────────────────────
def evaluate_criterion(bidder: dict, tender: dict, crit: dict) -> dict:
    cat  = crit["cat"]
    desc = crit["desc"]

    # ── FINANCIAL: Turnover
    if cat == "financial" and "turnover" in desc.lower():
        threshold = tender.get("min_turnover", 5)
        avg = bidder.get("avg_turnover", 0) or 0
        passes = avg >= threshold
        margin = avg / threshold if threshold else 1
        conf = 0.95 if (passes and margin > 1.2) else 0.89 if passes else 0.97
        return {
            "id": crit["id"], "desc": desc, "cat": cat,
            "status": "eligible" if passes else "ineligible",
            "conf": conf,
            "bidder_val": f"₹{avg:.2f} Cr (3yr avg)",
            "required_val": f"₹{threshold} Cr min",
            "src": "Audited Balance Sheets / CA Certificate",
            "reason": (f"Average annual turnover ₹{avg:.2f} Cr {'≥' if passes else '<'} required ₹{threshold} Cr. "
                       f"{'Criterion met.' if passes else 'Offer shall be summarily rejected per tender clause.'}"),
            "review": passes and margin < 1.05
        }

    # ── FINANCIAL: Net worth
    if cat == "financial" and "net worth" in desc.lower():
        nw = bidder.get("net_worth")
        if nw is None:
            return {"id":crit["id"],"desc":desc,"cat":cat,"status":"document_missing","conf":0.88,
                    "bidder_val":"Not submitted","required_val":"Positive net worth",
                    "src":"CA Certificate","reason":"Net worth certificate not found.","review":True}
        passes = float(nw) > 0
        return {"id":crit["id"],"desc":desc,"cat":cat,
                "status":"eligible" if passes else "ineligible","conf":0.92,
                "bidder_val":f"₹{nw} Cr ({'positive' if passes else 'NEGATIVE'})",
                "required_val":"Positive net worth","src":"CA Certificate",
                "reason":f"Net worth ₹{nw} Cr is {'positive — criterion met' if passes else 'NEGATIVE — disqualified'}.","review":False}

    # ── FINANCIAL: EMD
    if cat == "financial" and "emd" in desc.lower():
        docs = [d.upper() for d in (bidder.get("docs_list") or "").split(",") if d.strip()]
        has_nsic = any("NSIC" in d or "MSME" in d or "UDYAM" in d for d in docs)
        if has_nsic:
            return {"id":crit["id"],"desc":desc,"cat":cat,"status":"eligible","conf":0.95,
                    "bidder_val":"NSIC/MSME Registered — Exempt","required_val":desc,
                    "src":"NSIC/MSME Certificate","reason":"NSIC/MSME-registered firms are exempt from EMD.","review":False}
        has_emd = any("EMD" in d or "DD" in d or "DEMAND DRAFT" in d or "BANK GUARANTEE" in d for d in docs)
        return {"id":crit["id"],"desc":desc,"cat":cat,
                "status":"eligible" if has_emd else "ineligible","conf":0.90,
                "bidder_val":"DD/BG submitted" if has_emd else "NOT FOUND","required_val":desc,
                "src":"Demand Draft / Bank Guarantee",
                "reason":"EMD demand draft/BG found." if has_emd else "EMD not submitted and bidder is not NSIC/MSME exempt.","review":not has_emd}

    # ── EXPERIENCE
    if cat == "experience":
        required = tender.get("min_projects", 3)
        count = bidder.get("projects", 0) or 0
        exp_text = bidder.get("exp_text") or ""
        tender_kw = (tender.get("name") or "") + " " + (tender.get("description") or "")[:300]
        sim = semantic_similarity(exp_text, tender_kw) if exp_text else 0
        matched = min(count, max(1, round(count * min(sim * 2.5, 1.0))))
        passes = matched >= required
        conf = 0.88 if exp_text else 0.65
        return {"id":crit["id"],"desc":desc,"cat":cat,
                "status":"eligible" if passes else "ineligible","conf":conf,
                "bidder_val":f"{matched}/{count} projects matched (domain similarity {sim:.0%})",
                "required_val":f"{required} similar projects",
                "src":"Experience / Completion Certificates",
                "reason":(f"{matched} of {count} projects matched tender domain at {sim:.0%} similarity. "
                          f"{'Criterion met.' if passes else f'Need {required} — only {matched} qualified.'}"),
                "review":conf < 0.80}

    # ── COMPLIANCE: GSTIN
    if cat == "compliance" and "gstin" in desc.lower():
        gstin = bidder.get("gstin") or ""
        if not gstin:
            return {"id":crit["id"],"desc":desc,"cat":cat,"status":"document_missing","conf":0.95,
                    "bidder_val":"NOT PROVIDED","required_val":"Valid GSTIN",
                    "src":"GST Registration Certificate","reason":"GSTIN not provided.","review":True}
        result = verify_gstin_real(gstin)
        passes = result.get("verified", False)
        note = f"Source: {result.get('source','format_check')}."
        if result.get("note"):
            note += " " + result["note"]
        return {"id":crit["id"],"desc":desc,"cat":cat,
                "status":"eligible" if passes else "ineligible","conf":0.97,
                "bidder_val":gstin,"required_val":"Valid GSTIN (15-char)",
                "src":"GST Registration Certificate",
                "reason":f"GSTIN '{gstin}' {'passes' if passes else 'FAILS'} validation. Status: {result.get('status','UNKNOWN')}. {note}","review":not passes}

    # ── COMPLIANCE: PAN
    if cat == "compliance" and "pan" in desc.lower():
        pan = bidder.get("pan") or ""
        if not pan:
            return {"id":crit["id"],"desc":desc,"cat":cat,"status":"document_missing","conf":0.95,
                    "bidder_val":"NOT PROVIDED","required_val":"PAN Card",
                    "src":"PAN Card","reason":"PAN not provided.","review":True}
        valid = bool(re.match(r'^[A-Z]{5}\d{4}[A-Z]$', pan.upper()))
        return {"id":crit["id"],"desc":desc,"cat":cat,
                "status":"eligible" if valid else "ineligible","conf":0.94,
                "bidder_val":pan,"required_val":"Valid PAN (XXXXXNNNNA)",
                "src":"PAN Card",
                "reason":f"PAN '{pan}' {'valid format' if valid else 'INVALID format'}.","review":not valid}

    # ── COMPLIANCE: Doc keyword check
    if cat == "compliance":
        docs = [d.upper() for d in (bidder.get("docs_list") or "").split(",") if d.strip()]
        kw_map = {"ISO":"ISO 9001","NSIC":"NSIC","MSME":"MSME","UDYAM":"MSME","IMPORT":"Import Licence","EXPORT":"Export Licence"}
        for kw, label in kw_map.items():
            if kw in desc.upper():
                found = any(kw in d for d in docs)
                return {"id":crit["id"],"desc":desc,"cat":cat,
                        "status":"eligible" if found else ("ineligible" if crit["mandatory"] else "ineligible"),
                        "conf":0.90,"bidder_val":f"{label} {'found' if found else 'NOT found'}",
                        "required_val":desc,"src":"Document Checklist",
                        "reason":f"{label} certificate {'found' if found else 'NOT found'} in submission.{' Desirable criterion.' if not crit['mandatory'] else ''}","review":not found and crit["mandatory"]}

    # ── LEGAL
    if cat == "legal":
        docs_str = (bidder.get("docs_list") or "").lower()
        keywords = ["integrity pact", "declaration", "affidavit", "blacklist", "liquidation", "stamp paper"]
        found = any(k in docs_str for k in keywords)
        return {"id":crit["id"],"desc":desc,"cat":cat,
                "status":"eligible" if found else "review_required","conf":0.85 if found else 0.60,
                "bidder_val":"Declaration/Pact found" if found else "Manual check needed",
                "required_val":desc,"src":"Legal Declarations",
                "reason":"Legal declaration found in document list." if found else "Declaration not explicitly listed — manual verification required.","review":not found}

    # Fallback
    return {"id":crit["id"],"desc":desc,"cat":cat,"status":"review_required","conf":0.50,
            "bidder_val":"Manual review needed","required_val":desc,"src":"Document submission",
            "reason":"Automated check could not verify this criterion.","review":True}


def evaluate_bidder_full(bidder: dict, tender: dict, criteria: list) -> dict:
    results = [evaluate_criterion(bidder, tender, c) for c in criteria]
    mandatory = [r for r, c in zip(results, criteria) if c["mandatory"]]
    optional  = [r for r, c in zip(results, criteria) if not c["mandatory"]]
    mand_pass = sum(1 for r in mandatory if r["status"] == "eligible")
    opt_pass  = sum(1 for r in optional  if r["status"] == "eligible")
    avg_conf  = sum(r["conf"] for r in results) / max(len(results), 1)
    has_review = any(r["review"] for r in results)
    opt_score = (opt_pass / max(len(optional), 1)) * 100

    if mand_pass == len(mandatory):
        overall = "review_required" if has_review else "eligible"
    else:
        overall = "ineligible"

    return {
        "overall": overall,
        "confidence": round(avg_conf, 3),
        "mand_pass": mand_pass,
        "mand_total": len(mandatory),
        "opt_score": round(opt_score, 1),
        "has_review": has_review,
        "results": results,
        "evaluated_at": datetime.utcnow().isoformat()
    }


# ── AUDIT CHAIN ───────────────────────────────────────────────────────────────
def make_hash(event_id, event_type, timestamp, actor, description, prev_hash):
    content = f"{event_id}|{event_type}|{timestamp}|{actor}|{description}|{prev_hash}"
    return hashlib.sha256(content.encode()).hexdigest()[:16] + "..."
