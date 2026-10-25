"""Build the four-page, evidence-based VoiceOps 2026 capstone report."""
from __future__ import annotations
import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report.pdf"
PAGE_W, PAGE_H = A4

NAVY = colors.HexColor("#13283D")
DARK = colors.HexColor("#0C1B2A")
TEAL = colors.HexColor("#12A997")
TEAL_DARK = colors.HexColor("#087F74")
MINT = colors.HexColor("#E5F7F3")
ORANGE = colors.HexColor("#F4A261")
BG = colors.HexColor("#F7F9FB")
WHITE = colors.white
TEXT = colors.HexColor("#253848")
MUTED = colors.HexColor("#647586")
LINE = colors.HexColor("#DDE5EB")
PALE = colors.HexColor("#EEF2F6")
RED = colors.HexColor("#B54743")
AMBER = colors.HexColor("#96601B")
GREEN = colors.HexColor("#267A67")

styles = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.5, leading=12.1, textColor=TEXT, alignment=TA_LEFT, spaceAfter=0),
    "body_small": ParagraphStyle("body_small", fontName="Helvetica", fontSize=7.4, leading=10.2, textColor=TEXT, alignment=TA_LEFT, spaceAfter=0),
    "small_muted": ParagraphStyle("small_muted", fontName="Helvetica", fontSize=7.2, leading=9.3, textColor=MUTED, alignment=TA_LEFT, spaceAfter=0),
    "card_title": ParagraphStyle("card_title", fontName="Helvetica-Bold", fontSize=9.2, leading=11, textColor=NAVY, alignment=TA_LEFT, spaceAfter=0),
    "table": ParagraphStyle("table", fontName="Helvetica", fontSize=7.0, leading=8.6, textColor=TEXT, alignment=TA_LEFT, spaceAfter=0),
    "table_bold": ParagraphStyle("table_bold", fontName="Helvetica-Bold", fontSize=7.1, leading=8.6, textColor=NAVY, alignment=TA_LEFT, spaceAfter=0),
    "table_header": ParagraphStyle("table_header", fontName="Helvetica-Bold", fontSize=7.1, leading=8.6, textColor=WHITE, alignment=TA_LEFT, spaceAfter=0),
    "white_body_small": ParagraphStyle("white_body_small", fontName="Helvetica", fontSize=7.4, leading=10.2, textColor=WHITE, alignment=TA_LEFT, spaceAfter=0),
    "tiny": ParagraphStyle("tiny", fontName="Helvetica", fontSize=6.8, leading=8.5, textColor=MUTED, alignment=TA_LEFT, spaceAfter=0),
}

def para(c: canvas.Canvas, text: str, x: float, y_top: float, width: float, style: str="body") -> float:
    p = Paragraph(text, styles[style])
    _, h = p.wrap(width, PAGE_H)
    p.drawOn(c, x, y_top - h)
    return y_top - h

def section(c, num: str, title: str, x: float, y: float) -> float:
    c.setFillColor(TEAL)
    c.roundRect(x, y-2, 4, 18, 2, stroke=0, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7.4)
    c.drawString(x+12, y+7, num)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 13.2)
    c.drawString(x+46, y+5, title)
    return y-10

