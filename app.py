import os, io, json, base64, re, datetime
from typing import List, Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

async def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    retry_after = int(exc.retry_after) if hasattr(exc, "retry_after") else 60
    return JSONResponse(
        {"error": "Rate limit exceeded", "retry_after": retry_after,
         "message": f"Too many requests. Please wait {retry_after} seconds."},
        status_code=429, headers={"Retry-After": str(retry_after)})

app = FastAPI(title="Circuit Copilot v4")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)
client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
GROQ_MODEL        = "llama-3.3-70b-specdec"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_AGENT_MODEL  = "compound-beta"   # Agentic model with built-in web search

# ── Database ───────────────────────────────────────────────────────────────────
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Initialize Supabase client if credentials exist, otherwise None
if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None
    print("WARNING: Supabase credentials not found. Database features will be unavailable.")

# ── WebSocket Collaboration ────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    async def connect(self, ws: WebSocket, cid: str):
        await ws.accept()
        self.active_connections.setdefault(cid, []).append(ws)
    def disconnect(self, ws: WebSocket, cid: str):
        if cid in self.active_connections:
            self.active_connections[cid].remove(ws)
    async def broadcast(self, msg: str, cid: str, sender: WebSocket):
        for c in self.active_connections.get(cid, []):
            if c != sender: await c.send_text(msg)
manager = ConnectionManager()

# ── System Prompts ─────────────────────────────────────────────────────────────
SCHEMATIC_PROMPT = """You are an expert electronics engineer. When the user describes a circuit,
respond with ONLY a JSON object — no markdown, no explanation.

The JSON MUST include x/y grid coordinates so the frontend can draw a proper schematic:
- Battery/power → left side, orientation "up"
- Series components → arranged left-to-right horizontally
- Ground → bottom
- Parallel branches → stacked vertically (different y values)
- x/y are grid units (integers 0-8); keep layout compact and sensible

Example for "LED with 220Ω resistor, 9V battery":
{
  "components": [
    {"id":"V1","type":"battery","value":"9V","label":"V1","x":0,"y":1,"orientation":"up"},
    {"id":"R1","type":"resistor","value":"220Ω","label":"R1","x":1,"y":0,"orientation":"right"},
    {"id":"LED1","type":"led","value":"red","label":"LED1","x":2,"y":0,"orientation":"right"},
    {"id":"GND1","type":"ground","value":"","label":"GND","x":2,"y":2,"orientation":"down"}
  ],
  "connections":[
    {"from":"V1.pos","to":"R1.start"},
    {"from":"R1.end","to":"LED1.anode"},
    {"from":"LED1.cathode","to":"GND1.top"},
    {"from":"V1.neg","to":"GND1.top"}
  ],
  "nets":[
    {"name":"VCC","nodes":["V1.pos","R1.start"]},
    {"name":"MID","nodes":["R1.end","LED1.anode"]},
    {"name":"GND","nodes":["LED1.cathode","V1.neg","GND1.top"]}
  ],
  "title":"LED Circuit",
  "description":"Series LED circuit with current-limiting resistor. I = (9-2)/220 ≈ 31.8mA.",
  "difficulty":"Beginner",
  "use_case":"Indicators, learning circuits"
}

Supported types: resistor, capacitor, led, battery, switch, ground, diode, transistor,
inductor, ic, potentiometer, mosfet, op_amp, voltage_reg, buzzer, motor.
orientation values: "right","left","up","down"
Output valid JSON only."""

COMPONENT_PROMPT = """You are an expert electronics component advisor (multi-turn).
For each component include: exact part number, key specs, why it fits, cost USD, supplier.
Use markdown tables. Be beginner-friendly but technically precise."""

DEBUG_PROMPT = """You are an expert circuit debugger (multi-turn).
For each issue: name it, explain why (physics), give exact fix with values,
rate 🔴Critical/🟡Warning/🟢Info. Use markdown."""

ARDUINO_PROMPT = """You are an expert Arduino programmer (multi-turn).
Generate complete upload-ready .ino code: #define pin constants, comments on every block,
full setup()+loop(), Serial.begin(9600), required libraries noted.
After code, explain in 3-5 sentences."""

