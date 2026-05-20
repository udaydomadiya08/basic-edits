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
            import re
            url_hash = hashlib.md5(url.encode()).hexdigest()
            filename = f"{url_hash}.jpg"
            filepath = os.path.join(query_folder, filename)

            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
            ]
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive"
            }
            
            content = None
            
            # Try async aiohttp download first
            try:
                is_encoded = False
                if "%" in url and re.search(r"%[0-9a-fA-F]{2}", url):
                    is_encoded = True
                yarl_url = yarl.URL(url, encoded=is_encoded)
                
                async with session.get(yarl_url, timeout=12, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                    else:
                        raise Exception(f"HTTP Status {response.status}")
            except Exception as e:
                # Synchronous Requests Fallback
                print(f"🔄 Async download failed for {url} ({e}). Trying synchronous requests fallback...")
                try:
                    import requests
                    def sync_download():
                        # Disable SSL verification warning since verify=False is used for maximum download success
                        import urllib3
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        return requests.get(url, headers=headers, timeout=10, verify=False)
                    
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, sync_download)
                    if res.status_code == 200:
                        content = res.content
                        print(f"✨ Synchronous fallback SUCCESS for {url}")
                    else:
                        raise Exception(f"Requests returned status {res.status_code}")
                except Exception as re_err:
                    # Native Curl Fallback (Ultimate Weapon)
                    print(f"🔄 Requests fallback failed for {url} ({re_err}). Trying native curl fallback...")
                    try:
                        import subprocess
                        temp_file = filepath + ".tmp"
                        cmd = [
                            "curl",
                            "-f",
                            "-L",
                            "-s",
                            "-k",
                            "--max-time", "10",
                            "-H", f"User-Agent: {headers['User-Agent']}",
                            "-H", "Accept: image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                            "-H", "Sec-Fetch-Dest: image",
                            "-H", "Sec-Fetch-Mode: no-cors",
                            "-H", "Sec-Fetch-Site: cross-site",
                            "-o", temp_file,
                            url
                        ]
                        
                        def run_curl():
                            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            
                        loop = asyncio.get_event_loop()
                        sub_res = await loop.run_in_executor(None, run_curl)
                        if sub_res.returncode == 0 and os.path.exists(temp_file) and os.path.getsize(temp_file) > 100:
                            with open(temp_file, "rb") as f:
                                content = f.read()
                            try:
                                os.remove(temp_file)
                            except:
                                pass
                            print(f"✨ Curl fallback SUCCESS for {url}")
                        else:
                            print(f"❌ Curl fallback failed for {url} (Returncode: {sub_res.returncode})")
                            try:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                            except:
                                pass
                    except Exception as curl_err:
                        print(f"❌ Curl fallback exception for {url}: {curl_err}")
            
            if not content:
                return None
                
            try:
                img = Image.open(io.BytesIO(content))
                img.verify()
                img = Image.open(io.BytesIO(content)) # Re-open for size check
            except Exception as img_err:
                print(f"❌ Corrupted image from {url}: {img_err}")
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
                
            img.save(filepath, "JPEG", quality=95)
            
            return {"url": url, "path": filepath, "hash": url_hash}

    async def bulk_download(self, urls, query):
        # Deduplicate candidate URLs to prevent parallel write collisions
        urls = list(dict.fromkeys(urls))
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

