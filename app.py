import os, io, json, base64, re, datetime, sqlite3
import schemdraw
import schemdraw.elements as elm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Image as RLImage, Table, TableStyle, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

app = FastAPI(title="Circuit Design Copilot v3")
client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
GROQ_MODEL = "llama-3.3-70b-versatile"

# SQLite Database Setup
DB_PATH = "circuits.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS circuits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                data TEXT NOT NULL,
                is_public INTEGER DEFAULT 0
            )
        """)
init_db()

# ── System Prompts ─────────────────────────────────────────────────────────────

SCHEMATIC_PROMPT = """You are an expert electronics engineer specializing in circuit schematics.
When the user describes a circuit, respond with a JSON object (and NOTHING else):
{
  "components": [
    {"id": "V1", "type": "battery", "value": "9V", "label": "V1"},
    {"id": "R1", "type": "resistor", "value": "220Ω", "label": "R1"},
    {"id": "LED1", "type": "led", "value": "2V/20mA", "label": "LED1"}
  ],
  "connections": [
    {"from": "V1+", "to": "R1.start"},
    {"from": "R1.end", "to": "LED1.anode"},
    {"from": "LED1.cathode", "to": "V1-"}
  ],
  "title": "Simple LED Circuit",
  "description": "A basic LED circuit with current-limiting resistor to prevent burnout.",
  "difficulty": "Beginner",
  "use_case": "Learning, indicator lights, power indicators"
}
Supported types: resistor, capacitor, led, battery, switch, ground, diode, transistor, inductor, ic, potentiometer.
Output valid JSON only — no markdown, no extra text."""

COMPONENT_PROMPT = """You are an expert electronics component advisor in a multi-turn conversation.
For each recommended component include:
- Exact part name/number
- Key specs (voltage, current, resistance, tolerance)
- Why this component suits the requirement
- Estimated cost (USD)
- Where to buy (DigiKey, Mouser, Amazon)
Use markdown with tables. Be beginner-friendly but technically precise."""

DEBUG_PROMPT = """You are an expert circuit debugger in a multi-turn conversation.
For each issue:
1. Name the problem clearly
2. Explain WHY (physics/safety)
3. Give exact fix with values
4. Rate: 🔴 Critical / 🟡 Warning / 🟢 Info
Use markdown. If circuit looks correct, confirm and suggest optimizations."""

ARDUINO_PROMPT = """You are an expert Arduino programmer in a multi-turn conversation.
Generate complete upload-ready .ino code with:
- #define pin constants at top
- Comments on every block
- Full setup() and loop()
- Serial.begin(9600) for debugging
- Required libraries: // Install: Library Manager → search "Name"
After code, explain how it works in 3-5 sentences."""

SIMULATION_PROMPT = """You are a circuit simulation expert. Perform DC operating point analysis.
Respond ONLY with valid JSON:
{
  "circuit_title": "Circuit name",
  "supply_voltage": 9,
  "supply_unit": "V",
  "nodes": [
    {"id": "N1", "name": "V_supply", "voltage": 9.0, "unit": "V", "description": "Positive battery terminal"},
    {"id": "N2", "name": "V_mid", "voltage": 2.35, "unit": "V", "description": "Junction after R1"},
    {"id": "N3", "name": "GND", "voltage": 0.0, "unit": "V", "description": "Ground reference"}
  ],
  "branches": [
    {"id": "B1", "name": "Loop current", "current": 30.7, "unit": "mA", "through": "R1, LED1", "description": "Series current"}
  ],
  "power": [
    {"component": "R1", "power": 207.0, "unit": "mW", "status": "OK"},
    {"component": "LED1", "power": 72.1, "unit": "mW", "status": "OK"},
    {"component": "Battery", "power": 276.1, "unit": "mW", "status": "OK"}
  ],
  "summary": "Plain English analysis with recommendations.",
  "warnings": ["Warning if any"]
}
LED forward voltage: red/yellow ~2V, blue/white ~3.2V. Output valid JSON only."""

BOM_PROMPT = """You are an electronics procurement expert. Generate a complete Bill of Materials (BOM).
Given a circuit description or component list, respond ONLY with valid JSON:
{
  "project_name": "Circuit name",
  "total_cost_usd": 4.75,
  "items": [
    {
      "ref": "R1",
      "description": "Carbon Film Resistor",
      "value": "220Ω",
      "part_number": "CF14JT220R",
      "quantity": 1,
      "unit_cost": 0.10,
      "total_cost": 0.10,
      "supplier": "DigiKey",
      "supplier_url": "https://www.digikey.com",
      "package": "Through-hole axial",
      "notes": "1/4W, 5% tolerance"
    }
  ],
  "tools_needed": ["Breadboard", "Multimeter", "Wire stripper"],
  "estimated_build_time": "30 minutes",
  "difficulty": "Beginner"
}
Output valid JSON only."""

LEARN_PROMPT = """You are a friendly electronics teacher explaining concepts to beginners.
When asked to explain a circuit concept, component, or how something works, respond in this format:

