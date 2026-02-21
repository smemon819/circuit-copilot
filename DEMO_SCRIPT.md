# ⚡ Circuit Copilot — Competition Demo Script
## Estimated time: 5–7 minutes

---

## 🎯 OPENING (30 seconds)
**Say:**
> "How many of you have ever tried to build a circuit and had no idea where to start?
> Maybe you burned an LED, or your Arduino kept resetting, or you had no idea which components to buy.
> We built Circuit Copilot to fix exactly that — it's an AI assistant that takes your plain English description and turns it into a complete circuit design in seconds."

**Action:** The landing page should be open on screen — the animated PCB traces make a great visual.

---

## 🔌 DEMO 1 — Schematic Generation (60 seconds)
**Say:**
> "Let's start with the core feature. I'm going to describe a circuit in plain English."

**Action:** Click **Launch App** → go to the **Schematic tab**

**Type or speak:** `"LED circuit with a 220 ohm resistor and a 9V battery"`

**While it loads, say:**
> "No knowledge of circuit symbols required. No EDA software. Just describe what you want."

**When result appears, say:**
> "There's our schematic. Notice it also shows the difficulty level — Beginner — and the use case.
> And here at the bottom — it's automatically generated a link to Falstad, a real circuit simulator,
> pre-loaded with our components."

---

## 📊 DEMO 2 — Simulation (60 seconds)
**Say:**
> "Now let's actually simulate this circuit — see what the real voltages and currents are."

**Action:** Click the **Simulate tab**

**Type:** `"9V battery, 220 ohm resistor, red LED in series"`

**When result appears, say:**
> "Look at this — we get the actual DC operating point. Node voltages at each point in the circuit,
> power dissipation for every component, and branch currents.
> And this animation — the green dots — show actual current flowing, proportional to the real current value.
> If there are any issues, like the LED current being too high, it flags them as warnings right here."

---

## 〰️ DEMO 3 — Waveform Visualizer (30 seconds)
**Say:**
> "For AC circuits, we have a built-in oscilloscope visualizer."

**Action:** Click **Waveform tab** → change type to **Square** → drag frequency slider

**Say:**
> "You can generate sine, square, triangle, sawtooth, and PWM waveforms.
> Change the frequency, amplitude, duty cycle — it updates live.
> You can then ask the AI what happens if you pass this signal through a filter."

---

## 🧾 DEMO 4 — Bill of Materials (45 seconds)
**Say:**
> "One of the most practical features — especially if you're actually going to build this —
> is the Bill of Materials generator."

**Action:** Click **BOM tab**

**Type:** `"555 timer LED blinker on a breadboard"`

**When result appears, say:**
> "Exact part numbers, specs, unit costs, total cost, and where to buy — DigiKey, Mouser, Amazon.
> One click exports this as a CSV you can send straight to your supplier.
> This alone would save a beginner hours of research."

---

## 💻 DEMO 5 — Arduino Code (45 seconds)
**Say:**
> "For microcontroller projects, we generate complete, upload-ready Arduino code."

**Action:** Click **Arduino tab**

**Type or speak:** `"Blink an LED on pin 13 every 500ms, and when a button on pin 2 is pressed, speed it up to 100ms"`

**When result appears, say:**
> "Complete .ino file — pin definitions, setup, loop, comments on every block.
> Hit the download button and it goes straight into the Arduino IDE."

---

## 🎯 DEMO 6 — Quiz Mode (30 seconds, optional if time allows)
**Say:**
> "We also built a learning mode for students. The quiz has three difficulty levels."

**Action:** Click **Quiz tab** → Click **New Question** (Intermediate level)

**Let the audience read the question → click an answer**

**Say:**
> "Each answer comes with a full explanation with the actual formula and numbers.
> It's not just right/wrong — it teaches you why."

---

## 📄 DEMO 7 — PDF Export (20 seconds)
**Say:**
> "Finally — everything we just generated can be exported as a single PDF report."

**Action:** Type a project name like `"My LED Circuit"` → click **📄 PDF** in the header

**Say:**
> "Schematic image, component table, simulation results, BOM, and Arduino code — all in one document.
> Perfect for project documentation, lab reports, or presenting to a client."

---

## 🏁 CLOSING (30 seconds)
**Say:**
> "Circuit Copilot turns a blank screen into a complete, documented circuit design in under 5 minutes.
> It's powered by Groq's LLaMA 3.3 70B — completely free, deployed on HuggingFace.
> Our vision is to make electronics accessible to anyone — whether you're a student, a maker, or
> an engineer who just needs a quick prototype.
>
> The entire stack is open source. Thank you."

---

## 💡 TIPS FOR THE PRESENTATION

**If something fails:**
- If the API errors: *"Groq's free tier has rate limits — in production we'd handle this with a queue"*
- If the schematic looks off: *"The rendering is a visual approximation — the Falstad link gives a fully accurate simulation"*

**Likely judge questions & answers:**

| Question | Answer |
|---|---|
| "How accurate is the simulation?" | "It's an LLM-based DC approximation. For production use, we'd integrate a SPICE engine like PySpice for full accuracy." |
| "What's the cost to run this?" | "Zero — Groq's free tier, HuggingFace free hosting. For scale, Groq Pro is ~$20/month." |
| "Can it handle complex circuits?" | "Yes — we've tested up to 15-component circuits. The more detail in the prompt, the better the output." |
| "What would you build next?" | "PCB export in KiCad format, a component database integration, and multi-user collaboration." |

---

## 🎤 VOICE INPUT MOMENT (Optional wow factor)
At any point during the demo, press the 🎤 mic button and **speak** your circuit description out loud.
This always gets a reaction from the audience and shows the accessibility angle of the project.