SIMULATION_PROMPT = """You are a circuit simulation expert. Perform DC operating point analysis.
Respond ONLY with valid JSON — no markdown, no explanation:
{
  "circuit_title":"name","supply_voltage":9,"supply_unit":"V",
  "nodes":[{"id":"N1","name":"V_supply","voltage":9.0,"unit":"V","description":"..."}],
  "branches":[{"id":"B1","name":"Loop","current":31.8,"unit":"mA","through":"R1,LED1","description":"..."}],
  "power":[{"component":"R1","power":223,"unit":"mW","status":"OK"}],
  "summary":"Plain English summary with key values and safety notes.",
  "warnings":[]
}"""

BOM_PROMPT = """You are an electronics procurement expert. Respond ONLY with valid JSON:
{
  "project_name":"name","total_cost_usd":4.75,
  "items":[{
    "ref":"R1","description":"Carbon Film Resistor","value":"220Ω",
    "part_number":"CF14JT220R","quantity":1,"unit_cost":0.10,"total_cost":0.10,
    "supplier":"DigiKey","supplier_url":"https://www.digikey.com",
    "package":"Through-hole axial","notes":"1/4W 5%"
  }],
  "tools_needed":["Breadboard","Multimeter"],
  "estimated_build_time":"30 minutes","difficulty":"Beginner"
}"""

LEARN_PROMPT = """You are a friendly electronics teacher for beginners (multi-turn).
Format: one-sentence summary, then markdown sections:
## How it works  ## The math  ## Real-world analogy
## Common mistakes  ## Try it yourself
Encourage, use analogies, avoid jargon. Audience: 16-year-olds."""

BREADBOARD_PROMPT = """You are an expert electronics router.
You will receive a JSON circuit schema. Your job is to map these components onto a standard half-size breadboard (30 columns).
The breadboard has:
- Top power rails: 'top_+' and 'top_-'
- Bottom power rails: 'bottom_+' and 'bottom_-'
- Main terminal strips: rows 'A'-'C' (top half) and 'D'-'F' (bottom half), columns 1 to 30.
Output ONLY valid JSON matching this schema:
{
  "routing": [
    {"id": "R1", "type": "resistor", "start": "B2", "end": "B6", "color": "#0090ff", "value": "1k\u03a9"},
    {"id": "V1", "type": "battery", "start": "top_+", "end": "top_-", "color": "#ff3333", "value": "9V"},
    {"id": "LED1", "type": "led", "start": "C6", "end": "top_-", "color": "#00f090", "value": "Red"},
    {"id": "Wire1", "type": "wire", "start": "top_+", "end": "A2", "color": "#ff3333", "value": "Jumper"}
  ],
  "steps": [
    "1. Connect Battery V1 positive to top + rail and negative to top - rail.",
    "2. Place Resistor R1 from B2 to B6.",
    "3. Insert LED1 anode at C6 and cathode to top - rail."
  ]
}
Ensure connections physically make sense and match the schematic. Components must share columns to connect. Example: if R1 ends at column 6, LED1 must start at column 6 to be in series.
Output valid JSON only. No markdown formatting."""

IMAGE_CIRCUIT_PROMPT = """You are an expert electronics engineer with vision.
Analyze this image (hand-drawn circuit, breadboard photo, or PCB).
Identify all components and connections. Respond ONLY with valid JSON matching this schema:
{
  "components":[{"id":"V1","type":"battery","value":"9V","label":"V1","x":0,"y":1,"orientation":"up"}],
  "connections":[{"from":"V1.pos","to":"R1.start"}],
  "nets":[{"name":"VCC","nodes":["V1.pos","R1.start"]}],
  "title":"Identified Circuit",
  "description":"What this circuit does.",
  "difficulty":"Beginner","use_case":"...",
  "confidence":"high",
  "notes":"Any caveats about image quality or identification uncertainty."
}
Supported types: resistor,capacitor,led,battery,switch,ground,diode,transistor,inductor,ic,potentiometer,mosfet,op_amp.
Output valid JSON only."""

