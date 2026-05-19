import requests
from bs4 import BeautifulSoup
import json
import logging
import re
import random

logger = logging.getLogger(__name__)

class SimpleScraper:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/"
        }

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        logger.info(message)

    def search_bing(self, query, limit, offset_start=1):
        # Add negative keywords to avoid news/event/text noise
        query += " -news -event -text -logo -watermark"
        self.log(f"Bing search for '{query}' (Offset: {offset_start})...")
        
        blacklist = ["thehindu.com", "starofmysore.com", "prokerala.com", "pinterest.com", "shutterstock.com", "istockphoto.com", "whatshot.in"]
        results = []
        try:
            offset = offset_start
            while len(results) < limit and offset < offset_start + limit * 6:
                url = f"https://www.bing.com/images/search?q={query}&first={offset}"
                res = requests.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                
                links = soup.find_all("a", class_="iusc")
                if not links: break
                
                for link in links:
                    if len(results) >= limit: break
                    m = link.get("m")
                    if m:
                        try:
                            m_data = json.loads(m)
                            murl = m_data.get("murl")
                            if murl:
                                # Blacklist Check
                                if any(domain in murl.lower() for domain in blacklist):
                                    continue
                                    
                                results.append({
                                    "url": murl,
                                    "title": m_data.get("t", ""),
                                    "description": m_data.get("s", "")
                                })
                        except: continue
                
                offset += len(links)
                if offset > offset_start + 300: break
        except Exception as e:
            self.log(f"Bing error: {e}")
        return results

    def search_duckduckgo(self, query, limit):
        # Add negative keywords to avoid news/event/text noise
        query += " -news -event -text -logo -watermark"
        self.log(f"DDG search for '{query}'...")
        
        blacklist = ["thehindu.com", "starofmysore.com", "prokerala.com", "pinterest.com", "shutterstock.com", "istockphoto.com", "whatshot.in"]
        results = []
        try:
            res = requests.get(f"https://duckduckgo.com/?q={query}", headers=self.headers)
            vqd_match = re.search(r"vqd='([^']+)'", res.text) or re.search(r'vqd="([^"]+)"', res.text)
            if vqd_match:
                vqd = vqd_match.group(1)
                url = f"https://duckduckgo.com/i.js?l=us-en&o=json&q={query}&vqd={vqd}"
                res = requests.get(url, headers=self.headers, timeout=10)
                data = res.json()
                for result in data.get("results", []):
                    if len(results) >= limit: break
                    img_url = result.get("image")
                    if img_url:
                        # Blacklist Check
                        if any(domain in img_url.lower() for domain in blacklist):
                            continue
                            
                        results.append({
                            "url": img_url,
                            "title": result.get("title", ""),
                            "description": ""
                        })
        except Exception as e:
            self.log(f"DDG error: {e}")
        return results

    def search_pexels(self, query, limit):
        self.log(f"Pexels search for '{query}'...")
        results = []
        try:
            url = f"https://www.pexels.com/search/{query}/"
            res = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            imgs = soup.find_all("img")
            for img in imgs:
                if len(results) >= limit: break
                src = img.get("src")
                if src and "images.pexels.com" in src:
                    results.append({"url": src, "title": img.get("alt", ""), "description": ""})
        except: pass
        return results

    def search_yahoo(self, query, limit):
        self.log(f"Yahoo search for '{query}'...")
        results = []
        try:
            url = f"https://images.search.yahoo.com/search/images?p={query}"
            res = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.find_all("li", class_="ld")
            for item in items:
                if len(results) >= limit: break
                data = item.get("data")
                if data:
                    try:
                        m_data = json.loads(data)
                        iurl = m_data.get("iurl")
                        if iurl: results.append({"url": iurl, "title": m_data.get("alt", ""), "description": ""})
                    except: continue
        except: pass
        return results

    def search_google(self, query, limit):
        self.log(f"Google Images search for '{query}'...")
        results = []
        
        user_agents = [
            # 1. Legacy Mobile (returns basic HTML, completely bypasses TLS fingerprint checks)
            "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12A366 Safari/600.1.4",
            # 2. Modern Desktop Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        for ua in user_agents:
            try:
                headers = {
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Referer": "https://www.google.com/"
                }
                url = f"https://www.google.com/search?q={query}&tbm=isch"
                res = requests.get(url, headers=headers, timeout=10)
                self.log(f"Google status: {res.status_code} | Length: {len(res.text)} | Agent: {ua[:30]}...")
                
                if res.status_code != 200:
                    continue
                
                raw_html = res.text
                soup = BeautifulSoup(raw_html, 'html.parser')
                seen = set()
                blacklist_domains = ["googleusercontent.com", "adsystem.com", "doubleclick.net"]
                
                # Strategy A: Extract high-resolution external image redirects from legacy mobile anchor tags
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/url?q=" in href:
                        match = re.search(r'/url\?q=([^&]+)', href)
                        if match:
                            dest_url = re.sub(r'&.*', '', requests.utils.unquote(match.group(1)))
                            if dest_url.startswith("http") and dest_url.lower().endswith((".jpg", ".jpeg", ".png")) and not any(domain in dest_url.lower() for domain in blacklist_domains):
                                if dest_url not in seen:
                                    seen.add(dest_url)
                                    results.append({
                                        "url": dest_url,
                                        "title": query,
                                        "description": ""
                                    })
                                    if len(results) >= limit:
                                        break
                                        
                # Strategy B: Fallback to high-res Javascript regex payload extraction
                if not results:
                    all_urls = re.findall(r'(https?://[^\s"\';\\<>]+?\.(?:jpg|jpeg|png))', raw_html)
                    for img_url in all_urls:
                        img_url = img_url.replace("\\u003d", "=").replace("\\u0026", "&").replace("\\", "")
                        if any(domain in img_url.lower() for domain in blacklist_domains):
                            continue
                        if img_url not in seen:
                            seen.add(img_url)
                            results.append({
                                "url": img_url,
                                "title": query,
                                "description": ""
                            })
                            if len(results) >= limit:
                                break
                                
                # Strategy C: Fallback to static thumbnail source links (excluding standard logos)
                if not results:
                    for img in soup.find_all("img"):
                        src = img.get("src")
                        if src and src.startswith("http") and not "gif" in src:
                            if any(domain in src.lower() for domain in ["google.com", "gstatic.com"]):
                                # Allow encrypted-tbn thumbnail links explicitly
                                if "encrypted-tbn" not in src:
                                    continue
                            results.append({
                                "url": src,
                                "title": img.get("alt", query),
                                "description": ""
                            })
                            if len(results) >= limit:
                                break
                                
                if results:
                    break  # Successfully found links!
            except Exception as e:
                self.log(f"Google Agent error: {e}")
                
        self.log(f"Google Images found {len(results)} candidate links.")
        return results
