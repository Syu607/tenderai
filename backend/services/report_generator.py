"""
DOCX Report Generator
Generates a professional Word document evaluation report.
"""
import json, os
from datetime import datetime
from docx import Document as DocxDocument
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


STATUS_COLOR = {
    "eligible":         RGBColor(0x16, 0xA3, 0x4A),
    "ineligible":       RGBColor(0xDC, 0x26, 0x26),
    "review_required":  RGBColor(0xD9, 0x77, 0x06),
    "document_missing": RGBColor(0x25, 0x63, 0xEB),
}
STATUS_LABEL = {
    "eligible":         "✓ ELIGIBLE",
    "ineligible":       "✗ INELIGIBLE",
    "review_required":  "⚑ REVIEW REQUIRED",
    "document_missing": "□ DOCUMENT MISSING",
}
STATUS_BG = {
    "eligible":         "DCFCE7",
    "ineligible":       "FEE2E2",
    "review_required":  "FEF3C7",
    "document_missing": "DBEAFE",
}


def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), hex_color)
    shd.set(qn('w:val'), 'clear')
    tcPr.append(shd)


def set_cell_border(cell):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:color'), 'D1D5DB')
        tcBorders.append(el)
    tcPr.append(tcBorders)


def add_heading(doc, text, level=1):
    style = {1: 'Heading 1', 2: 'Heading 2', 3: 'Heading 3'}.get(level, 'Heading 2')
    p = doc.add_heading(text, level=level)
    run = p.runs[0]
    run.font.name = 'Arial'
    run.font.color.rgb = RGBColor(0x1A, 0x2D, 0x5A)
    return p