# ── Schematic PNG Renderer (used for PDF export & fallback) ───────────────────
def render_schematic(schema: dict) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import schemdraw
        import schemdraw.elements as elm

        components = schema.get("components", [])
        title      = schema.get("title", "Circuit")
        difficulty = schema.get("difficulty", "")
        fig, ax = plt.subplots(figsize=(11, 6.5), facecolor="#07090f")
        ax.set_facecolor("#07090f")
        with schemdraw.Drawing(canvas=ax) as d:
            d.config(fontsize=11, color="#c8d8e8", lw=2.0)
            batts  = [c for c in components if c.get("type")=="battery"]
            series = [c for c in components if c.get("type") not in ("battery","ground")]
            grnds  = [c for c in components if c.get("type")=="ground"]
            def _elem(c):
                t = c.get("type",""); lbl = c.get("label",""); val = c.get("value","")
                dl = f"{lbl}\n{val}" if val else lbl
                mapping = {
                    "resistor":    elm.Resistor().right().label(dl, loc="top"),
                    "capacitor":   elm.Capacitor().right().label(dl, loc="top"),
                    "led":         elm.LED().right().label(dl, loc="top").color("#00ff88"),
                    "battery":     elm.Battery().up().label(dl, loc="left"),
                    "switch":      elm.Switch().right().label(dl, loc="top"),
                    "diode":       elm.Diode().right().label(dl, loc="top"),
                    "ground":      elm.Ground(),
                    "transistor":  elm.BjtNpn(circle=True).anchor("base").label(dl),
                    "inductor":    elm.Inductor().right().label(dl, loc="top"),
                    "potentiometer": elm.Potentiometer().right().label(dl, loc="top"),
                }
                return mapping.get(t, elm.Resistor().right().label(dl, loc="top"))
            for c in batts:  d.add(_elem(c))
            for c in series: d.add(_elem(c))
            if series and (batts or grnds):
                d.add(elm.Line().down())
                d.add(elm.Line().left())
                if grnds: d.add(elm.Ground())
                else:     d.add(elm.Line().up())
        title_txt = f"{title}  [{difficulty}]" if difficulty else title
        ax.set_title(title_txt, color="#00c8f0", fontsize=13,
                     fontweight="bold", fontfamily="monospace", pad=10)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                    facecolor="#07090f", edgecolor="none")
        plt.close(); buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        return _fallback_schematic(schema, str(e))

