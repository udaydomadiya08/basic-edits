import os
import sys
import asyncio
import random
from datetime import datetime
import logging
from moviepy.editor import VideoClip, ImageClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip, concatenate_videoclips
import moviepy.video.fx.all as vfx
import numpy as np
import re
import json

# Add backend to path for modules
sys.path.append(os.path.join(os.getcwd(), "backend"))
sys.path.append(os.path.join(os.getcwd(), "backend", "app"))

from backend.app.modules.simple_scraper import SimpleScraper
from backend.app.modules.downloader import ImageDownloader
from llm_router import LLMRouter, LLMProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CLI_Editor")

class AIVideoEditor:
    def __init__(self):
        # Use the 10 keys config
        self.router = LLMRouter(config_path="gemini_config_10keys.json")
        self.scraper = SimpleScraper()
        self.downloader = ImageDownloader(output_dir="datasets")
        self.music_dir = "music"
        self.output_dir = "outputs"
        os.makedirs(self.output_dir, exist_ok=True)

    def list_music(self):
        files = [f for f in os.listdir(self.music_dir) if f.endswith(('.mp3', '.wav'))]
        return sorted(files)

    async def get_autocorrected_topic(self, topic: str, song_name: str = "") -> str:
        """Correct typos and resolve ambiguous entities in user input using LLM Router with optional song context"""
        song_context = f"\nVideo Music Track: {song_name}" if song_name else ""
        prompt = (
            f"You are an expert AI search query optimizer. Given a user input search topic, identify the core subject, "
            f"entity, concept, or character they are looking for. Resolve any typos, spelling mistakes, or ambiguous/messy "
            f"descriptions (e.g., if they write a descriptive query, resolve it to the most clean, standard, and official name of that subject). "
            f"If a music track context is provided, use it to intelligently resolve any contextual ambiguities in the topic.\n"
            f"Return ONLY the official, correctly spelled name of the core subject. Do not explain, do not add quotes, just return the name.{song_context}\n"
            f"Topic: {topic}\n"
            f"Corrected Name:"
        )
        try:
            res = await self.router.get_response(prompt, category="text")
            corrected = res.get("content", "").strip()
            if corrected and len(corrected) < 50:
                return corrected
        except Exception:
            pass
        return topic

    async def get_hook_phrase(self, topic):
        prompt = f"Create a short, hype building phrase for a video edit about '{topic}'. Maximum 5-7 words. Make it sound cool and mysterious, like a 'Fictic' or 'Eagle Stan' edit hook. Return ONLY the phrase."
        response = await self.router.get_response(prompt)
        if response["status"] == "success":
            return response["content"].strip().replace('"', '')
        return f"The Power of {topic.capitalize()}"

    async def analyze_topic_dynamically(self, topic: str) -> dict:
        """Dynamically analyze the user input topic with AI to determine positive/negative criteria for zero-hardcoding auditing"""
        prompt = f"""
        You are an expert AI media auditor.
        Analyze the search topic: '{topic}'
        
        Generate a highly precise JSON specification for validating scraped image metadata.
        1. Identify the core subject/entity.
        2. Determine if this subject is a real-life person, model, actor, singer, or celebrity (is_real_person: true/false).
        3. Identify 'positive_keywords' that MUST appear in candidate titles or descriptions to prove it is actually about this subject (e.g. ['jalebi', 'sweet'] for 'jalebi'; ['weeknd', 'starboy'] for 'The Weeknd').
        4. Identify 'negative_keywords' representing irrelevant contexts, parodies, press event spam, blog/generator screenshots, reviews, or other off-topic contexts that must be rejected.
        
        Return ONLY a raw, clean JSON object matching this schema:
        {{
          "core_subject": "...",
          "is_real_person": true,
          "positive_keywords": ["word1", "word2", ...],
          "negative_keywords": ["word1", "word2", ...]
        }}
        STRICT: Do not provide any markdown, no explanation, no backticks, just the JSON string.
        """
        
        # Safe default spec in case of rate-limiting/errors
        spec = {
            "core_subject": topic,
            "is_real_person": False,
            "positive_keywords": [w.lower() for w in topic.split() if len(w) > 2],
            "negative_keywords": ["infographic", "diagram", "news", "event", "poster", "chart", "map", "parody", "cartoon", "caricature", "illustration", "sketch", "drawing", "press", "bash", "success party", "red carpet", "paparazzi", "screenshot", "blog", "article", "generator", "best ai", "top 10", "how to"]
        }
        
        try:
            response = await self.router.get_response(prompt, temperature=0.0)
            if response["status"] == "success":
                content = response["content"].strip()
                if content.startswith("```"):
                    content = re.sub(r"^```[a-zA-Z]*\n", "", content)
                    content = re.sub(r"\n```$", "", content)
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    spec["core_subject"] = parsed.get("core_subject", topic)
                    spec["is_real_person"] = bool(parsed.get("is_real_person", False))
                    spec["positive_keywords"] = [w.lower() for w in parsed.get("positive_keywords", []) if len(w) > 1]
                    spec["negative_keywords"] = [w.lower() for w in parsed.get("negative_keywords", []) if len(w) > 1]
                    print(f"✨ AI Dynamic Topic Analysis Complete for '{topic}':")
                    print(f"   Subject: {spec['core_subject']}")
                    print(f"   Real Person: {spec['is_real_person']}")
                    print(f"   Positives: {spec['positive_keywords']}")
                    print(f"   Negatives: {spec['negative_keywords']}")
        except Exception as e:
            logger.warning(f"Error during dynamic topic analysis: {e}")
            
        return spec

    async def filter_results_with_ai(self, topic, results, is_hook=False, topic_spec=None):
        if not results: return []
        
        if not topic_spec:
            topic_spec = await self.analyze_topic_dynamically(topic)
            
        # Prepare metadata for Gemini
        metadata_list = []
        for i, res in enumerate(results):
            metadata_list.append(f"[{i}] Title: {res['title']} | Desc: {res['description']}")
            
        prompt = f"""
        STRICT AUDIT: You are a professional video editor. 
        TOPIC: '{topic}'
        
        DYNAMIC SUBJECT SPECIFICATION:
        - Core Subject: {topic_spec.get('core_subject', topic)}
        - Must contain: {', '.join(topic_spec.get('positive_keywords', []))}
        - Must NOT contain: {', '.join(topic_spec.get('negative_keywords', []))}
        
        AUDITING INSTRUCTIONS:
        Scan both the 'Title' and 'Desc' (Description) for each candidate index in the Metadata List.
        You MUST DISCARD any candidates that match the negative indicators or are parodies/cartoons/fan-art/crowd shots.
        The approved candidate must represent the core subject beautifully, accurately, and cleanly as a high-quality vertical wallpaper.
        
        Metadata List:
        {chr(10).join(metadata_list)}
        
        Return a JSON list of indices that are 100% ACCURATE.
        Example: [0, 2, 5]
        STRICT: Do not provide any explanation, chat, or additional text. Only the JSON list.
        """
        
        # Use low temp for filtering accuracy
        response = await self.router.get_response(prompt, temperature=0.0)
        if response["status"] == "success":
            try:
                content = response["content"].strip()
                
                # Strip markdown code blocks if present
                clean_content = content
                if clean_content.startswith("```"):
                    clean_content = re.sub(r"^```[a-zA-Z]*\n", "", clean_content)
                    clean_content = re.sub(r"\n```$", "", clean_content)
                clean_content = clean_content.strip()
                
                # Auto-heal truncated JSON arrays if they start with [ but lack a closing ]
                if '[' in clean_content and ']' not in clean_content:
                    clean_content = re.sub(r'[^0-9,\s]*$', '', clean_content).strip()
                    clean_content = re.sub(r',\s*$', '', clean_content)
                    clean_content += ']'
                
                # Find JSON array boundaries
                start_idx = clean_content.find('[')
                end_idx = clean_content.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    array_str = clean_content[start_idx:end_idx+1]
                    indices = json.loads(array_str)
                    valid_urls = [results[i]['url'] for i in indices if isinstance(i, int) and i < len(results)]
                    if valid_urls:
                        print(f"✅ AI Audit: Approved {len(valid_urls)}/{len(results)} images.")
                        return valid_urls
                
                logger.warning(f"AI Audit: No valid list found in response. Raw: {content[:150]}...")
            except Exception as e:
                logger.warning(f"AI Filter parse error: {e}")
        
        return []

    def filter_results_locally(self, topic, results, topic_spec=None):
        """Ultra-resilient local fallback filter using dynamically generated AI criteria (Zero Hardcoding!)"""
        valid_urls = []
        
        if not topic_spec:
            # Create a basic default spec synchronously to keep signature compatible
            stop_words = {"the", "a", "an", "pop", "artist", "musician", "singer", "actor", "celeb", "celebrity", "man", "woman", "vertical", "wallpaper", "photo", "art"}
            important_words = [w for w in topic.lower().split() if w not in stop_words and len(w) > 2]
            if not important_words:
                important_words = [w for w in topic.lower().split() if len(w) > 1]
            topic_spec = {
                "positive_keywords": important_words,
                "negative_keywords": ["infographic", "diagram", "news", "event", "poster", "chart", "map", "parody", "cartoon", "caricature", "illustration", "sketch", "drawing", "press", "bash", "success party", "red carpet", "paparazzi", "screenshot", "blog", "article", "generator", "best ai", "top 10", "how to"]
            }
            
        pos_words = [w.lower() for w in topic_spec.get("positive_keywords", [])]
        neg_words = [w.lower() for w in topic_spec.get("negative_keywords", [])]
        
        for res in results:
            title = res.get("title", "").lower()
            desc = res.get("description", "").lower()
            
            # Check dynamic negative words
            if any(w in title or w in desc for w in neg_words):
                continue
                
            # If multi-word dynamic positive, require ALL words to be present
            # If single-word, require at least one word to be present
            if len(pos_words) > 1:
                if not all(w in title or w in desc for w in pos_words):
                    continue
            elif len(pos_words) == 1:
                if not any(w in title or w in desc for w in pos_words):
                    continue
                    
            valid_urls.append(res["url"])
                
        return valid_urls

    async def fetch_images(self, topic, count=15):
        all_paths = []
        attempts = 0
        
        # 1. Analyze topic dynamically with AI before querying search engines (Zero Hardcoding!)
        topic_spec = await self.analyze_topic_dynamically(topic)
        
        if topic_spec.get("is_real_person", False):
            # Tailored high-quality photo styles for real people, celebrities, models, singers
            styles = [
                "vertical wallpaper",
                "photoshoot vertical",
                "vertical portrait",
                "candid portrait vertical",
                "cinematic photo vertical"
            ]
        else:
            # Artistic and concept-oriented styles for abstract concepts, fictional characters, or objects
            styles = [
                "vertical wallpaper",
                "aesthetic vertical art",
                "cinematic vertical portrait",
                "dynamic lockscreen vertical art",
                "concept digital art vertical"
            ]
        # Shuffle visual styles list on every run to query completely different aesthetics first
        random.shuffle(styles)
        
        while len(all_paths) < count and attempts < len(styles):
            style = styles[attempts]
            attempts += 1
            print(f"🔍 Search Attempt {attempts} (Style: {style}, Got: {len(all_paths)}/{count})...")
            
            # Universal Super-Scraper Pipeline: Case-insensitively deduplicate words to prevent duplicate terms like "vertical vertical"
            query_words = []
            for word in f"{topic} {style}".split():
                if word.lower() not in [w.lower() for w in query_words]:
                    query_words.append(word)
            main_query = " ".join(query_words)
            stock_query = main_query
            
            print(f"🔍 Multi-Scraping Pexels, Bing, Google, DDG & Yahoo for '{style}' style...")
            candidates = []
            
            # 1. Pexels (premium stock photos)
            try:
                candidates += self.scraper.search_pexels(stock_query, 40)
            except Exception as e:
                logger.warning(f"Pexels error: {e}")
                
            # 2. Bing Images (highly reliable search results)
            try:
                candidates += self.scraper.search_bing(main_query, 60)
            except Exception as e:
                logger.warning(f"Bing error: {e}")
                
            # 3. Google Images
            try:
                candidates += self.scraper.search_google(main_query, 60)
            except Exception as e:
                logger.warning(f"Google error: {e}")
                
            # 4. DuckDuckGo & Yahoo
            if len(candidates) < 20:
                try:
                    candidates += self.scraper.search_duckduckgo(main_query, 60)
                    candidates += self.scraper.search_yahoo(main_query, 40)
                except Exception as e:
                    logger.warning(f"DDG/Yahoo error: {e}")
            
            # Shuffle scraped candidates list to ensure a unique selection of images is filtered and downloaded
            random.shuffle(candidates)
            
            # AI Filter using dynamically generated specifications
            verified_urls = await self.filter_results_with_ai(topic, candidates, topic_spec=topic_spec)
            
            # Resilient local fallback using dynamically generated specifications
            if not verified_urls:
                print("⚠️ AI Filter rate-limited or unavailable. Activating ultra-resilient local metadata filter...")
                verified_urls = self.filter_results_locally(topic, candidates, topic_spec=topic_spec)
            
            # Download
            if verified_urls:
                download_results = await self.downloader.bulk_download(verified_urls, topic)
                for r in download_results:
                    if r["path"] not in all_paths:
                        all_paths.append(r["path"])
            
            if len(all_paths) >= count:
                break
            print(f"🔄 Need more images. Successfully got {len(all_paths)} so far. Retrying...")
            
        if not all_paths:
            print("❌ Failure: No images could be secured.")
            return []
            
        print(f"✅ Target Reached: {len(all_paths)} images secured.")
        # Shuffle the final resulting paths so the image slots and drop sync sequence is completely unique and randomized
        random.shuffle(all_paths)
        return all_paths[:count+5]

    def create_zoom_clip(self, img_path, duration, target_size=(1080, 1920), start_zoom=1.0, end_zoom=1.2, blur=False):
        clip = ImageClip(img_path).set_duration(duration)
        w, h = clip.size
        target_w, target_h = target_size
        scale = max(target_w/w, target_h/h)
        clip = vfx.resize(clip, scale)
        clip = clip.set_position('center')
        
        def zoom_func(t):
            return start_zoom + (end_zoom - start_zoom) * (t / duration)
            
        clip = vfx.resize(clip, zoom_func).set_position('center').set_fps(24)
        if blur:
            clip = clip.fx(vfx.fadein, 1.0)
        return clip

    def find_best_segment(self, audio_path, build_up_duration=3.5, target_duration=10.0):
        try:
            print(f"Performing Rhythm Analysis on '{os.path.basename(audio_path)}'...")
            audio = AudioFileClip(audio_path)
            duration = audio.duration
            step = 0.05 # Higher precision for beat detection
            times = np.arange(0, duration, step)
            volumes = []
            for t in times:
                frame = audio.get_frame(t)
                volumes.append(np.abs(frame).mean())
            
            # Find the 'drop' based on Highest Delta (Slope)
            best_drop_time = duration / 2 
            max_delta = 0
            window_size = int(build_up_duration / step)
            
            # Use absolute difference between consecutive samples (the slope)
            for i in range(window_size, len(volumes) - int(10/step)):
                # Delta = Sudden change in volume
                delta = abs(volumes[i] - volumes[i-1])
                
                # We weight delta by current volume to ensure we hit a LOUD drop
                impact = delta * volumes[i]
                
                if impact > max_delta:
                    max_delta = impact
                    best_drop_time = i * step
            
            # 2. Extract Beats after the drop (Ensure at least target_duration of beats)
            beats = []
            drop_idx = int(best_drop_time / step)
            max_beats_limit = int(target_duration * 4)
            
            for i in range(drop_idx, len(volumes) - 1):
                if volumes[i] > volumes[i-1] and volumes[i] > volumes[i+1]:
                    if volumes[i] > np.mean(volumes[max(0, i-10):i+10]) * 1.15:
                        beats.append(i * step)
                
                if len(beats) > 10 and (beats[-1] - best_drop_time) >= target_duration:
                    break
                if len(beats) >= max_beats_limit: break
                
            print(f"📈 Drop at {best_drop_time:.2f}s | Delta Intensity: {max_delta:.4f} | Detected {len(beats)} beats.")
            return best_drop_time, beats
        except Exception as e:
            print(f"Rhythm analysis failed ({e})")
            return 10.0, [10.0 + i*0.4 for i in range(30)]

    def create_video(self, topic, hook_phrase, image_paths, music_path, output_name, use_hook=False, target_duration=10.0):
        print(f"Assembling Beat-Synced Masterpiece ({target_duration}s Main Edit)...")
        W, H = 1080, 1920 
        HOOK_DURATION = 3.5 if use_hook else 0.0
        
        drop_timestamp, beats = self.find_best_segment(music_path, HOOK_DURATION, target_duration)
        start_time = max(0, drop_timestamp - HOOK_DURATION)
        audio = AudioFileClip(music_path).subclip(start_time)
        
        # 1. MYSTERY HOOK (Optional)
        hook_part = None
        main_images = image_paths
        if use_hook:
            hook_img = image_paths[0]
            hook_bg = self.create_zoom_clip(hook_img, HOOK_DURATION, (W, H), 1.1, 1.3, blur=True)
            hook_bg = hook_bg.fl_image(lambda image: (image * 0.6).astype('uint8'))
            hook_text = TextClip(hook_phrase.upper(), fontsize=85, color='white', font='Arial-Bold', method='caption', size=(W-200, None), stroke_color='black', stroke_width=2, kerning=5).set_duration(HOOK_DURATION).set_position('center')
            hook_part = CompositeVideoClip([hook_bg, hook_text], size=(W, H))
            main_images = image_paths[1:]
            
        # 2. THE BANG & BEAT-SYNCED EDITS
        clips = []
        print(f"🎬 Assembly: Using {len(main_images)} unique images for {len(beats)-1} beats.")
        
        # We'll use images to match detected beats
        for i in range(len(beats) - 1):
            # Loop images if we have more beats than images
            img = main_images[i % len(main_images)]
            if i < len(main_images):
                print(f"   - Slot {i}: {os.path.basename(img)}")
            
            beat_start = beats[i]
            beat_end = beats[i+1]
            clip_duration = beat_end - beat_start
            
            # Safety checks
            if clip_duration < 0.15: clip_duration = 0.25
            
            z_start = 1.0 if i % 2 == 0 else 1.25
            z_end = 1.25 if z_start == 1.0 else 1.0
            
            c = self.create_zoom_clip(img, clip_duration, (W, H), z_start, z_end)
            flash = ColorClip(size=(W, H), color=(255,255,255)).set_duration(0.05).set_opacity(0.4)
            c = CompositeVideoClip([c, flash])
            clips.append(c)
            
        main_part = concatenate_videoclips(clips, method="compose")
        if use_hook and hook_part:
            final_video = concatenate_videoclips([hook_part, main_part], method="compose")
        else:
            final_video = main_part
            
        audio = audio.set_duration(final_video.duration).audio_fadein(1.0).audio_fadeout(2.0)
        final_video = final_video.set_audio(audio)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"{output_name}_{timestamp}.mp4")
        final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', threads=8, preset='superfast', bitrate="5000k")
        print(f"🔥 BEAT-SYNCED Edit saved to {output_path}")
 
 
