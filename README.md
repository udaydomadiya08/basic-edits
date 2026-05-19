# Antigravity Bulk Image Scraper

An advanced, AI-powered industrial-grade image dataset collection system with stealth-focused scraping behavior and a premium dashboard.

## 🚀 Features

### 1. Advanced Stealth Architecture
- **Undetected Chromedriver**: Bypasses most bot detection systems.
- **Human Behavior Simulation**: Randomized scrolling, mouse movements, and delays.
- **Fingerprint Protection**: Randomized viewports and User-Agent rotation.
- **Navigator Masking**: Hides automation flags.

### 2. Multi-Source Scraping
- Support for **Google Images**, **Bing Images**, and extensible architecture for others.
- Dynamic pagination and infinite scroll handling.

### 3. High-Performance Downloader
- **Asynchronous Pipeline**: Uses `aiohttp` and `asyncio` for parallel downloads.
- **Verification**: Automatic detection and removal of corrupted or small images.
- **Retries**: Built-in retry logic for failed requests.

### 4. Dataset Cleaning & Processing
- **Duplicate Removal**: Uses Perceptual Hashing (`imagehash`) to find and remove visually identical images.
- **Blur Detection**: Uses OpenCV Laplacian variance to filter out low-quality/blurry images.
- **Auto-Processing**: Optional resizing and format conversion.

### 5. Premium Dashboard
- **Real-time Monitoring**: Progress bars and live status updates.
- **System Logs**: Console-style live logs of the scraping process.
- **History**: Keep track of previous datasets collected.

---

## 🛠 Tech Stack

- **Backend**: Python (FastAPI, Selenium, undetected-chromedriver, OpenCV, Pillow)
- **Frontend**: React (Vite, TailwindCSS, Framer Motion, Lucide Icons)
- **Concurrency**: Asyncio, Multiprocessing

---

## 🚦 Getting Started

### Prerequisites
- Python 3.9+
- Node.js & npm
- Google Chrome installed

### Quick Start
1. Clone the repository.
2. Run the startup script:
   ```bash
   ./start.sh
   ```

---

## 📂 Project Structure

```text
bulk_images/
├── backend/
│   ├── app/
│   │   ├── modules/
│   │   │   ├── scraper.py   # Scraper engines
│   │   │   ├── stealth.py   # Anti-bot logic
│   │   │   ├── downloader.py # Download & Process
│   │   │   └── metadata.py  # CSV/JSON export
│   │   └── main.py          # FastAPI Entry
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Dashboard UI
│   │   └── index.css        # Styles & Glassmorphism
└── datasets/                # Collected images & metadata
```