def _fallback_schematic(schema: dict, error: str) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    components = schema.get("components", [])
    title = schema.get("title", "Circuit")
    lines = [f"  {title}", "─"*44, schema.get("description",""), "", "Components:"]
    for c in components:
        lines.append(f"  [{c.get('type','?').upper():12s}]  {c.get('label','')}  {c.get('value','')}")
    lines += ["", "Connections:"]
    for cn in schema.get("connections", []):
        lines.append(f"  {cn.get('from','')}  →  {cn.get('to','')}")
    fig, ax = plt.subplots(figsize=(9, max(4, len(lines)*0.32)), facecolor="#07090f")
    ax.set_facecolor("#07090f"); ax.axis("off")
    ax.text(0.04, 0.97, "\n".join(lines), transform=ax.transAxes,
            fontsize=10, color="#39d353", va="top", fontfamily="monospace", linespacing=1.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#07090f")
    plt.close(); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ── Falstad URL ────────────────────────────────────────────────────────────────
def build_falstad_url(schema: dict) -> str:
    try:
        comps = schema.get("components", [])
        lines = ["$ 1 0.000005 10.235265340896002 50 5 43 5e-11"]
        step = 112; cx, cy = 160, 160
        batts  = [c for c in comps if c.get("type")=="battery"]
        series = [c for c in comps if c.get("type") not in ("battery","ground","wire")]
        def _val(comp):
            vs = re.sub(r"[^\d.km]","", comp.get("value","1000").lower()) or "1000"
            try:
                v = float(re.sub(r"[^\d.]","",vs) or "1000")
                if "k" in vs: v *= 1000
                if "m" in vs and comp.get("type") not in ("battery",): v /= 1000
            except: v = 1000
            return v
        for b in batts:
            v = _val(b)
            lines.append(f"v {cx-step//2} {cy+step//2} {cx-step//2} {cy-step//2} 0 0 40 {v} 0 0 0.5")
        for i, c in enumerate(series):
            t = c.get("type","resistor"); v = _val(c)
            x1 = cx + i*step; y1 = cy - step//2; x2 = x1 + step; y2 = y1
            if t == "resistor":   lines.append(f"r {x1} {y1} {x2} {y2} 0 {v}")
            elif t == "capacitor":lines.append(f"c {x1} {y1} {x2} {y2} 0 {v*1e-6} 0")
            elif t == "led":      lines.append(f"d {x1} {y1} {x2} {y2} 2 default-led")
            elif t == "diode":    lines.append(f"d {x1} {y1} {x2} {y2} 2 default")
            elif t == "switch":   lines.append(f"s {x1} {y1} {x2} {y2} 0 1 false")
            elif t == "inductor": lines.append(f"l {x1} {y1} {x2} {y2} 0 {v*1e-3}")
            else:                 lines.append(f"r {x1} {y1} {x2} {y2} 0 1000")
        encoded = base64.b64encode("\n".join(lines).encode()).decode()
        return f"https://falstad.com/circuit/circuitjs.html?ctz={encoded}"
    except:
        return "https://falstad.com/circuit/circuitjs.html"

# ── PDF Export ─────────────────────────────────────────────────────────────────
def generate_pdf(data: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Image as RLImage, Table, TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    def PS(n, **kw): return ParagraphStyle(n, parent=styles["Normal"], **kw)
    T  = PS("T",  fontSize=22, textColor=colors.HexColor("#003366"), spaceAfter=4,  alignment=TA_CENTER, fontName="Helvetica-Bold")
    S  = PS("S",  fontSize=10, textColor=colors.HexColor("#555"),    spaceAfter=12, alignment=TA_CENTER)
    H2 = PS("H2", fontSize=13, textColor=colors.HexColor("#003366"), spaceBefore=14,spaceAfter=6, fontName="Helvetica-Bold")
    B  = PS("B",  fontSize=10, leading=15)
    W  = PS("W",  fontSize=10, leading=14, textColor=colors.HexColor("#cc6600"), leftIndent=10)
    C  = PS("C",  fontSize=8,  leading=11, fontName="Courier")
    F  = PS("F",  fontSize=8,  textColor=colors.HexColor("#999"), alignment=TA_CENTER)
    story = []
    now = datetime.datetime.now().strftime("%B %d, %Y %H:%M")
    story += [Paragraph("⚡ Circuit Copilot", T),
              Paragraph(f"AI-Powered Circuit Design Report · {now}", S),
              HRFlowable(width="100%", thickness=2, color=colors.HexColor("#003366")),
              Spacer(1, 8*mm)]
    if data.get("project_name"):
        story += [Paragraph(f"Project: {data['project_name']}", PS("pn",fontSize=14,textColor=colors.HexColor("#003366"),fontName="Helvetica-Bold")),
                  Spacer(1, 4*mm)]
    if data.get("schematic_image"):
        story.append(Paragraph("Circuit Schematic", H2))
        story.append(RLImage(io.BytesIO(base64.b64decode(data["schematic_image"])), width=160*mm, height=90*mm))
        story.append(Spacer(1, 4*mm))
    if data.get("schematic_description"):
        story += [Paragraph(data["schematic_description"], B), Spacer(1, 6*mm)]
    if data.get("bom"):
        bom = data["bom"]
        story.append(Paragraph("Bill of Materials", H2))
        rows = [["Ref","Description","Value","Qty","Unit $","Total","Supplier"]]
        for it in bom.get("items",[]):
            rows.append([it.get("ref",""),it.get("description",""),it.get("value",""),
                         str(it.get("quantity",1)),f"${it.get('unit_cost',0):.2f}",
                         f"${it.get('total_cost',0):.2f}",it.get("supplier","")])
        rows.append(["","","","","TOTAL",f"${bom.get('total_cost_usd',0):.2f}",""])
        t = Table(rows, colWidths=[15*mm,45*mm,22*mm,10*mm,18*mm,18*mm,32*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#003366")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
            ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#e8f0fe")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.HexColor("#f0f4ff"),colors.white]),
            ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#ccc")),("PADDING",(0,0),(-1,-1),5),
        ]))
        story += [t, Spacer(1, 6*mm)]
    if data.get("simulation"):
        sim = data["simulation"]
        story.append(Paragraph("Simulation Results", H2))
        story += [Paragraph(sim.get("summary",""), B), Spacer(1,4*mm)]
        if sim.get("nodes"):
            nr = [["Node","Voltage","Description"]]
            for n in sim["nodes"]: nr.append([n.get("name",""),f"{n.get('voltage',0)} {n.get('unit','V')}",n.get("description","")])
            nt = Table(nr, colWidths=[40*mm,30*mm,100*mm])
            nt.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#005588")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#eef6ff"),colors.white]),
                ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#ccc")),("PADDING",(0,0),(-1,-1),5),
            ]))
            story += [nt, Spacer(1,4*mm)]
        for w in sim.get("warnings",[]): story.append(Paragraph(f"⚠ {w}", W))
    if data.get("arduino_code"):
        story.append(Paragraph("Arduino Code", H2))
        code = data["arduino_code"]
        m = re.search(r"```(?:cpp|arduino|ino)?\n([\s\S]*?)```", code)
        for line in (m.group(1) if m else code)[:3000].split("\n"):
            story.append(Paragraph(line.replace(" ","&nbsp;").replace("<","&lt;") or "&nbsp;", C))
    story += [HRFlowable(width="100%",thickness=1,color=colors.HexColor("#ccc")),Spacer(1,3*mm),
              Paragraph("Generated by Circuit Copilot v4 · Powered by Groq LLaMA 3.3 70B · github.com/smemon819/circuit-copilot", F)]
    doc.build(story)
    buf.seek(0)
    return buf.read()