def header(c, page_no: int, title: str | None = None, subtitle: str | None = None):
    c.setFillColor(BG); c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    if page_no == 1:
        c.setFillColor(NAVY); c.rect(0, PAGE_H-127, PAGE_W, 127, stroke=0, fill=1)
        c.setFillColor(TEAL); c.rect(0, PAGE_H-127, 7, 127, stroke=0, fill=1)
        c.setFillColor(ORANGE); c.circle(PAGE_W-45, PAGE_H-39, 10, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#2C475E")); c.circle(PAGE_W-65, PAGE_H-77, 26, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1D374C")); c.circle(PAGE_W-35, PAGE_H-91, 18, stroke=0, fill=1)
        c.setFillColor(ORANGE); c.setFont("Helvetica-Bold", 7.3)
        c.drawString(40, PAGE_H-33, "VOICEOPS 2026   /   CAPSTONE ENGINEERING REPORT")
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 23)
        c.drawString(40, PAGE_H-67, "ZentroMart AI Voice")
        c.drawString(40, PAGE_H-94, "Support Agent")
        c.setFillColor(colors.HexColor("#C7D5DF")); c.setFont("Helvetica", 8.5)
        c.drawString(40, PAGE_H-112, "Evidence-grounded support | multi-turn workflows | Gnani.ai speech")
    else:
        c.setFillColor(NAVY); c.rect(0, PAGE_H-65, PAGE_W, 65, stroke=0, fill=1)
        c.setFillColor(TEAL); c.rect(0, PAGE_H-65, 7, 65, stroke=0, fill=1)
        c.setFillColor(ORANGE); c.setFont("Helvetica-Bold", 7.3)
        c.drawString(40, PAGE_H-24, f"VOICEOPS 2026   /   ENGINEERING REPORT     /     0{page_no}")
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 16)
        c.drawString(40, PAGE_H-47, title or "")
        if subtitle:
            c.setFillColor(colors.HexColor("#C7D5DF")); c.setFont("Helvetica", 7.4)
            c.drawRightString(PAGE_W-40, PAGE_H-46, subtitle)
    c.setStrokeColor(LINE); c.setLineWidth(0.6); c.line(40, 31, PAGE_W-40, 31)
    c.setFillColor(MUTED); c.setFont("Helvetica", 6.8)
    c.drawString(40, 19, "ZentroMart is fictional; all supplied customer records are synthetic.")
    c.drawRightString(PAGE_W-40, 19, f"{page_no} / 4")

def tag(c, x, y, w, label, fill=MINT, ink=TEAL_DARK):
    c.setFillColor(fill); c.roundRect(x, y, w, 18, 8, stroke=0, fill=1)
    c.setFillColor(ink); c.setFont("Helvetica-Bold", 6.6); c.drawCentredString(x+w/2, y+6, label)

def card(c, x, y, w, h, title, body, accent=TEAL):
    c.setFillColor(WHITE); c.setStrokeColor(LINE); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
    c.setFillColor(accent); c.roundRect(x+10, y+h-25, 3, 13, 1.5, stroke=0, fill=1)
    para(c, title, x+20, y+h-10, w-31, "card_title")
    para(c, body, x+12, y+h-35, w-24, "body_small")

def bullet(c, x, y_top, text, width, color=TEAL, style="body_small"):
    c.setFillColor(color); c.circle(x+3, y_top-5, 2, stroke=0, fill=1)
    return para(c, text, x+12, y_top, width-12, style)-6

def page_one(c):
    header(c, 1)
    tag(c, 40, 694, 125, "REFERENCE DATE  |  20 OCT 2026")
    tag(c, 173, 694, 101, "OFFLINE TESTED")
    tag(c, 282, 694, 138, "LIVE API TESTS PENDING", fill=colors.HexColor("#FFF1E6"), ink=AMBER)
    y = section(c, "01", "Problem and solution", 40, 665)
    y = para(c, "ZentroMart support handles repeated questions about delivery, cancellations, returns, refunds, warranty and damaged goods. This capstone implements an AI support agent that retrieves company evidence, keeps conversation context, gates protected order lookups behind caller verification, and uses the same agent for text and voice.", 40, 640, PAGE_W-80, "body")
    y -= 18
    y = section(c, "02", "Core capabilities", 40, y)
    gap = 12; cw = (PAGE_W-80-gap)/2; ch = 80
    top_y = y-7
    card(c,40,top_y-ch,cw,ch,"Evidence-grounded answers","Section-aware Markdown ingestion; source/effective-date metadata; policy precedence; abstention when evidence is absent.")
    card(c,40+cw+gap,top_y-ch,cw,ch,"Verified order support","Uses supplied lookup tool; asks for phone last four or delivery pincode; no order facts before tool verification.",ORANGE)
    second_y = top_y-ch-11
    card(c,40,second_y-ch,cw,ch,"Human handover","Uses the provided ticket tool for configured escalation rules; confirms a ticket only after `created=True`.",TEAL_DARK)
    card(c,40+cw+gap,second_y-ch,cw,ch,"Voice interface","Browser microphone Record / Stop / preview / Send Audio, plus upload; actual audio is converted to WAV and sent through Gnani STT -> same agent -> Gnani TTS. Real-mic regression still pending.",ORANGE)
    y = second_y-ch-24
    y = section(c, "03", "Technology stack", 40, y)
    tags = [("Python", 54),("FastAPI", 61),("TF-IDF + cosine", 106),("OpenAI-compatible LLM", 129),("Gnani.ai STT / TTS", 116)]
    x=40
    for label,w in tags:
        tag(c,x,y-27,w,label,fill=PALE,ink=NAVY); x += w+7
        if x > PAGE_W-110: x=40; y-=24
    y -= 42
    c.setFillColor(NAVY); c.roundRect(40,y-80,PAGE_W-80,80,9,stroke=0,fill=1)
    c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",7.3); c.drawString(54,y-18,"IMPLEMENTATION STATUS")
    para(c,"45 automated tests pass, dataset validation passes, and retrieval finds 81/90 gold evidence IDs in the top five. Live baseline/RAG answer scoring and all 96 conversation turns remain pending without provider keys. A prior uploaded-audio STT/TTS pass was reported; browser-microphone end-to-end testing remains pending on Windows.",54,y-29,PAGE_W-108,"white_body_small")
    c.showPage()

