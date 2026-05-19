import os
import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid

from .modules.simple_scraper import SimpleScraper
from .modules.downloader import ImageDownloader, ImageCleaner, ImageProcessor

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Bulk Image Scraper API")

# Ensure datasets directory exists
os.makedirs("datasets", exist_ok=True)
app.mount("/datasets", StaticFiles(directory="datasets"), name="datasets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for task status
tasks = {}

class ScrapingRequest(BaseModel):
    query: str
    limit: int
    engines: List[str] = ["bing", "yahoo", "duckduckgo"]
    resize: Optional[bool] = False
    clean_duplicates: Optional[bool] = True
    output_dir: Optional[str] = "datasets"

async def run_scraping_task(task_id: str, request: ScrapingRequest):
    tasks[task_id]["status"] = "scraping"
    all_urls = set()
    
    def log_cb(msg):
        tasks[task_id]["logs"].append(msg)

    # Scrape from multiple engines
    buffer_limit = int(request.limit * 1.5) # Fetch 50% more to ensure quality
    
    ss = SimpleScraper(log_callback=log_cb)
    
    # We now exclusively use high-yield "Simple" scrapers to avoid bot detection
    for engine in request.engines:
        # Priority 1: Bing
        if engine == "bing":
            urls = ss.search_bing(request.query, buffer_limit)
            all_urls.update(urls)
            
        # Priority 2: Yahoo
        elif engine == "yahoo":
            urls = ss.search_yahoo(request.query, buffer_limit)
            all_urls.update(urls)
            
        # Priority 3: DuckDuckGo
        elif engine == "duckduckgo":
            urls = ss.search_duckduckgo(request.query, buffer_limit)
            all_urls.update(urls)
            
        # Priority 4: Pexels
        elif engine == "unsplash" or engine == "pexels":
            urls = ss.search_pexels(request.query, buffer_limit)
            all_urls.update(urls)

    tasks[task_id]["status"] = "downloading"
    tasks[task_id]["total_urls"] = len(all_urls)
    
    downloader = ImageDownloader(request.output_dir)
    downloaded_images = await downloader.bulk_download(list(all_urls), request.query)
    
    tasks[task_id]["downloaded_count"] = len(downloaded_images)
    tasks[task_id]["logs"].append(f"Successfully downloaded {len(downloaded_images)} images")

    # Cleaning and Processing
    final_images = []
    if request.clean_duplicates or request.resize:
        tasks[task_id]["status"] = "processing"
        hashes = set()
        for img_info in downloaded_images:
            path = img_info["path"]
            
            # Relevance Check
            relevant, reason = ImageCleaner.is_relevant(path, request.query)
            if not relevant:
                if os.path.exists(path): os.remove(path)
                tasks[task_id]["logs"].append(f"Filtered low-relevance image ({reason}): {path}")
                continue

            if request.clean_duplicates:
                p_hash = ImageCleaner.get_pixel_hash(path)
                if p_hash in hashes:
                    if os.path.exists(path): os.remove(path)
                    tasks[task_id]["logs"].append(f"Removed duplicate: {path}")
                    continue
                hashes.add(p_hash)
            
            if request.resize:
                ImageProcessor.resize_image(path)
            
            final_images.append(img_info)
            # Live Preview Update
            if "images" not in tasks[task_id]: tasks[task_id]["images"] = []
            tasks[task_id]["images"].append(path.replace("\\", "/"))

            if len(final_images) >= request.limit:
                break
    else:
        final_images = downloaded_images[:request.limit]
        tasks[task_id]["images"] = [img["path"].replace("\\", "/") for img in final_images]
        
    # Save Metadata
    from .modules.metadata import MetadataManager
    mm = MetadataManager(request.output_dir)
    mm.save_metadata(request.query, final_images)
    tasks[task_id]["logs"].append(f"Metadata saved for {len(final_images)} images")
        
    tasks[task_id]["status"] = "completed"
    tasks[task_id]["images"] = [img["path"].replace("\\", "/") for img in final_images]
    tasks[task_id]["logs"].append("Task completed successfully")

@app.post("/scrape")
async def start_scraping(request: ScrapingRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "id": task_id,
        "query": request.query,
        "status": "pending",
        "downloaded_count": 0,
        "total_urls": 0,
        "logs": [],
    }
    background_tasks.add_task(run_scraping_task, task_id, request)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/tasks")
async def list_tasks():
    return list(tasks.values())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