# ── LLM Helpers ────────────────────────────────────────────────────────────────
def llm(system: str, messages: list, max_tokens: int = 1024) -> str:
    r = client.chat.completions.create(
        model=GROQ_MODEL, max_tokens=max_tokens,
        messages=[{"role":"system","content":system}] + messages)
    return r.choices[0].message.content

async def llm_stream(system: str, messages: list, max_tokens: int = 1024):
    """Async generator yielding SSE chunks."""
    stream = client.chat.completions.create(
        model=GROQ_MODEL, max_tokens=max_tokens, stream=True,
        messages=[{"role":"system","content":system}] + messages)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield f"data: {json.dumps({'content': delta})}\n\n"
    yield "data: [DONE]\n\n"

def llm_compound(system: str, messages: list, max_tokens: int = 1500) -> str:
    """Call compound-beta with web_search tool for live data (prices, stock)."""
    try:
        r = client.chat.completions.create(
            model=GROQ_AGENT_MODEL, max_tokens=max_tokens,
            messages=[{"role":"system","content":system}] + messages)
        return r.choices[0].message.content
    except Exception:
        # Fallback to standard model if compound-beta unavailable
        return llm(system, messages, max_tokens)

async def llm_compound_stream(system: str, messages: list, max_tokens: int = 1500):
    """Streaming variant of compound-beta with graceful fallback."""
    try:
        stream = client.chat.completions.create(
            model=GROQ_AGENT_MODEL, max_tokens=max_tokens, stream=True,
            messages=[{"role":"system","content":system}] + messages)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {json.dumps({'content': delta})}\n\n"
    except Exception:
        async for chunk in llm_stream(system, messages, max_tokens):
            yield chunk
    yield "data: [DONE]\n\n"


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.post("/api/schematic")
@limiter.limit("5/minute")
async def generate_schematic(request: Request):
    body = await request.json()
    prompt = body.get("prompt",""); history = body.get("history",[])
    if not prompt: return JSONResponse({"error":"No prompt"}, status_code=400)
    raw = llm(SCHEMATIC_PROMPT, history+[{"role":"user","content":prompt}], 1600)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m: return JSONResponse({"error":"Could not parse schematic JSON","raw":raw}, status_code=500)
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

@app.post("/api/image-to-circuit")
@limiter.limit("5/minute")
async def image_to_circuit(request: Request):
    """Vision endpoint: base64 image → identified circuit schema."""
    body = await request.json()
    image_b64  = body.get("image","")
    image_type = body.get("type","image/jpeg")
    if not image_b64:
        return JSONResponse({"error":"No image provided"}, status_code=400)
    try:
        resp = client.chat.completions.create(
            model=GROQ_VISION_MODEL, max_tokens=1600,
            messages=[{"role":"user","content":[
                {"type":"image_url","image_url":{"url":f"data:{image_type};base64,{image_b64}"}},
                {"type":"text","text":IMAGE_CIRCUIT_PROMPT}
            ]}])
        raw = resp.choices[0].message.content
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m: return JSONResponse({"error":"Could not parse vision response","raw":raw}, status_code=500)
        schema = json.loads(m.group())
        return JSONResponse({
            "schema": schema, "image": render_schematic(schema),
            "description": schema.get("description",""),
            "title": schema.get("title","Identified Circuit"),
            "difficulty": schema.get("difficulty",""),
            "confidence": schema.get("confidence","medium"),
            "notes": schema.get("notes",""),
            "falstad_url": build_falstad_url(schema),
        })
    except Exception as e:
        return JSONResponse({"error": f"Vision error: {str(e)}"}, status_code=500)