async def main():
    editor = AIVideoEditor()
    songs = editor.list_music()
    if not songs: return
    for i, song in enumerate(songs): print(f"[{i}] {song}")
    try:
        song_idx = int(input("\nEnter song number: "))
        selected_song = os.path.join(editor.music_dir, songs[song_idx])
    except: return
    topic = input("Enter topic: ")
    if not topic: return
    
    corrected_topic = await editor.get_autocorrected_topic(topic, songs[song_idx])
    if corrected_topic.lower() != topic.lower():
        print(f"🪄 Autocorrected search term: '{topic}' ➔ '{corrected_topic}'")
        topic = corrected_topic
    print("Include introductory hook/title phase? (y/N): ")
    use_hook = input("Include introductory hook/title phase? (y/N): ").strip().lower() == 'y'
    print("Enter target edit duration in seconds (default 10): ")
    dur_input = input("Enter target edit duration in seconds (default 10): ").strip()
    try:
        target_duration = float(dur_input) if dur_input else 10.0
    except ValueError:
        target_duration = 10.0
        
    hook_phrase = ""
    if use_hook:
        hook_phrase = await editor.get_hook_phrase(topic)
        print(f"Hook: '{hook_phrase}'")
        
    # Dynamically scale required images based on duration (minimum 15, approx 2.5 per second to avoid looping)
    img_count = max(15, int(target_duration * 2.5))
    image_paths = await editor.fetch_images(topic, count=img_count)
    if not image_paths: return
    editor.create_video(topic, hook_phrase, image_paths, selected_song, topic.replace(' ','_'), use_hook=use_hook, target_duration=target_duration)
 
if __name__ == "__main__": asyncio.run(main())
