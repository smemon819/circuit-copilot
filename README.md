---
title: Circuit Copilot
emoji: ⚡
colorFrom: blue
colorTo: cyan
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI circuit design — schematics, simulation, Arduino code & BOM
---

# ⚡ Circuit Copilot v3.0

AI-powered circuit design assistant. Describe circuits in plain English → get schematics, simulations, BOM, Arduino code, and more instantly.

## 🚀 Features
- **Voice-to-Circuit:** Speak your circuit description naturally and watch it build itself instantaneously (hands-free Iron Man mode).
- **Schematic Generation:** Create interactive schematics from natural language prompts.
- **Vision Support:** Upload an image of a circuit to have it analyzed and digitized.
- **Interactive Simulations:** Real-time DC circuit simulations powered by Falstad.
- **AI Breadboard Router:** Generate and visualize realistic breadboard wiring layouts mapped to a smart physical grid.
- **Arduino Code & BOM:** Instantly generate microcontroller code and Bill of Materials.
- **Learn & Quiz Modes:** Learn electronics concepts and test your knowledge with interactive quizzes.
- **Template Library:** Browse and load battle-tested circuit templates.
- **Calculators:** Ohm's Law, LED Resistor, and 555 Timer calculators built-in.
- **Cloud Saving & Community:** Save circuits to the cloud and browse the Community Gallery.

## 🛠️ Architecture Updates (v3.0)
- **Supabase Integration:** User circuits and the Community Gallery are now stored persistently in a Supabase PostgreSQL database instead of a local SQLite file.
- **API Rate Limiting:** The backend is protected by `slowapi` to prevent abuse of the AI LLM pipelines.
- **Multi-User Isolation:** Saved circuits are filtered using locally-generated device fingerprints stored in Supabase `jsonb` columns, ensuring a private workspace without forced user registration.
- **Mega Menu Navigation:** A polished "More Tools" dropdown cleans up the UI and improves mobile responsiveness.

## ⚙️ Environment Variables 
Set these in Space Secrets or your `.env` file before running:
- `GROQ_API_KEY`: Required for AI content generation (Llama 3.3).
- `SUPABASE_URL`: Required for saving circuits and the Community Gallery.
- `SUPABASE_KEY`: Required for database authentication.

*(Note: If Supabase credentials are not provided, the application gracefully degrades and disables cloud-saving features without crashing.)*