@app.post("/api/components")
@limiter.limit("10/minute")
async def recommend_components(request: Request):
    body = await request.json()
    result = llm_compound(COMPONENT_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1500)
    return JSONResponse({"result": result, "model": "compound-beta"})

@app.post("/api/components/stream")
@limiter.limit("10/minute")
async def components_stream(request: Request):
    body = await request.json()
    return StreamingResponse(
        llm_compound_stream(COMPONENT_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1500),
        media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/debug")
@limiter.limit("10/minute")
async def debug_circuit(request: Request):
    body = await request.json()
    result = llm(DEBUG_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1200)
    return JSONResponse({"result": result})

@app.post("/api/debug/stream")
@limiter.limit("10/minute")
async def debug_stream(request: Request):
    body = await request.json()
    return StreamingResponse(
        llm_stream(DEBUG_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1200),
        media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/arduino")
@limiter.limit("10/minute")
async def generate_arduino(request: Request):
    body = await request.json()
    result = llm(ARDUINO_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 2500)
    return JSONResponse({"result": result})

@app.post("/api/arduino/stream")
@limiter.limit("10/minute")
async def arduino_stream(request: Request):
    body = await request.json()
    return StreamingResponse(
        llm_stream(ARDUINO_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 2500),
        media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/learn")
@limiter.limit("10/minute")
async def learn(request: Request):
    body = await request.json()
    result = llm(LEARN_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1500)
    return JSONResponse({"result": result})

@app.post("/api/learn/stream")
@limiter.limit("10/minute")
async def learn_stream(request: Request):
    body = await request.json()
    return StreamingResponse(
        llm_stream(LEARN_PROMPT, body.get("history", []) + [{"role": "user", "content": body.get("prompt", "")}], 1500),
        media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/breadboard")
@limiter.limit("5/minute")
async def generate_breadboard(request: Request):
    body = await request.json()
    raw = llm(BREADBOARD_PROMPT, body.get("history", []) + [{"role": "user", "content": "Schema: " + json.dumps(body.get("schema",{}))}], 1500)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m: return JSONResponse({"error":"Could not parse breadboard JSON","raw":raw}, status_code=500)
    return JSONResponse({"breadboard": json.loads(m.group())})

@app.post("/api/simulate")
async def simulate_circuit(request: Request):
    body = await request.json()
    raw = llm(SIMULATION_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1500)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m: return JSONResponse({"error":"Could not parse simulation JSON"}, status_code=500)
    return JSONResponse({"simulation": json.loads(m.group())})

@app.post("/api/bom")
@limiter.limit("10/minute")
async def generate_bom(request: Request):
    body = await request.json()
    raw = llm(BOM_PROMPT, body.get("history",[])+[{"role":"user","content":body.get("prompt","")}], 1500)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m: return JSONResponse({"error":"Could not parse BOM JSON"}, status_code=500)
    return JSONResponse({"bom": json.loads(m.group())})

@app.post("/api/save-circuit")
async def save_circuit(request: Request):
    if not supabase: return JSONResponse({"error":"Database not configured"}, status_code=500)
    body = await request.json()
    name = body.get("name","Untitled Circuit").strip() or "Untitled Circuit"
    device_id = body.get("device_id", "unknown")
    saved_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    tech = {k: body.get(k) for k in ("schematic_image","schematic_description","components","simulation","arduino_code","bom")}
    tech["device_id"] = device_id
    
    try:
        data = {
            "name": name,
            "saved_at": saved_at,
            "data": tech,
            "is_public": 1 if body.get("is_public") else 0,
            "upvotes": 0
        }
        res = supabase.table("circuits").insert(data).execute()
        return JSONResponse({"id": str(res.data[0]["id"]), "name": name})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/list-circuits")
async def list_circuits(device_id: str = None):
    if not supabase: return JSONResponse({"circuits": []})
    try:
        query = supabase.table("circuits").select("id,name,saved_at")
        if device_id:
            query = query.eq("data->>device_id", device_id)
        res = query.order("id", desc=True).limit(50).execute()
        return JSONResponse({"circuits": [{"id": str(r["id"]), "name": r["name"], "saved_at": r["saved_at"]} for r in res.data]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/load-circuit/{cid}")
async def load_circuit(cid: str):
    if not supabase: return JSONResponse({"error":"Database not configured"}, status_code=404)
    try:
        res = supabase.table("circuits").select("name,saved_at,data").eq("id", cid).execute()
        if not res.data: return JSONResponse({"error":"Not found"},status_code=404)
        row = res.data[0]
        data = row["data"]
        data["name"] = row["name"]
        data["saved_at"] = row["saved_at"]
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# gallery endpoint moved below with upvote support

@app.post("/api/export-kicad")
async def export_kicad(request: Request):
    body = await request.json()
    name = body.get("name","Circuit"); components = body.get("components",[])
    type_map = {"resistor":"R","capacitor":"C","led":"LED","battery":"Battery",
                "diode":"D","transistor":"Q","inductor":"L","switch":"SW","mosfet":"Q","op_amp":"U"}
    kicad = f'(kicad_sch (version 20230121) (generator "circuit_copilot")\n  (paper "A4")\n'
    for i, c in enumerate(components):
        ref = c.get("label",f"U{i+1}"); val = c.get("value","?")
        sym = type_map.get(c.get("type","resistor"),"R")
        x, y = 50 + (i % 6)*50, 50 + (i//6)*50
        kicad += f'  (symbol (lib_id "Device:{sym}") (at {x} {y} 0)\n'
        kicad += f'    (property "Reference" "{ref}" (id 0) (at {x} {y-7} 0))\n'
        kicad += f'    (property "Value" "{val}" (id 1) (at {x} {y+7} 0)) )\n'
    kicad += ')'
    return JSONResponse({"kicad_sch": kicad})

@app.post("/api/export-pdf")
async def export_pdf(request: Request):
    data = await request.json()
    pdf_bytes = generate_pdf(data)
    fname = data.get("project_name","circuit_report").replace(" ","_")+".pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition":f"attachment; filename={fname}"})

@app.websocket("/ws/{cid}")
async def websocket_endpoint(websocket: WebSocket, cid: str):
    await manager.connect(websocket, cid)
    try:
        while True:
            await manager.broadcast(await websocket.receive_text(), cid, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, cid)

@app.get("/", response_class=HTMLResponse)
async def landing():
    with open("static/landing.html", encoding="utf-8") as f: return f.read()

@app.get("/app", response_class=HTMLResponse)
async def main_app():
    with open("static/index.html", encoding="utf-8") as f: return f.read()

@app.get("/sw.js")
async def serve_sw():
    return FileResponse("static/sw.js", media_type="application/javascript")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/api/upvote/{cid}")
async def upvote_circuit(cid: str):
    """Increment upvote count for a circuit."""
    if not supabase: return JSONResponse({"error":"Database not configured"}, status_code=500)
    try:
        res = supabase.table("circuits").select("upvotes").eq("id", cid).execute()
        if not res.data: return JSONResponse({"error": "Not found"}, status_code=404)
        
        current_upvotes = res.data[0].get("upvotes", 0) or 0
        new_upvotes = current_upvotes + 1
        
        upd = supabase.table("circuits").update({"upvotes": new_upvotes}).eq("id", cid).execute()
        return JSONResponse({"id": cid, "upvotes": new_upvotes})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/gallery")
async def get_gallery():
    if not supabase: return JSONResponse({"gallery": []})
    try:
        res = supabase.table("circuits").select("id,name,saved_at,data,upvotes").eq("is_public", 1).order("upvotes", desc=True).order("id", desc=True).limit(30).execute()
        return JSONResponse({"gallery": [{
            "id": str(r["id"]),
            "name": r["name"],
            "saved_at": r["saved_at"],
            "image": r["data"].get("schematic_image"),
            "description": r["data"].get("schematic_description", ""),
            "upvotes": r["upvotes"] or 0
        } for r in res.data]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)