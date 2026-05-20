# ⚡ Antigravity Bulk Image Scraper & Beat-Synced Video Engine

An advanced, AI-powered industrial-grade image collection and beat-synced video generation suite, equipped with stealth-focused multi-source scraping, resilient downloader pipelines, and zero-rate-limit AI orchestration.

---

## 🌟 Core Features

### 🎬 1. AI Beat-Synced Video Editor (`cli_editor.py`)
Assemble highly customized vertical video edits dynamically synchronized to the rhythmic beats and intensity drops of any music track.
* **Dynamic 6 Sub-Query Loop:** Generates a diverse list of 6 visual sub-queries via AI (e.g. for topic "environment", queries `"lush misty redwood forest vertical"`, `"deep ocean coral reef landscape"`, etc.) ensuring extreme visual asset variety.
* **Aesthetic Keyword Preservation:** The dynamic topic pre-processor preserves rich visual genres (like *vaporwave*, *cyberpunk*, *dreamcore*, *glitchcore*, *surreal*) during autocorrection, keeping the creative intent fully intact.
* **High-Variety Image Collection:** Securely scrapes and downloads dozens of unique, non-repeating vertical images to map perfectly to rapid transition drops.
* **Precision Rhythm & Beat Analysis:** Parses the audio frequency waves of any `.mp3` or `.wav` track, accurately locating intensity peaks (drops) and sync points automatically.
* **Dynamic Zoom & Motion Transitions:** Alternates camera panning and kinetic zoom scales on consecutive transitions, overlaying brief visual flashes on every beat drop for a premium production feel.

### 🧠 2. Smarter API Key Preservation (95% Reduction!)
* **Single-Call AI Orchestration:** Bypassed the highly rate-limited per-image auditing loop. The engine now triggers **exactly 1 Gemini API call** at the very beginning of the run to generate sub-queries and metadata specifications.
* **Instant Local Auditing:** Evaluates, shuffles, and filters hundreds of scraped image candidates completely locally and instantaneously using dynamically generated visual keywords.
* **Key-Rotation & Failover:** Integrates seamlessly with multi-key structures, rotating fallback models automatically to safeguard execution.

### 🛡️ 3. Resilient Multi-Source Stealth Scraper
* **Stealth Scraper Architecture:** Uses undetected chromedrivers, randomized scrolling, human behavior simulation, mouse gestures, navigator masking, and user-agent rotations to bypass robust CDN/bot blockades.
* **Extensive Engine Queries:** Searches concurrently across **Google Images**, **Bing Images**, **Pexels Stock**, **DuckDuckGo**, and **Yahoo**.
* **Pexels Tag Optimization:** Automatically strips layout words (like *vertical*, *wallpaper*) and isolates the first 2-3 core nouns to bypass Pexels' strict tag search boundaries.
* **Self-Healing Search Fallbacks:** If a descriptive sub-query returns too few candidates, the scraper dynamically simplifies the phrase to its core terms and retries secondary engines instantly.

### 📥 4. High-Performance Downloader Pipeline
* **Asynchronous Concurrency:** Employs concurrent `aiohttp` streams to download dozens of images concurrently in seconds.
* **Strict Blacklisting:** Bypasses domains that actively restrict direct scrapers (e.g. Pinterest/pinimg, fineartamerica) to speed up download cycles.
* **URL Deduplication:** Deduplicates identical search engine results pre-download to prevent concurrent file write collisions and `.tmp` corruption.
* **Dual Fallback Recovery:** If the async request encounters a `403 Forbidden` block, it automatically triggers a synchronous `requests` fallback, followed by a native macOS subprocess `curl` failover.
* **Fail-Safe Aborts (`curl -f`):** Integrated native curl failure returns to prevent hotlink blocks from writing HTML error logs to disk.

---

## 🛠️ Tech Stack

* **Video Processing:** MoviePy, NumPy, FFmpeg, OpenCV
* **AI Orchestration:** Gemini API Manager, LLM Router (Fallback to NVIDIA, Groq)
* **Scraping Pipeline:** Undetected Chromedriver, AioHTTP, Requests, Selenium
* **Verification:** Perceptual Hashing (`imagehash`), Laplacian Variance Blur Filter, Pillow

---

## 🚀 How to Run the Video Creator

Execute the CLI editor with any topic, song index, and target duration to generate beat-synced videos:

```bash
python3 cli_editor.py --song 13 --topic "liminal space nostalgia" --hook n --duration 11
```

### Options:
* `--song`: The numerical index of the music track from the `music/` directory (displays a list if omitted).
* `--topic`: The search topic or visual concept.
* `--hook`: Set to `y` or `n` to toggle the introductory title/mystery hook phase (includes dynamic text layout overlay).
* `--duration`: Target duration of the main edit in seconds.

---

## 📂 Project Structure

```text
bulk_images/
├── backend/
│   ├── app/
│   │   ├── modules/
│   │   │   ├── scraper.py       # Selenium/Undetected Chromedriver Scraper
│   │   │   ├── simple_scraper.py# Universal multi-engine search scraper
│   │   │   ├── downloader.py    # Async downloader, domains blacklist, curls
│   │   │   └── stealth.py       # Anti-bot detection masking logic
│   │   └── main.py              # FastAPI Web Entry
├── music/                       # Rhythmic soundtracks & audio tracks
├── datasets/                    # Local storage for scraped visual assets
├── outputs/                     # Rendered beat-synced vertical videos (.mp4)
├── cli_editor.py                # Beat-synced master creator engine CLI
├── llm_router.py                # LLM key management and routing failover
└── start.sh                     # Startup script
```