def add_para(doc, text, bold=False, color=None, size=11, align=None, italic=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = 'Arial'
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color
    if align:
        p.alignment = align
    return p


def add_table_row(table, cells_data):
    row = table.add_row()
    for i, (text, opts) in enumerate(cells_data):
        cell = row.cells[i]
        cell.text = str(text)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = opts.get("align", WD_ALIGN_PARAGRAPH.LEFT)
        run = p.runs[0] if p.runs else p.add_run(str(text))
        if p.runs:
            run = p.runs[0]
            run.text = str(text)
        run.font.name = 'Arial'
        run.font.size = Pt(opts.get("size", 10))
        run.bold = opts.get("bold", False)
        if opts.get("color"):
            run.font.color.rgb = opts["color"]
        if opts.get("bg"):
            set_cell_bg(cell, opts["bg"])
        set_cell_border(cell)
    return row


def generate_docx_report(tender_data: dict, evaluations: list, output_path: str) -> str:
    """
    Main report generation function.
    tender_data: tender dict from DB
    evaluations: list of {bidder, evaluation, criteria_results}
    output_path: where to save the .docx
    """
    doc = DocxDocument()

    # Page margins
    for section in doc.sections:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)

    # ── COVER PAGE ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("GOVERNMENT OF INDIA")
    run.font.name = 'Arial'; run.font.size = Pt(16); run.bold = True
    run.font.color.rgb = RGBColor(0x1B, 0x4F, 0x72)

    add_para(doc, tender_data.get("org", "Ministry / Department"), align=WD_ALIGN_PARAGRAPH.CENTER,
             color=RGBColor(0x37, 0x41, 0x51), size=13)
    doc.add_paragraph()

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title_p.add_run("TECHNICAL BID EVALUATION REPORT")
    r.font.name = 'Arial'; r.font.size = Pt(22); r.bold = True
    r.font.color.rgb = RGBColor(0x1A, 0x2D, 0x5A)

    add_para(doc, tender_data.get("name", ""), align=WD_ALIGN_PARAGRAPH.CENTER,
             bold=True, size=14, color=RGBColor(0x37, 0x41, 0x51))
    add_para(doc, tender_data.get("ref", ""), align=WD_ALIGN_PARAGRAPH.CENTER,
             bold=True, size=13, color=RGBColor(0x25, 0x63, 0xEB))
    doc.add_paragraph()

    # Cover table
    cover_table = doc.add_table(rows=0, cols=2)
    cover_table.style = 'Table Grid'
    cover_table.columns[0].width = Inches(2.5)
    cover_table.columns[1].width = Inches(4.0)

    summary = {
        "Tender Reference": tender_data.get("ref",""),
        "Organisation": tender_data.get("org",""),
        "Evaluation Date": datetime.utcnow().strftime("%d %B %Y"),
        "Total Bidders": str(len(evaluations)),
        "Eligible Bidders": str(sum(1 for e in evaluations if e["evaluation"]["overall"]=="eligible")),
        "Ineligible Bidders": str(sum(1 for e in evaluations if e["evaluation"]["overall"]=="ineligible")),
        "Generated By": "TenderAI v2.0 — AI-Assisted Evaluation",
    }
    for lbl, val in summary.items():
        add_table_row(cover_table, [
            (lbl,  {"bold": True, "bg": "F3F4F6", "size": 10}),
            (val,  {"size": 10}),
        ])

    doc.add_paragraph()
    warn = add_para(doc, "CONFIDENTIAL — FOR OFFICIAL USE ONLY", bold=True,
                    color=RGBColor(0xDC, 0x26, 0x26), align=WD_ALIGN_PARAGRAPH.CENTER, size=11)
    note = add_para(doc, "This report is AI-assisted. Final eligibility determination is a human administrative act per GFR 2017.",
                    italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
                    color=RGBColor(0x6B, 0x72, 0x80))
    doc.add_page_break()

    # ── TENDER DETAILS ──
    add_heading(doc, "1. Tender Details", 1)
    td = doc.add_table(rows=0, cols=2)
    td.style = 'Table Grid'
    td.columns[0].width = Inches(2.5)
    td.columns[1].width = Inches(4.0)
    fields = [
        ("Tender Reference",    tender_data.get("ref","")),
        ("Tender Name",         tender_data.get("name","")),
        ("Organisation",        tender_data.get("org","")),
        ("Procurement Type",    tender_data.get("proc_type","OTE")),
        ("Estimated Value",     f"₹{tender_data.get('value',0)} Crore"),
        ("Min. Annual Turnover",f"₹{tender_data.get('min_turnover',5)} Crore (mandatory)"),
        ("Min. Similar Projects",str(tender_data.get("min_projects",3))),
        ("EMD Amount",          f"₹{tender_data.get('emd',0):,.0f}" if tender_data.get("emd") else "Not specified"),
        ("Deadline",            tender_data.get("deadline","") or "Not specified"),
    ]
    for lbl, val in fields:
        add_table_row(td, [(lbl,{"bold":True,"bg":"F9FAFB","size":10}),(val,{"size":10})])

    doc.add_paragraph()

    # ── EVALUATION SUMMARY ──
    add_heading(doc, "2. Evaluation Summary", 1)
    st = doc.add_table(rows=2, cols=4)
    st.style = 'Table Grid'
    headers_row = st.rows[0]
    for i, h in enumerate(["Total Bidders","Eligible","Ineligible","Review Required"]):
        c = headers_row.cells[i]
        c.text = h
        set_cell_bg(c, "1A2D5A")
        set_cell_border(c)
        run = c.paragraphs[0].runs[0]
        run.font.name = 'Arial'; run.font.size = Pt(11); run.bold = True
        run.font.color.rgb = RGBColor(0xFF,0xFF,0xFF)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    vals_row = st.rows[1]
    total = len(evaluations)
    elig  = sum(1 for e in evaluations if e["evaluation"]["overall"]=="eligible")
    inelig= sum(1 for e in evaluations if e["evaluation"]["overall"]=="ineligible")
    rev   = sum(1 for e in evaluations if e["evaluation"]["overall"]=="review_required")
    for i, (val, bg) in enumerate([(total,"DBEAFE"),(elig,"DCFCE7"),(inelig,"FEE2E2"),(rev,"FEF3C7")]):
        c = vals_row.cells[i]
        c.text = str(val)
        set_cell_bg(c, bg)
        set_cell_border(c)
        run = c.paragraphs[0].runs[0]
        run.font.name = 'Arial'; run.font.size = Pt(22); run.bold = True
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # ── LEADERBOARD ──
    add_heading(doc, "3. Evaluation Leaderboard", 1)
    sorted_evals = sorted(evaluations,
        key=lambda e: (
            {"eligible":0,"review_required":1,"ineligible":2}.get(e["evaluation"]["overall"],3),
            -e["evaluation"]["confidence"]
        ))

    lb = doc.add_table(rows=1, cols=7)
    lb.style = 'Table Grid'
    hdr = lb.rows[0]
    for i, h in enumerate(["#","Company","Status","Mandatory","Optional","Confidence","Review"]):
        c = hdr.cells[i]
        c.text = h
        set_cell_bg(c, "1A2D5A")
        set_cell_border(c)
        run = c.paragraphs[0].runs[0]
        run.font.name='Arial'; run.font.size=Pt(10); run.bold=True
        run.font.color.rgb = RGBColor(0xFF,0xFF,0xFF)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for rank, ev in enumerate(sorted_evals, 1):
        b = ev["bidder"]
        e = ev["evaluation"]
        status = e["overall"]
        add_table_row(lb, [
            (str(rank),           {"align":WD_ALIGN_PARAGRAPH.CENTER,"size":10}),
            (b.get("company",""), {"size":10,"bold":rank==1}),
            (STATUS_LABEL.get(status,status.upper()), {"size":10,"bold":True,"color":STATUS_COLOR.get(status),"bg":STATUS_BG.get(status,"FFFFFF")}),
            (f"{e['mand_pass']}/{e['mand_total']}", {"align":WD_ALIGN_PARAGRAPH.CENTER,"size":10}),
            (f"{e['opt_score']:.0f}%",              {"align":WD_ALIGN_PARAGRAPH.CENTER,"size":10}),
            (f"{e['confidence']*100:.0f}%",          {"align":WD_ALIGN_PARAGRAPH.CENTER,"size":10}),
            ("⚑ Yes" if e["has_review"] else "—",   {"align":WD_ALIGN_PARAGRAPH.CENTER,"size":10,
             "color":RGBColor(0xD9,0x77,0x06) if e["has_review"] else RGBColor(0x9C,0xA3,0xAF)}),
        ])

    doc.add_page_break()

    # ── PER-BIDDER DETAIL ──
    for idx, ev in enumerate(sorted_evals):
        b  = ev["bidder"]
        e  = ev["evaluation"]
        cr = ev.get("criteria_results", e.get("results", []))
        status = e["overall"]

        add_heading(doc, f"{idx+4}. {b.get('company','')}", 1)

        # Verdict banner
        verdict_p = doc.add_paragraph()
        verdict_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        vr = verdict_p.add_run(STATUS_LABEL.get(status, status.upper()))
        vr.font.name = 'Arial'; vr.font.size = Pt(16); vr.bold = True
        vr.font.color.rgb = STATUS_COLOR.get(status, RGBColor(0,0,0))

        sub = add_para(doc,
            f"Mandatory: {e['mand_pass']}/{e['mand_total']} passed  |  "
            f"Confidence: {e['confidence']*100:.0f}%  |  Optional: {e['opt_score']:.0f}%",
            size=11, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x37,0x41,0x51))
        doc.add_paragraph()

        # Bidder info
        add_heading(doc, "Bidder Information", 2)
        bi = doc.add_table(rows=0, cols=2)
        bi.style = 'Table Grid'
        bi.columns[0].width = Inches(2.5)
        bi.columns[1].width = Inches(4.0)
        for lbl, val in [
            ("GSTIN", b.get("gstin","")),
            ("PAN",   b.get("pan","")),
            ("CIN",   b.get("cin","") or "N/A"),
            ("State", b.get("state","") or "N/A"),
            ("Avg. Turnover (3yr)", f"₹{b.get('avg_turnover',0):.2f} Cr"),
            ("Net Worth", f"₹{b.get('net_worth',0)} Cr" if b.get("net_worth") else "Not submitted"),
            ("Similar Projects", str(b.get("projects",0))),
            ("Uploaded Files", str(b.get("file_paths","None"))),
        ]:
            add_table_row(bi,[(lbl,{"bold":True,"bg":"F9FAFB","size":10}),(val,{"size":10})])
        doc.add_paragraph()

        # Criterion table
        add_heading(doc, "Criterion-by-Criterion Assessment", 2)
        ct = doc.add_table(rows=1, cols=6)
        ct.style = 'Table Grid'
        ch = ct.rows[0]
        for i,h in enumerate(["ID","Description","Status","Bidder Value","Confidence","Source"]):
            c = ch.cells[i]
            c.text = h
            set_cell_bg(c,"1A2D5A")
            set_cell_border(c)
            r = c.paragraphs[0].runs[0]
            r.font.name='Arial'; r.font.size=Pt(9); r.bold=True
            r.font.color.rgb=RGBColor(0xFF,0xFF,0xFF)

        for res in cr:
            s = res.get("status","")
            add_table_row(ct, [
                (res.get("id",""),          {"size":9}),
                (res.get("desc","")[:60],   {"size":9}),
                (STATUS_LABEL.get(s,s),     {"size":9,"bold":True,"color":STATUS_COLOR.get(s),"bg":STATUS_BG.get(s,"FFFFFF")}),
                (res.get("bidder_val","")[:40],{"size":9}),
                (f"{res.get('conf',0)*100:.0f}%",{"size":9,"align":WD_ALIGN_PARAGRAPH.CENTER}),
                (res.get("src","")[:30],    {"size":9}),
            ])
        doc.add_paragraph()

        # AI Reasoning
        add_heading(doc, "AI Reasoning — Detailed", 2)
        for res in cr:
            s = res.get("status","")
            p = doc.add_paragraph()
            r1 = p.add_run(f"{res.get('id','')} — {res.get('desc','')}: ")
            r1.font.name='Arial'; r1.font.size=Pt(10); r1.bold=True
            r2 = p.add_run(STATUS_LABEL.get(s,s))
            r2.font.name='Arial'; r2.font.size=Pt(10); r2.bold=True
            if STATUS_COLOR.get(s): r2.font.color.rgb=STATUS_COLOR[s]

            reason_p = doc.add_paragraph()
            reason_p.paragraph_format.left_indent = Inches(0.3)
            rr = reason_p.add_run(res.get("reason",""))
            rr.font.name='Arial'; rr.font.size=Pt(9)
            rr.font.color.rgb = RGBColor(0x37,0x41,0x51)

            if res.get("review"):
                rflag = doc.add_paragraph()
                rflag.paragraph_format.left_indent = Inches(0.3)
                rf = rflag.add_run("⚑ REVIEW FLAG: Human verification recommended.")
                rf.font.name='Arial'; rf.font.size=Pt(9); rf.bold=True
                rf.font.color.rgb = RGBColor(0xD9,0x77,0x06)

        # Recommended action
        doc.add_paragraph()
        add_heading(doc, "Recommended Action", 2)
        actions = {
            "eligible":         "PROCEED TO FINANCIAL BID OPENING. Retain AI evaluation report per CVC audit requirements.",
            "ineligible":       f"REJECT TECHNICAL BID. Do not open financial envelope. Issue rejection notice citing failed criteria: [{', '.join(r['id'] for r in cr if r.get('status')=='ineligible')}].",
            "review_required":  "HOLD FOR EXPERT REVIEW. Assign to senior procurement officer for manual verification of flagged items.",
        }
        action_p = doc.add_paragraph()
        ar = action_p.add_run(actions.get(status,"MANUAL REVIEW REQUIRED."))
        ar.font.name='Arial'; ar.font.size=Pt(11); ar.bold=True
        if STATUS_COLOR.get(status): ar.font.color.rgb=STATUS_COLOR[status]

        doc.add_page_break()

    # ── DISCLAIMER ──
    add_heading(doc, "Disclaimer & Compliance Statement", 1)
    disclaimers = [
        "1. This report is AI-assisted. The final eligibility determination is a human administrative act and must be confirmed by the authorised Procurement Officer.",
        "2. All AI verdicts are traceable to specific document sources, extracted values, and evaluation rules.",
        "3. Criteria marked 'Review Required' must be manually verified before final decision.",
        "4. This report must be retained in the tender file per GFR 2017 Rule 149.",
        "5. Any human override of AI verdicts must be documented with written justification and officer DSC signature.",
    ]
    for d in disclaimers:
        add_para(doc, d, size=10, color=RGBColor(0x37,0x41,0x51))

    doc.add_paragraph()

    # Sign-off table
    sign_table = doc.add_table(rows=1, cols=2)
    sign_table.style = 'Table Grid'
    lc = sign_table.rows[0].cells[0]
    rc = sign_table.rows[0].cells[1]
    lc.text = "Evaluated by:\nTenderAI v2.0\nDate: " + datetime.utcnow().strftime("%d %B %Y")
    rc.text = "Approved by (Procurement Officer):\nName: _______________________\nDesignation: _________________\nDate: ________________________\nDSC Seal:"
    for c in [lc, rc]:
        set_cell_border(c)
        for p in c.paragraphs:
            for r in p.runs:
                r.font.name = 'Arial'
                r.font.size = Pt(10)

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
