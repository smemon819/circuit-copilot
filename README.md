# ⚡ Circuit Copilot

**AI-powered circuit design assistant** — Describe circuits in plain English and get schematics, simulations, Arduino code, and BOM instantly.

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Powered by Groq](https://img.shields.io/badge/Powered%20by-Groq%20LLaMA%203.3-orange.svg)](https://groq.com)

---

## 🚀 Features

| Feature | Description |
|---|---|
| 🔌 **Schematic Generation** | Describe a circuit in English → get a rendered schematic with Falstad simulation link |
| 📊 **DC Simulation** | Node voltages, branch currents, power dissipation with animated current flow |
| 〰️ **Waveform Generator** | Interactive oscilloscope with sine, square, triangle, sawtooth, PWM waveforms |
| 🧾 **Bill of Materials** | Part numbers, costs, suppliers (DigiKey, Mouser, Amazon) — export as CSV |
| 🧩 **Component Advisor** | AI recommends exact parts with specs and where to buy |
| 🔍 **Circuit Debugger** | Paste your broken circuit → get step-by-step diagnosis |
| 💻 **Arduino Code Gen** | Complete upload-ready `.ino` files with comments and pin definitions |
| 📚 **Learn Mode** | Explain any electronics concept with analogies, formulas, and experiments |
| 🎯 **Quiz Mode** | 3 difficulty levels with explanations, scoring, streaks, and persistent leaderboard |
| 📄 **PDF Export** | One-click report with schematic, simulation, BOM, and code |
| 🎤 **Voice Input** | Speak your circuit description — no typing required |
| 🌗 **Dark/Light Mode** | Toggle between sleek dark and clean light themes |
| ⌨️ **Keyboard Shortcuts** | Power-user shortcuts for fast navigation |
| 📋 **Circuit Templates** | Pre-built circuits you can load with one click |

---

## 🛠️ Tech Stack

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://uvicorn.org/)
- **AI Model:** [Groq](https://groq.com/) LLaMA 3.3 70B (free tier)
- **Schematic Rendering:** [SchemDraw](https://schemdraw.readthedocs.io/) + Matplotlib
- **PDF Generation:** [ReportLab](https://www.reportlab.com/)
- **Circuit Simulation:** [Falstad](https://falstad.com/circuit/) (embedded)
- **Frontend:** Vanilla HTML/CSS/JS with [Marked.js](https://marked.js.org/) for markdown

---

## ⚡ Quick Start

### Prerequisites
- Python 3.11+
- [Groq API Key](https://console.groq.com/) (free)

### Local Development

```bash
# Clone the repo
git clone https://github.com/smemon819/circuit-copilot.git
cd circuit-copilot

# Install dependencies
pip install -r requirements.txt

# Set your API key
export GROQ_API_KEY="your-groq-api-key"

# Run the server
uvicorn app:app --reload --port 7860

# Open http://localhost:7860
```

### Deploy to Hugging Face Spaces

1. Create a new Space with **Docker** SDK
2. Add `GROQ_API_KEY` as a Repository Secret
3. Push this repo to the Space
4. Wait for build → your app is live!

---

## 📁 Project Structure

```
circuit-copilot/
├── app.py              # FastAPI backend (API routes, LLM, rendering)
├── requirements.txt    # Python dependencies
├── Dockerfile          # HuggingFace Spaces deployment
├── DEMO_SCRIPT.md      # Competition demo walkthrough
├── LICENSE             # MIT License
└── static/
    ├── index.html      # Main app (full UI)
    └── landing.html    # Landing page with PCB animation
```

---

## 🎤 Demo

> "How many of you have ever tried to build a circuit and had no idea where to start?"

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for a complete 5–7 minute competition demo walkthrough.

---

## 📝 License

[MIT](LICENSE) — Free and open source.

---

**Built with ❤️ and AI** · Powered by Groq LLaMA 3.3 70B
