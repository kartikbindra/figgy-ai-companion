# 💀 Figgy — The Handheld AI Companion

Figgy is an unhinged, witty, handheld AI companion designed to feel like an entertaining, intelligent, and context-aware friend.

It combines local LLM inference, five dynamic personality modes, persistent multi-tier SQLite memory, real-time token streaming, and an ESP32-integrated physical hardware architecture.

---

## ⚡ Quick Start

### 1. Setup Environment
```powershell
# Create & activate virtual environment (already set up in .venv)
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r backend/requirements.txt

# Pull the default abliterated model in Ollama
ollama pull huihui_ai/qwen3-abliterated
```

### 2. Start the Backend Server
```powershell
cd backend
..\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be live at: **`http://localhost:8000/docs`**

### 3. Start the Interactive Terminal Chat
In a separate terminal window:
```powershell
python client/cli.py
```

### 4. Or Open the Web Dashboard
Open `client/web/index.html` in your web browser. You can:
- Chat with real-time streaming tokens
- Toggle all 5 personalities with one click
- Adjust fusion sliders and intensity in real time
- View the simulated ESP32 RGB LED & haptic feedback
- Inspect persistent memories saved in SQLite

---

## 🎭 The 5 Personalities

1. **The Dark Comedian (`dark_comedian`) [DEFAULT]**: Roast-style observational comedy, rapid comebacks, sarcastic wit, and absurd analogies.
2. **The Existentialist (`existentialist`)**: Dostoevsky-inspired philosophical depth, introspective questions on suffering, morality, and ambition.
3. **The First-Principles Thinker (`first_principles`)**: Physics-first logic, engineering mindset, clear separation of verifiable facts from hypotheses.
4. **The Hopeless Romantic (`ted_mosby`)**: Affectionate, earnest, finds destiny in coincidences, warm and dramatic storytelling.
5. **The Unhinged Villain (`homelander`)**: Theatrical megalomania, smiling superiority, world-destroyer theatrics in playful fictional entertainment.

### Real-Time Switching & Fusion
- **Single Switch**: `POST /v1/persona` with `{"mode": "single", "persona": "homelander", "intensity": 0.9}`
- **Weighted Fusion**: `POST /v1/persona` with `{"mode": "fusion", "fusion_weights": {"dark_comedian": 0.6, "existentialist": 0.4}}`
- **Contextual Mood Adaptation**: Detects user distress, sadness, or exhaustion and dials back roast severity automatically.

---

## 🧠 Multi-Tier SQLite Memory

- **Working Memory**: Sliding window of recent conversation turns.
- **Semantic Memory**: Automatic extraction of user facts (name, hobbies, favorite foods, tech stack, preferences).
- **Episodic Memory**: Automatic compaction of older conversations into milestone episodic summaries.
- **Inspect/Manage**: `GET /v1/memory` and `DELETE /v1/memory/{id}`.

---

## 🌐 Remote Access with Cloudflare Tunnel

When the ESP32 is away from your home PC (e.g. connected to your mobile phone hotspot):
See the complete guide in [docs/cloudflare_tunnel.md](docs/cloudflare_tunnel.md).

```powershell
cloudflared tunnel --url http://localhost:8000
```

---

## 🎙️ Voice Pipeline (TTS & STT)

- **Edge-TTS Neural Voice Synthesis**: Zero-GPU latency with 7 curated voices matched to personalities (`Guy`, `Ryan`, `Christopher`, `Eric`, `Roger`, `Ana`, `William`).
- **Faster-Whisper Speech-to-Text**: CPU-optimized `tiny.en` model running via `int8` quantization (~180ms latency) preserving 100% of GPU VRAM for LLM generation.
- **Audio Chat Endpoint**: `POST /v1/voice/chat` accepts recorded microphone audio, transcribes it, runs the Figgy persona LLM, and streams back synthesized audio.

---

## 🧪 Running Tests

```powershell
.\.venv\Scripts\pytest backend/tests/ -v
```