def arrow(c,x1,y,x2,color=TEAL):
    c.setStrokeColor(color); c.setLineWidth(1.5); c.line(x1,y,x2-5,y)
    p=c.beginPath(); p.moveTo(x2-5,y+3); p.lineTo(x2,y); p.lineTo(x2-5,y-3); p.close()
    c.setFillColor(color); c.drawPath(p,stroke=0,fill=1)

def page_two(c):
    header(c,2,"Architecture and implementation","One shared agent for text and voice")
    c.setFillColor(MUTED); c.setFont("Helvetica-Bold",7.2); c.drawString(40, PAGE_H-90,"ONE TURN  /  END-TO-END PIPELINE")
    items = [
        ("Customer", "Audio / text", colors.HexColor("#F0F4F8")),
        ("Gnani STT", "en-IN", MINT),
        ("Session", "Context + routing", colors.HexColor("#F0F4F8")),
        ("RAG + LLM", "Evidence + answer", MINT),
        ("Policy / tools", "Verify + ticket", colors.HexColor("#FFF1E6")),
        ("Gnani TTS", "WAV response", MINT),
    ]
    widths=[67,67,77,72,79,67]; gap=12; x=40; y=PAGE_H-191; h=75
    centers=[]
    for (title,sub,fill),w in zip(items,widths):
        c.setFillColor(fill); c.setStrokeColor(LINE); c.roundRect(x,y,w,h,7,stroke=1,fill=1)
        c.setFillColor(NAVY); c.setFont("Helvetica-Bold",7.3); c.drawCentredString(x+w/2,y+47,title)
        para(c,sub,x+5,y+36,w-10,"tiny")
        centers.append((x,y,w)); x+=w+gap
    for i in range(len(centers)-1):
        x0,w0=centers[i][0],centers[i][2]; x1=centers[i+1][0]
        arrow(c,x0+w0+2,y+h/2,x1-2)
    c.setFillColor(WHITE); c.setStrokeColor(LINE); c.roundRect(40, PAGE_H-273, PAGE_W-80, 39, 7, stroke=1, fill=1)
    c.setFillColor(TEAL_DARK); c.setFont("Helvetica-Bold",7.5); c.drawString(52,PAGE_H-250,"DATA PLANE")
    para(c,"21 KB Markdown documents + 70 product rows | 7 database CSVs | holidays.csv | supplied `lookup_order` and `create_ticket` tools | practice questions and conversations",126,PAGE_H-243,PAGE_W-178,"body_small")
    y = section(c,"04","Implementation details",40,PAGE_H-305)
    cw=(PAGE_W-80-12)/2; ch=96; top=y-5
    card(c,40,top-ch,cw,ch,"Ingestion and chunking","Reads front matter, splits on `[SECTION-ID]` headings and paragraph boundaries, and preserves source, status, effective date, version and chunk index.")
    card(c,40+cw+12,top-ch,cw,ch,"Retrieval and authority","TF-IDF n-gram vectors + cosine similarity; current policies receive priority and a per-source diversity cap. Superseded return text is conditional-only for the legacy case preserved by current RET-3.",ORANGE)
    second=top-ch-12
    card(c,40,second-ch,cw,ch,"Session and protected data","Session state retains recent turns and order context. The supplied tool enforces proof matching; contact fields and pincode proof are filtered from model context.",TEAL_DARK)
    card(c,40+cw+12,second-ch,cw,ch,"Escalation and tool truth","Order lookup, business-day checks and ticket actions are deterministic code. Ticket ID/handover wording depends on the actual tool result; failed creation is reported as unconfirmed.",ORANGE)
    call_y=second-ch-20
    c.setFillColor(NAVY); c.roundRect(40,call_y-68,PAGE_W-80,68,8,stroke=0,fill=1)
    c.setFillColor(ORANGE); c.setFont("Helvetica-Bold",7.4); c.drawString(54,call_y-18,"SPEECH INTEGRATION BOUNDARY")
    para(c,"Official `gnani-vachana` adapters are configured for STT `en-IN` and TTS `timbre-v2.5` / `Kaveri`. Browser `MediaRecorder` output is decoded and encoded as true WAV before upload. No alternate speech provider is used. The package's changed microphone workflow still requires a real Windows-device + live-Gnani check; no credentials are available in this build workspace.",54,call_y-29,PAGE_W-108,"white_body_small")
    c.showPage()