Start with a one-sentence plain-English summary.
Then use clear markdown sections:
## How it works
## The math (keep it simple, show the formula then plug in numbers)
## Real-world analogy
## Common mistakes to avoid
## Try it yourself (simple experiment suggestion)

Be encouraging, use analogies, avoid jargon. Aim for a 16-year-old audience."""

# ── Schematic Renderer ─────────────────────────────────────────────────────────

def render_schematic(schema: dict) -> str:
    try:
        components = schema.get("components", [])
        title = schema.get("title", "Circuit Schematic")
        difficulty = schema.get("difficulty", "")

        fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0a0f1a")
        ax.set_facecolor("#0a0f1a")

        with schemdraw.Drawing(canvas=ax) as d:
            d.config(fontsize=11, color="#c8d8e8", lw=1.8)
            for comp in components:
                ctype = comp.get("type", "").lower()
                label = comp.get("label", "")
                value = comp.get("value", "")
                dl = f"{label}\n{value}" if value else label
                if ctype == "resistor":
                    d.add(elm.Resistor().right().label(dl, loc="top"))
                elif ctype == "capacitor":
                    d.add(elm.Capacitor().right().label(dl, loc="top"))
                elif ctype == "led":
                    d.add(elm.LED().right().label(dl, loc="top").color("#00ff88"))
                elif ctype == "battery":
                    d.add(elm.Battery().up().label(dl, loc="left"))
                elif ctype == "switch":
                    d.add(elm.Switch().right().label(dl, loc="top"))
                elif ctype == "diode":
                    d.add(elm.Diode().right().label(dl, loc="top"))
                elif ctype == "ground":
                    d.add(elm.Ground())
                elif ctype == "transistor":
                    d.add(elm.BjtNpn(circle=True).anchor("base").label(dl))
                elif ctype == "inductor":
                    d.add(elm.Inductor().right().label(dl, loc="top"))
                elif ctype == "potentiometer":
                    d.add(elm.Potentiometer().right().label(dl, loc="top"))
                else:
                    d.add(elm.Resistor().right().label(dl, loc="top"))
            if len(components) > 1:
                d.add(elm.Line().down())
                d.add(elm.Line().left())
                d.add(elm.Line().up())

        title_full = f"{title}  [{difficulty}]" if difficulty else title
        ax.set_title(title_full, color="#00d4ff", fontsize=13,
                     fontweight="bold", fontfamily="monospace", pad=10)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=160, bbox_inches="tight",
                    facecolor="#0a0f1a", edgecolor="none")
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        return _fallback_schematic(schema, str(e))


def _fallback_schematic(schema: dict, error: str) -> str:
    components = schema.get("components", [])
    title = schema.get("title", "Circuit Schematic")
    lines = [f"  {title}", "─"*44, schema.get("description",""), "", "Components:"]
    for c in components:
        lines.append(f"  [{c.get('type','?').upper():12s}]  {c.get('label','')}  {c.get('value','')}")
    lines += ["", "Connections:"]
    for cn in schema.get("connections", []):
        lines.append(f"  {cn.get('from','')}  →  {cn.get('to','')}")
    fig, ax = plt.subplots(figsize=(9, max(4, len(lines)*0.32)), facecolor="#0a0f1a")
    ax.set_facecolor("#0a0f1a"); ax.axis("off")
    ax.text(0.04, 0.97, "\n".join(lines), transform=ax.transAxes,
            fontsize=10, color="#39d353", va="top", fontfamily="monospace", linespacing=1.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a0f1a")
    plt.close(); buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ── Falstad URL Builder ────────────────────────────────────────────────────────

def build_falstad_url(schema: dict) -> str:
    try:
        components = schema.get("components", [])
        lines = ["$ 1 0.000005 10.235265340896002 50 5 43 5e-11"]
        step = 96
        for i, comp in enumerate(components):
            ctype = comp.get("type","").lower()
            vs = comp.get("value","1000").replace("Ω","").replace("V","").replace("mA","")
            try:
                val = float(re.sub(r"[^\d.]","",vs) or "1000")
                if "k" in vs.lower(): val *= 1000
            except: val = 1000
            x1,y1,x2,y2 = 48+i*step,48,48+(i+1)*step,48
            if ctype=="resistor":   lines.append(f"r {x1} {y1} {x2} {y2} 0 {val}")
            elif ctype=="capacitor":lines.append(f"c {x1} {y1} {x2} {y2} 0 {val/1e9} 0")
            elif ctype=="led":      lines.append(f"d {x1} {y1} {x2} {y2} 2 default-led")
            elif ctype=="battery":  lines.append(f"v {x1} {y2+step} {x1} {y1} 0 0 40 {val} 0 0 0.5")
            elif ctype=="switch":   lines.append(f"s {x1} {y1} {x2} {y2} 0 0 false")
            elif ctype=="diode":    lines.append(f"d {x1} {y1} {x2} {y2} 2 default")
            else:                   lines.append(f"r {x1} {y1} {x2} {y2} 0 1000")
        encoded = base64.b64encode("\n".join(lines).encode()).decode()
        return f"https://falstad.com/circuit/circuitjs.html?ctz={encoded}"
    except:
        return "https://falstad.com/circuit/circuitjs.html"


# ── PDF Export ─────────────────────────────────────────────────────────────────

def generate_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    def PS(name, **kw): return ParagraphStyle(name, parent=styles["Normal"], **kw)
    title_s  = PS("T", fontSize=22, textColor=colors.HexColor("#003366"), spaceAfter=4, alignment=TA_CENTER, fontName="Helvetica-Bold")
    sub_s    = PS("S", fontSize=10, textColor=colors.HexColor("#555555"), spaceAfter=12, alignment=TA_CENTER)
    h2_s     = PS("H2", fontSize=13, textColor=colors.HexColor("#003366"), spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold")
    body_s   = PS("B", fontSize=10, leading=15)
    warn_s   = PS("W", fontSize=10, leading=14, textColor=colors.HexColor("#cc6600"), leftIndent=10)
    code_s   = PS("C", fontSize=8, leading=11, backColor=colors.HexColor("#f4f4f4"), leftIndent=8, fontName="Courier")
    footer_s = PS("F", fontSize=8, textColor=colors.HexColor("#999999"), alignment=TA_CENTER)

    story = []
    now = datetime.datetime.now().strftime("%B %d, %Y %H:%M")
    story.append(Paragraph("⚡ Circuit Copilot", title_s))
    story.append(Paragraph(f"AI-Powered Circuit Design Report · {now}", sub_s))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#003366")))
    story.append(Spacer(1, 8*mm))

    if data.get("project_name"):
        story.append(Paragraph(f"Project: {data['project_name']}", PS("pn", fontSize=14, textColor=colors.HexColor("#003366"), fontName="Helvetica-Bold")))
        story.append(Spacer(1, 4*mm))

    if data.get("schematic_image"):
        story.append(Paragraph("Circuit Schematic", h2_s))
        img_buf = io.BytesIO(base64.b64decode(data["schematic_image"]))
        story.append(RLImage(img_buf, width=160*mm, height=90*mm))
        story.append(Spacer(1, 4*mm))
    if data.get("schematic_description"):
        story.append(Paragraph(data["schematic_description"], body_s))
        story.append(Spacer(1, 6*mm))

    if data.get("bom"):
        bom = data["bom"]
        story.append(Paragraph("Bill of Materials", h2_s))
        rows = [["Ref","Description","Value","Qty","Unit Cost","Total","Supplier"]]
        for item in bom.get("items",[]):
            rows.append([
                item.get("ref",""), item.get("description",""),
                item.get("value",""), str(item.get("quantity",1)),
                f"${item.get('unit_cost',0):.2f}", f"${item.get('total_cost',0):.2f}",
                item.get("supplier","")
            ])
        rows.append(["","","","","TOTAL", f"${bom.get('total_cost_usd',0):.2f}",""])
        t = Table(rows, colWidths=[15*mm,45*mm,22*mm,10*mm,20*mm,20*mm,28*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#003366")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#e8f0fe")),
            ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.HexColor("#f0f4ff"),colors.white]),
            ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cccccc")),
            ("ALIGN",(3,0),(-1,-1),"CENTER"),
            ("PADDING",(0,0),(-1,-1),5),
        ]))
        story.append(t)
        if bom.get("tools_needed"):
            story.append(Spacer(1,4*mm))
            story.append(Paragraph("Tools needed: " + ", ".join(bom["tools_needed"]), body_s))
        if bom.get("estimated_build_time"):
            story.append(Paragraph(f"Estimated build time: {bom['estimated_build_time']}", body_s))
        story.append(Spacer(1, 6*mm))

    if data.get("components") and not data.get("bom"):
        story.append(Paragraph("Component List", h2_s))
        rows = [["ID","Type","Value","Label"]]
        for c in data["components"]:
            rows.append([c.get("id",""), c.get("type","").capitalize(), c.get("value","—"), c.get("label","")])
        t = Table(rows, colWidths=[25*mm,40*mm,40*mm,40*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#003366")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f0f4ff"),colors.white]),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#cccccc")),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("PADDING",(0,0),(-1,-1),6),
        ]))
        story.append(t)
        story.append(Spacer(1,6*mm))

    if data.get("simulation"):
        sim = data["simulation"]
        story.append(Paragraph("Simulation Results", h2_s))
        story.append(Paragraph(sim.get("summary",""), body_s))
        story.append(Spacer(1,4*mm))
        if sim.get("nodes"):
            node_rows = [["Node","Voltage","Description"]]
            for n in sim["nodes"]:
                node_rows.append([n.get("name",""), f"{n.get('voltage',0)} {n.get('unit','V')}", n.get("description","")])
            nt = Table(node_rows, colWidths=[40*mm,30*mm,100*mm])
            nt.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#005588")),
                ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,-1),9),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#eef6ff"),colors.white]),
                ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#cccccc")),
                ("PADDING",(0,0),(-1,-1),5),
            ]))
            story.append(nt)
            story.append(Spacer(1,4*mm))
        if sim.get("warnings"):
            story.append(Paragraph("⚠ Warnings", PS("wh", fontSize=11, textColor=colors.HexColor("#cc6600"), fontName="Helvetica-Bold")))
            for w in sim["warnings"]:
                story.append(Paragraph(f"• {w}", warn_s))
            story.append(Spacer(1,4*mm))

    if data.get("arduino_code"):
        story.append(Paragraph("Arduino Code", h2_s))
        code = data["arduino_code"]
        m = re.search(r"```(?:cpp|arduino|ino)?\n([\s\S]*?)```", code)
        clean = m.group(1) if m else code
        for line in clean[:3000].split("\n"):
            story.append(Paragraph(line.replace(" ","&nbsp;").replace("<","&lt;") or "&nbsp;", code_s))
        story.append(Spacer(1,4*mm))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1,3*mm))
    story.append(Paragraph("Generated by Circuit Copilot v3 · Powered by Groq LLaMA 3.3 70B · Free & Open Source", footer_s))
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── LLM Helper ─────────────────────────────────────────────────────────────────

def llm(system: str, messages: list, max_tokens: int = 1024) -> str:
    resp = client.chat.completions.create(
        model=GROQ_MODEL, max_tokens=max_tokens,
        messages=[{"role":"system","content":system}] + messages
    )
    return resp.choices[0].message.content


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.post("/api/schematic")
async def generate_schematic(request: Request):
    body = await request.json()
    user_input = body.get("prompt","")
    history = body.get("history",[])
    if not user_input:
        return JSONResponse({"error":"No prompt"}, status_code=400)
    raw = llm(SCHEMATIC_PROMPT, history + [{"role":"user","content":user_input}], 1200)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return JSONResponse({"error":"Could not parse schematic JSON","raw":raw}, status_code=500)
    schema = json.loads(m.group())
    return JSONResponse({
        "schema": schema,
        "image": render_schematic(schema),
        "description": schema.get("description",""),
        "title": schema.get("title",""),
        "difficulty": schema.get("difficulty",""),
        "use_case": schema.get("use_case",""),
        "falstad_url": build_falstad_url(schema),
        "assistant_message": f"{schema.get('title','Circuit')}: {schema.get('description','')}"
    })


@app.post("/api/components")
async def recommend_components(request: Request):
    body = await request.json()
    history = body.get("history",[])
    result = llm(COMPONENT_PROMPT, history+[{"role":"user","content":body.get("prompt","")}], 1200)
    return JSONResponse({"result": result})


@app.post("/api/debug")
async def debug_circuit(request: Request):
    body = await request.json()
    history = body.get("history",[])
    result = llm(DEBUG_PROMPT, history+[{"role":"user","content":body.get("prompt","")}], 1200)
    return JSONResponse({"result": result})


@app.post("/api/arduino")
async def generate_arduino(request: Request):
    body = await request.json()
    history = body.get("history",[])
    result = llm(ARDUINO_PROMPT, history+[{"role":"user","content":body.get("prompt","")}], 2500)
    return JSONResponse({"result": result})


@app.post("/api/simulate")
async def simulate_circuit(request: Request):
    body = await request.json()
    history = body.get("history",[])
    raw = llm(SIMULATION_PROMPT, history+[{"role":"user","content":body.get("prompt","")}], 1500)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return JSONResponse({"error":"Could not parse simulation JSON","raw":raw}, status_code=500)
    return JSONResponse({"simulation": json.loads(m.group())})


@app.post("/api/bom")
async def generate_bom(request: Request):
    body = await request.json()
    history = body.get("history",[])
    raw = llm(BOM_PROMPT, history+[{"role":"user","content":body.get("prompt","")}], 1500)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return JSONResponse({"error":"Could not parse BOM JSON","raw":raw}, status_code=500)
    return JSONResponse({"bom": json.loads(m.group())})


@app.post("/api/learn")
async def learn(request: Request):
    body = await request.json()
    history = body.get("history",[])
    result = llm(LEARN_PROMPT, history+[{"role":"user","content":body.get("prompt","")}], 1500)
    return JSONResponse({"result": result})


@app.post("/api/save-circuit")
async def save_circuit(request: Request):
    body = await request.json()
    name = body.get("name", "Untitled Circuit").strip() or "Untitled Circuit"
    is_public = 1 if body.get("is_public") else 0
    
    tech_data = {
        "schematic_image": body.get("schematic_image"),
        "schematic_description": body.get("schematic_description", ""),
        "components": body.get("components", []),
        "simulation": body.get("simulation"),
        "arduino_code": body.get("arduino_code", ""),
        "bom": body.get("bom"),
    }
    
    saved_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO circuits (name, saved_at, data, is_public) VALUES (?, ?, ?, ?)",
            (name, saved_at, json.dumps(tech_data), is_public)
        )
        cid = cursor.lastrowid
        
    return JSONResponse({"id": str(cid), "name": name})


@app.get("/api/list-circuits")
async def list_circuits():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, saved_at FROM circuits ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        
    return JSONResponse({"circuits": [
        {"id": str(row[0]), "name": row[1], "saved_at": row[2]}
        for row in rows
    ]})


@app.get("/api/load-circuit/{cid}")
async def load_circuit(cid: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, saved_at, data FROM circuits WHERE id = ?", (cid,))
        row = cursor.fetchone()
        
    if not row:
        return JSONResponse({"error": "Not found"}, status_code=404)
        
    data = json.loads(row[2])
    data["name"] = row[0]
    data["saved_at"] = row[1]
    return JSONResponse(data)


@app.get("/api/gallery")
async def get_gallery():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, saved_at, data FROM circuits WHERE is_public = 1 ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        
    gallery = []
    for row in rows:
        tech = json.loads(row[3])
        gallery.append({
            "id": str(row[0]),
            "name": row[1],
            "saved_at": row[2],
            "image": tech.get("schematic_image"),
            "description": tech.get("schematic_description")
        })
    return JSONResponse({"gallery": gallery})


@app.post("/api/export-pdf")
async def export_pdf(request: Request):
    data = await request.json()
    pdf_bytes = generate_pdf(data)
    fname = data.get("project_name","circuit_report").replace(" ","_") + ".pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.get("/", response_class=HTMLResponse)
async def landing():
    with open("static/landing.html","r") as f:
        return f.read()

@app.get("/app", response_class=HTMLResponse)
async def main_app():
    with open("static/index.html","r") as f:
        return f.read()

app.mount("/static", StaticFiles(directory="static"), name="static")
