---
title: Circuit Copilot
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI-powered circuit design assistant. Describe circuits in plain English → get schematics, simulations, BOM, Arduino code, and more instantly.
---

# ⚡ Circuit Copilot v4.2

AI-powered circuit design assistant. Describe circuits in plain English → get schematics, simulations, BOM, Arduino code, and more instantly.

## 🚀 Features

### Core
- **Voice-to-Circuit:** Speak your circuit description naturally (hands-free Iron Man mode).
- **Schematic Generation:** Create interactive SVG schematics from natural language prompts.
- **Vision Support:** Upload an image of a circuit — AI identifies and digitizes it.
- **Interactive Simulations:** DC operating point analysis with animated current flow.
- **Hardware Bridge (WebSerial):** Flash generated code to Arduino directly from the browser + live Serial Monitor.
- **AI Breadboard Router:** Generate and visualize realistic breadboard wiring layouts.
- **Arduino Code & BOM:** Instantly generate microcontroller code and Bill of Materials.
- **Learn & Quiz Modes:** Electronics concepts + interactive quizzes with three difficulty levels.
- **Template Library:** Browse and load battle-tested circuit templates.
- **Calculators:** Ohm's Law, LED Resistor, and 555 Timer calculators built-in.
- **PDF Export:** Full circuit report — schematic, BOM, simulation, Arduino code — in one click.

### v4.1 New — What's Improved

| # | Feature | Description |
|---|---------|-------------|
| 1 | ⚡ Faster Model | Switched to `llama-3.3-70b-specdec` — 2-3× faster via speculative decoding |
| 2 | 🐛 Bug Fix | Fixed truncated `/api/learn/stream` route that could crash the server |
| 3 | 🐛 Bug Fix | Fixed missing `FileResponse` import causing `/api/export-kicad` `NameError` |
| 4 | 🔴 Rate Limit Countdown | 429 responses include `retry_after` seconds; UI shows an animated countdown banner |
| 5 | 📲 QR Code Share | Share button now opens a scannable QR code + copy link modal |
| 6 | 🔊 Explain This Circuit | New "Explain" button reads the circuit description aloud via browser TTS |
| 7 | ⚠️ Safety Banner | Auto-detects unsafe circuits (LED without resistor, excessive current, high voltage) |
| 8 | ◀▶ Prompt History | Back/forward navigation through last 20 prompts (`Alt+←` / `Alt+→`) |
| 9 | ♻ Auto-Restore | Last generated circuit is persisted to `localStorage` and restored on page reload |
| 10 | 📱 Mobile Tabs | Tab bar is now horizontally scrollable on small screens |

## 🛠️ Architecture

- **Backend:** FastAPI + Groq LLaMA 3.3 70B Specdec
- **Frontend:** Single-file HTML/CSS/JS with SVG schematic renderer
- **Database:** Supabase PostgreSQL (Community Gallery + saved circuits)
- **Rate Limiting:** `slowapi` with custom JSON 429 responses including `retry_after`
- **Realtime:** WebSocket-based collaboration per circuit session
- **PWA:** Service worker, offline support, installable

## ⚙️ Environment Variables

Set these in Space Secrets or your `.env` file before running:
- `GROQ_API_KEY`: Required for AI content generation.
- `SUPABASE_URL`: Required for saving circuits and the Community Gallery.
- `SUPABASE_KEY`: Required for database authentication.

*(If Supabase credentials are not provided, the application gracefully degrades and disables cloud-saving features without crashing.)*

## 🖥️ Running Locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here
uvicorn app:app --reload --port 7860
```

Then open [http://localhost:7860](http://localhost:7860).