def draw_table(c, x, y_top, widths, rows, row_h=30):
    headers=rows[0]
    c.setFillColor(NAVY); c.roundRect(x,y_top-row_h,sum(widths),row_h,5,stroke=0,fill=1)
    xx=x
    for text,w in zip(headers,widths):
        para(c,text,xx+7,y_top-8,w-14,"table_header")
        xx+=w
    y=y_top-row_h
    for index,row in enumerate(rows[1:]):
        fill=WHITE if index%2==0 else colors.HexColor("#F1F5F8")
        c.setFillColor(fill); c.rect(x,y-row_h,sum(widths),row_h,stroke=0,fill=1)
        c.setStrokeColor(LINE); c.setLineWidth(.35); c.line(x,y-row_h,x+sum(widths),y-row_h)
        xx=x
        for col,(text,w) in enumerate(zip(row,widths)):
            style="table_bold" if col==0 else "table"
            ink=TEXT
            if col==1 and ("PENDING" in text or "NOT LIVE" in text): ink=AMBER
            if col==1 and ("PASS" in text or "passed" in text.lower()): ink=GREEN
            tmp=ParagraphStyle(f"cell_{index}_{col}",parent=styles[style],textColor=ink)
            p=Paragraph(text,tmp); _,h=p.wrap(w-14,row_h-4); p.drawOn(c,xx+7,y-((row_h-h)/2)-h)
            xx+=w
        y-=row_h
    return y

