import os
import aiohttp
import asyncio
import hashlib
import random
import logging
from PIL import Image
import io
import cv2
import numpy as np
import yarl

logger = logging.getLogger(__name__)

class ImageDownloader:
    def __init__(self, output_dir, parallel_limit=8):
        self.output_dir = output_dir
        self.parallel_limit = parallel_limit
        self.semaphore = asyncio.Semaphore(parallel_limit)

    async def download_image(self, session, url, query_folder):
        async with self.semaphore:
            try:
                # Chameleon Headers: Rotated and realistic
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
                headers = {
                    "User-Agent": random.choice(user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/",
                    "DNT": "1"
                }
                # Prevent aiohttp from double-encoding pre-encoded URLs (which causes Wikipedia Status 400)
                yarl_url = yarl.URL(url, encoded=True)
                async with session.get(yarl_url, timeout=15, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        try:
                            img = Image.open(io.BytesIO(content))
                            img.verify()
                            img = Image.open(io.BytesIO(content)) # Re-open for size check
                        except:
                            print(f"❌ Corrupted image from {url}")
                            return None

                        width, height = img.size
                        if width < 50 or height < 50:
                            print(f"⚠️ Skipping tiny image ({width}x{height}) from {url}")
                            return None
                            
                        # Relaxed check: Only skip extremely wide panoramic images, allowing normal horizontal/square images to be center-cropped
                        if width > 2.2 * height:
                            print(f"⚠️ Skipping extremely wide panoramic image ({width}x{height}) from {url}")
                            return None

                        # Convert to RGB and save as High-Quality JPEG for 100% MoviePy compatibility
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                            
                        # Crop and resize to exactly 1080x1920 centered (fixed strict vertical dimension)
                        target_w, target_h = 1080, 1920
                        w, h = img.size
                        scale = max(target_w / w, target_h / h)
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        img = img.resize((new_w, new_h), Image.LANCZOS)
                        
                        left = int((new_w - target_w) / 2)
                        top = int((new_h - target_h) / 2)
                        right = left + target_w
                        bottom = top + target_h
                        img = img.crop((left, top, right, bottom))
                            
                        url_hash = hashlib.md5(url.encode()).hexdigest()
                        filename = f"{url_hash}.jpg"
                        filepath = os.path.join(query_folder, filename)
                        
                        img.save(filepath, "JPEG", quality=95)
                        
                        return {"url": url, "path": filepath, "hash": url_hash}
                    else:
                        print(f"❌ Download failed for {url} (Status: {response.status})")
                        return None
            except Exception as e:
                print(f"❌ Connection error for {url}: {e}")
            return None

    async def bulk_download(self, urls, query):
        query_folder = os.path.join(self.output_dir, query)
        os.makedirs(query_folder, exist_ok=True)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            tasks = [self.download_image(session, url, query_folder) for url in urls]
            results = await asyncio.gather(*tasks)
            valid_results = [r for r in results if r]
            print(f"✅ Bulk Download: Successfully saved {len(valid_results)}/{len(urls)} images.")
            return valid_results

class ImageCleaner:
    @staticmethod
    def get_pixel_hash(image_path):
        """A lighter alternative to imagehash for exact duplicate detection."""
        try:
            img = Image.open(image_path).convert('RGB')
            # Resize to a tiny thumb to catch 'near' duplicates without imagehash
            img = img.resize((32, 32), Image.LANCZOS)
            pixels = list(img.getdata())
            return hashlib.md5(str(pixels).encode()).hexdigest()
        except Exception as e:
            logger.error(f"PixelHash error: {e}")
            return None

    @staticmethod
    def is_relevant(image_path, query, image_url=None):
        """Heuristic check for relevance and quality."""
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            # 1. Size check: avoid tiny images
            if width < 200 or height < 200:
                return False, "Image too small"
            
            # 2. Aspect Ratio: avoid extremely narrow/wide images
            aspect_ratio = width / height
            if aspect_ratio > 3.0 or aspect_ratio < 0.3:
                return False, "Extreme aspect ratio"
            
            # 3. File size check
            file_size = os.path.getsize(image_path)
            if file_size < 5000: # 5KB
                return False, "File size too small"
                
            return True, "OK"
        except:
            return False, "Error processing image"

    @staticmethod
    def is_blurry(image_path, threshold=100.0):
        try:
            image = cv2.imread(image_path)
            if image is None: return False
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            fm = cv2.Laplacian(gray, cv2.CV_64F).var()
            return fm < threshold
        except Exception as e:
            logger.error(f"Blur detection error: {e}")
            return False

class ImageProcessor:
    @staticmethod
    def resize_image(image_path, target_size=(512, 512), maintain_aspect=True):
        try:
            img = Image.open(image_path)
            if maintain_aspect:
                img.thumbnail(target_size, Image.LANCZOS)
            else:
                img = img.resize(target_size, Image.LANCZOS)
            img.save(image_path)
            return True
        except:
            return False