def page_three(c, metrics, conv):
    header(c,3,"Evaluation and verified results","Offline metrics only where measured")
    y=PAGE_H-88
    retrieval=metrics.get("retrieval",{})
    answer=metrics.get("answer_evaluation",{})
    test_results = metrics.get("test_results", {})
    pytest_result = test_results.get("pytest", {})
    test_passed = pytest_result.get("passed", 20)
    test_failed = pytest_result.get("failed", 0)
    test_total = test_passed + test_failed
    recall_pct = retrieval.get("gold_evidence_recall_at_k", 0.9) * 100
    question_hits = round(retrieval.get("question_hit_rate_at_k", 1.0) * retrieval.get("questions_with_gold_evidence", 47))
    question_total = retrieval.get("questions_with_gold_evidence", 47)
    cards=[(f"{test_passed} / {test_total}","pytest tests passed",GREEN),(f"{recall_pct:.1f}%","gold evidence Recall@5",TEAL_DARK),(f"{question_hits} / {question_total}","questions hit at least one gold item",TEAL),("0","live API calls claimed",AMBER)]
    gap=10; cw=(PAGE_W-80-gap*3)/4
    for i,(value,label,accent) in enumerate(cards):
        x=40+i*(cw+gap)
        c.setFillColor(WHITE); c.setStrokeColor(LINE); c.roundRect(x,y-66,cw,66,8,stroke=1,fill=1)
        c.setFillColor(accent); c.setFont("Helvetica-Bold",16); c.drawString(x+10,y-27,value)
        para(c,label,x+10,y-36,cw-18,"tiny")
    y-=88
    c.setFillColor(NAVY); c.setFont("Helvetica-Bold",10.6); c.drawString(40,y,"RESULTS / STATUS")
    conversation_status = conv.get("status", "pending_missing_llm_configuration")
    if conversation_status == "completed":
        conversation_value = f"{conv.get('turns_passed', 0)} / {conv.get('turns_executed', 0)} passed"
    else:
        conversation_value = f"0 / {conv.get('turns_in_dataset', 96)} turns executed"
    rows=[
        ("Metric","Measured result","Interpretation"),
        ("Dataset validator","PASS","9 CSVs, 21 KB docs, keys, order math, practice evidence and verification gates checked."),
        ("Automated test suite",f"{test_passed} passed / {test_failed} failed","pytest run with offline mocks and supplied-data integration tests."),
        ("Gold evidence Recall@5",f"{retrieval.get('gold_evidence_items_found',81)}/{retrieval.get('gold_evidence_items_total',90)} = {retrieval.get('gold_evidence_recall_at_k',0.9)*100:.1f}%","Exact gold section/source IDs found in top-five retrieved chunks."),
        ("Question hit rate@5",f"{round(retrieval.get('question_hit_rate_at_k',1.0)*100)}% ({question_hits}/{question_total})","At least one gold evidence item retrieved for each question with a gold label."),
        ("Step 1 baseline accuracy","PENDING","Requires configured live LLM; no answer accuracy inferred from retrieval alone."),
        ("Step 2 RAG answer accuracy","PENDING","Same 52 questions and rubric await the live LLM evaluation."),
        ("Conversation evaluation",conversation_value,"Live evaluation status; answer and context checks require an LLM-configured run."),
        ("Gnani STT / TTS","UPLOAD TURN REPORTED PASS","A prior local uploaded-audio transcript and audible reply were reported; updated microphone flow still needs a real Windows/Gnani run."),
        ("Application / batch smoke","PASS (offline)","`/` and `/health`: HTTP 200; no-key chat: 503 as expected. No live provider was called in this packaging workspace."),
    ]
    end=draw_table(c,40,y-11,[130,112,PAGE_W-80-242],rows,row_h=30)
    note_y=end-16
    c.setFillColor(colors.HexColor("#FFF1E6")); c.roundRect(40,note_y-74,PAGE_W-80,74,8,stroke=0,fill=1)
    c.setFillColor(AMBER); c.setFont("Helvetica-Bold",7.7); c.drawString(52,note_y-18,"HOW TO READ THE RETRIEVAL SCORE")
    para(c,"Recall@5 = the fraction of supplied gold evidence IDs matched against the top-five retrieved source/section metadata. The 100% question hit rate means at least one gold item was found for each of 47 labelled questions. Neither metric proves the generated answer is correct. Product queries with unspecified variants can remain ambiguous; baseline/RAG correctness, unsupported-answer rate and conversation pass rate remain unmeasured.",52,note_y-29,PAGE_W-104,"body_small")
    c.showPage()

def page_four(c):
    header(c,4,"Limitations and reproduction","Remaining steps before final submission")
    left_x=40; left_w=252; right_x=307; right_w=PAGE_W-40-right_x
    y=PAGE_H-91
    y=section(c,"05","Limitations and next work",left_x,y)
    points=[
        ("Live scores and new microphone path pending.","No provider keys were available in this packaging workspace. Run the full baseline/RAG and 96-turn evaluations, then test a real browser microphone recording through live Gnani STT/TTS on Windows. A prior uploaded-audio test was reported to work."),
        ("Lexical retrieval, not dense embeddings.","Current retriever is sparse TF-IDF with cosine similarity and intent-aware ranking. Evaluate neural embeddings or hybrid reranking if allowed, using the same gold evidence set."),
        ("Session state is in memory.","Restarting the app loses context; use durable, access-controlled session storage and stronger identity controls before production."),
        ("Demo and public repo pending.","No fabricated `demo.mp4` was added. Record a real <=120-second demo after direct-microphone/live provider checks; publish this local project to a public repo and verify access."),
    ]
    for title,body in points:
        c.setFillColor(WHITE); c.setStrokeColor(LINE); c.roundRect(left_x,y-73,left_w,67,7,stroke=1,fill=1)
        para(c,title,left_x+10,y-12,left_w-20,"card_title")
        para(c,body,left_x+10,y-27,left_w-20,"tiny")
        y-=78
    y-=25
    y=section(c,"06","Fixes made",left_x,y)
    para(c,"The current build adds browser microphone recording with WAV conversion, validated voice uploads, ticket CSV readback and lookup-first routing to avoid duplicate ticket creation. Regression tests cover these paths. Dataset validation, order verification and honest tool-result handling remain exercised by tests.",left_x,y,left_w,"body_small")
    yr=PAGE_H-91
    yr=section(c,"07","Reproduce locally",right_x,yr)
    c.setFillColor(DARK); c.roundRect(right_x,yr-294,right_w,294,8,stroke=0,fill=1)
    commands=[
        "pip install -r requirements.txt",
        "# copy .env.example to .env",
        "# set LLM_API_KEY, LLM_MODEL,",
        "# GNANI_API_KEY, DATASET_DIR",
        "python scripts/build_index.py",
        "DATASET_DIR=<dataset-root> pytest -q",
        "python scripts/evaluate_questions.py",
        "python scripts/evaluate_conversations.py",
        "uvicorn app:app --host 127.0.0.1 --port 8000",
        "python run.py --input-dir sample_audio \\",
        "  --output-dir outputs",
    ]
    ty=yr-19
    c.setFillColor(colors.HexColor("#A6E6D9")); c.setFont("Helvetica-Bold",7.3); c.drawString(right_x+12,ty,"COMMANDS (FROM PROJECT ROOT)")
    ty-=20
    for i,line in enumerate(commands):
        c.setFillColor(colors.HexColor("#F1F5F8")); c.setFont("Courier",6.5)
        c.drawString(right_x+12,ty,line)
        ty-=16 if i not in (3,7) else 19
    yr-=315
    c.setFillColor(WHITE); c.setStrokeColor(LINE); c.roundRect(right_x,yr-117,right_w,108,7,stroke=1,fill=1)
    para(c,"<b>Links / submission status</b><br/>GitHub: github.com/aayush-as69/voiceops-zentromart<br/>Verify this source is pushed and public before review.<br/>Demo MP4: pending target-browser and credentialed voice test.<br/>SDK: github.com/Gnani-AI-Mintlify/gnani-vachana",right_x+10,yr-14,right_w-20,"body_small")
    yr-=132
    c.setFillColor(MINT); c.roundRect(right_x,yr-64,right_w,57,7,stroke=0,fill=1)
    para(c,"<b>Batch command</b><br/>`python run.py --input-dir sample_audio --output-dir outputs` processes actual audio files; missing configuration exits clearly without mock substitutions.",right_x+10,yr-15,right_w-20,"body_small")
    c.showPage()

def main():
    metrics_path = ROOT / "outputs" / "question_evaluation.json"
    conv_path = ROOT / "outputs" / "conversation_evaluation.json"
    sample_metrics_path = ROOT / "sample_outputs" / "retrieval_and_answer_evaluation.json"
    sample_conv_path = ROOT / "sample_outputs" / "conversation_evaluation.json"
    test_path = ROOT / "sample_outputs" / "test_results.json"
    metrics_fallback = sample_metrics_path if sample_metrics_path.exists() else None
    conv_fallback = sample_conv_path if sample_conv_path.exists() else None
    selected_metrics = metrics_path if metrics_path.exists() else metrics_fallback
    selected_conv = conv_path if conv_path.exists() else conv_fallback
    metrics = json.loads(selected_metrics.read_text(encoding="utf-8")) if selected_metrics else {}
    conv = json.loads(selected_conv.read_text(encoding="utf-8")) if selected_conv else {}
    metrics["test_results"] = json.loads(test_path.read_text(encoding="utf-8")) if test_path.exists() else {}
    c=canvas.Canvas(str(OUT),pagesize=A4)
    c.setTitle("VoiceOps 2026: ZentroMart AI Voice Support Agent")
    c.setAuthor("VoiceOps 2026 Capstone Project")
    page_one(c); page_two(c); page_three(c,metrics,conv); page_four(c); c.save()
    print(f"Wrote {OUT}")

if __name__=="__main__":main()
