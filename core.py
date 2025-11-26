import os
import json
import glob
import threading
import uuid
import random
import warnings
import logging
from dotenv import load_dotenv

# Import Config
from config import BROLL_FOLDER, IMAGEMAGICK_BINARY, setup_logging

# Setup Logger
logger = setup_logging()

# --- LAZY LOAD GLOBALS ---
torch = None
sf = None
genai = None
PIL = None
whisper = None
whisper_model = None
VideoFileClip = None
concatenate_videoclips = None
TextClip = None
CompositeVideoClip = None

vad_file_lock = threading.Lock()

class LazyCutCore:
    def __init__(self):
        self.is_loaded = False
        self.stop_event = threading.Event()
        self.current_status = "Idle"
        
    def load_heavy_modules(self, callback=None):
        """
        Loads heavy AI libraries. Can take a few seconds.
        """
        global torch, sf, genai, PIL, whisper, whisper_model
        global VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

        if self.is_loaded:
            if callback: callback("Modules already loaded.")
            return

        if callback: callback("🔌 Loading AI Engines (This may take a moment)...")
        logger.info("🔌 Loading AI Engines...")

        import torch
        import soundfile as sf
        # import google.generativeai as genai # Moved to Server
        import PIL.Image
        import whisper
        from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        from moviepy.config import change_settings

        # Compatibility Fixes
        warnings.filterwarnings("ignore")
        if not hasattr(PIL.Image, 'ANTIALIAS'):
            PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

        # ImageMagick Config
        if IMAGEMAGICK_BINARY:
            change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY})

        # Setup GenAI (Removed - Moved to Server)
        # load_dotenv()
        # api_key = os.getenv("GEMINI_API_KEY")
        # if not api_key: ...
        
        # Load Requests (for Server API)
        import requests

        # Load Whisper
        if callback: callback("🔌 Loading Whisper Model...")
        whisper_model = whisper.load_model("base")
        
        self.is_loaded = True
        logger.info("✅ Modules Loaded.")
        if callback: callback("✅ Ready.")

    def generate_premium_captions(self, text, duration, video_w, video_h):
        """Creates a clean, professional caption graphic."""
        clean_text = text.strip().upper()
        FONT_SIZE = int(video_h * 0.045)
        
        try:
            txt_clip = TextClip(
                clean_text,
                fontsize=FONT_SIZE,
                font="Arial-Bold", 
                color='white',
                stroke_color='black',
                stroke_width=4,
                method='label'
            )
            txt_clip = txt_clip.set_position(('center', 0.75), relative=True)
            txt_clip = txt_clip.set_start(0).set_duration(duration)
            return txt_clip
        except Exception as e:
            logger.error(f"Caption Error: {e}")
            return None

    def setup_brolls(self):
        if not os.path.exists(BROLL_FOLDER):
            os.makedirs(BROLL_FOLDER)
            return []
        files = glob.glob(os.path.join(BROLL_FOLDER, "*.mp4"))
        return files

    def get_broll_clip(self, keyword_text, duration, broll_files, used_brolls):
        if not broll_files: return None
        
        matching = [f for f in broll_files if os.path.basename(f).lower().split('.')[0] in keyword_text.lower()]
        
        if not matching:
            available = [f for f in broll_files if f not in used_brolls]
            if not available: 
                available = broll_files
                used_brolls.clear()
            selected_path = random.choice(available)
        else:
            selected_path = random.choice(matching)
            
        used_brolls.append(selected_path)
        
        try:
            bc = VideoFileClip(selected_path)
            if bc.duration < duration:
                bc = bc.loop(duration=duration)
            else:
                bc = bc.subclip(0, duration)
                
            bc = bc.resize(height=1080)
            if bc.w > bc.h * (9/16):
                bc = bc.crop(x_center=bc.w/2, width=bc.h*(9/16), height=bc.h)
                
            bc = bc.without_audio()
            return bc
        except Exception as e:
            logger.warning(f"⚠️ Failed to load B-Roll {selected_path}: {e}")
            return None

            bc = bc.without_audio()
            return bc
        except Exception as e:
            logger.warning(f"⚠️ Failed to load B-Roll {selected_path}: {e}")
            return None

    # Removed scale_to_hd to strictly preserve source dimensions
    # No resizing, no scaling, no cropping.


    def process_single_video(self, v_path, folder_path, callback=None):
        fname = os.path.basename(v_path)
        unique_id = str(uuid.uuid4())[:8]
        temp_audio = os.path.join(folder_path, f"temp_{unique_id}.wav")
        
        try:
            video = VideoFileClip(v_path)
            if video.audio is None:
                logger.warning(f"⚠️ Skipped {fname}: No audio track found.")
                if callback: callback(f"⚠️ Skipped {fname}: No audio track found.")
                video.close()
                return None

            video.audio.write_audiofile(temp_audio, fps=16000, verbose=False, logger=None)
            video.close()
            
            # VAD
            if callback: callback(f"🎙️ Analyzing Audio (VAD)...")
            if os.path.getsize(temp_audio) < 1000: 
                vad_data = []
            else:
                with vad_file_lock:
                    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                                  model='silero_vad',
                                                  force_reload=False,
                                                  onnx=False)
                (get_speech_timestamps, _, _, _, _) = utils
                data, samplerate = sf.read(temp_audio)
                if len(data) == 0:
                    vad_data = []
                else:
                    wav = torch.FloatTensor(data)
                    if len(wav.shape) > 1: wav = wav[:, 0]
                    speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
                    vad_data = [{'start': st['start']/16000, 'end': st['end']/16000} for st in speech_timestamps]

            # Whisper
            if callback: callback(f"📝 Transcribing Speech (Whisper)...")
            try:
                transcription = whisper_model.transcribe(v_path, word_timestamps=True)
                segments = transcription["segments"]
            except:
                segments = []

            if os.path.exists(temp_audio): os.remove(temp_audio)
            return {"filename": fname, "filepath": v_path, "segments": segments, "vad": vad_data}

        except Exception as e:
            logger.error(f"❌ Error on {fname}: {e}")
            if callback: callback(f"❌ Error on {fname}: {e}")
            return None

    def get_director_cut(self, library):
        # --- SERVER-SIDE AI LOGIC ---
        SERVER_URL = "http://localhost:8000/process_script"
        
        all_sentences = []
        global_id = 0
        transcript_parts = []
        
        for video in library:
            for seg in video['segments']:
                all_sentences.append({
                    "global_id": global_id,
                    "filename": video['filename'],
                    "text": seg['text'],
                    "start": seg['start'],
                    "end": seg['end'],
                    "words": seg.get('words', [])
                })
                transcript_parts.append(seg['text'])
                global_id += 1

        # Generate Hardware ID
        hw_id = str(uuid.getnode())

        # Join transcript parts into a single string
        full_transcript = " ".join(transcript_parts)
        
        if not full_transcript.strip():
            logger.warning("⚠️ Transcript is empty. No speech detected.")
            return "EMPTY_TRANSCRIPT", []

        payload = {
            "hardware_id": hw_id,
            "transcript": full_transcript
        }
        
        try:
            logger.info(f"🧠 Connecting to AI Director (Server)...")
            import requests
            response = requests.post(SERVER_URL, json=payload)
            
            if response.status_code == 403:
                logger.warning("⚠️ Daily Limit Reached.")
                return "LIMIT_REACHED", []
            
            if response.status_code != 200:
                error_msg = f"Server Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return "SERVER_ERROR", error_msg

            data = response.json()
            indices = data.get("indices", [])
            seo_title = data.get("seo_title", "Viral_Edit")
            
            if not indices:
                logger.warning("⚠️ AI returned 0 selected clips.")
                return [], [], "Viral_Edit"
            
            # Map indices back to global IDs
            selected_sequence = [all_sentences[i]['global_id'] for i in indices if i < len(all_sentences)]
            
            logger.info(f"✨ SEO Title: {seo_title}")
            return selected_sequence, all_sentences, seo_title

        except Exception as e:
            logger.error(f"Director Error: {e}")
            return "CONNECTION_ERROR", str(e)

    def render_story(self, sequence_ids, all_sentences, full_library, folder_path, seo_title="Viral_Edit", enable_captions=True, enable_broll=True, callback=None):
        logger.info(f"🏗️ Assembling Story...")
        if callback: callback("🏗️ Assembling Final Cut...")
        
        final_clips = []
        open_source_handles = []
        is_zoomed = False
        file_map = {v['filename']: {'path': v['filepath'], 'vad': v['vad']} for v in full_library}
        
        broll_files = self.setup_brolls()
        used_brolls = []
        last_broll_time = 0
        current_timeline_time = 0
        
        try:
            total_seq = len(sequence_ids)
            for idx, seq_id in enumerate(sequence_ids):
                if self.stop_event.is_set(): return
                
                sentence = next((s for s in all_sentences if s['global_id'] == seq_id), None)
                if not sentence: continue
                
                filename = sentence['filename']
                if filename not in file_map: continue
                
                file_data = file_map[filename]
                full_path = file_data['path']
                file_vad = file_data['vad']
                
                w_start = sentence['start']
                w_end = sentence['end']
                
                refined_start = max(0, w_start - 0.2)
                refined_end = w_end + 0.2 
                
                relevant_vad = [v for v in file_vad if (v['start'] >= w_start - 1.0) and (v['end'] <= w_end + 1.0)]
                if relevant_vad:
                    refined_start = min([v['start'] for v in relevant_vad])
                    refined_end = max([v['end'] for v in relevant_vad])
                
                source_video = VideoFileClip(full_path)
                open_source_handles.append(source_video)
                
                final_start = max(0, refined_start - 0.05)
                final_end = min(source_video.duration, refined_end + 0.1)
                if (final_end - final_start) < 0.5: continue

                clip = source_video.subclip(final_start, final_end)
                clip = clip.audio_fadein(0.05).audio_fadeout(0.05)
                
                # STRICT SOURCE PRESERVATION: No resizing, no scaling.
                # clip = self.scale_to_hd(clip)  <-- REMOVED
                
                # B-Roll
                clip_duration = clip.duration
                is_broll_candidate = (
                    enable_broll and
                    broll_files and
                    current_timeline_time > 5.0 and 
                    (current_timeline_time - last_broll_time) > 10.0
                )
                
                if is_broll_candidate:
                    b_dur = min(clip_duration, 3.0)
                    b_clip = self.get_broll_clip(sentence['text'], b_dur, broll_files, used_brolls)
                    if b_clip:
                        # Resize B-roll to match main clip dimensions exactly
                        if b_clip.size != clip.size:
                            b_clip = b_clip.resize(newsize=clip.size)
                        b_clip = b_clip.set_start(0).set_position("center")
                        video_comp = CompositeVideoClip([clip, b_clip])
                        video_comp.audio = clip.audio
                        clip = video_comp
                        last_broll_time = current_timeline_time

                current_timeline_time += clip_duration
                
                # Ken Burns Zoom Effect (smooth zoom for visual interest)
                if is_zoomed and clip.duration > 2.0:
                    def zoom_at_time(t):
                        # Smooth zoom from 1.0x to 1.1x over clip duration
                        progress = t / clip.duration
                        return 1.0 + (0.1 * progress)
                    
                    # Apply zoom while maintaining aspect ratio
                    clip = clip.resize(lambda t: zoom_at_time(t))
                    # Scale back to ORIGINAL source dimensions (not HD)
                    clip = clip.resize(newsize=source_video.size)
                
                # Captions
                if enable_captions and len(sentence.get('words', [])) > 0:
                    words = sentence['words']
                    caption_clips = []
                    chunk_size = 3
                    for i in range(0, len(words), chunk_size):
                        chunk = words[i:i+chunk_size]
                        text_chunk = " ".join([w['word'].strip() for w in chunk])
                        start_time = max(0, chunk[0]['start'] - final_start)
                        end_time = min(clip.duration, chunk[-1]['end'] - final_start)
                        
                        if end_time - start_time < 0.2: continue 
                        
                        cap = self.generate_premium_captions(text_chunk, end_time - start_time, source_video.w, source_video.h)
                        if cap:
                            cap = cap.set_start(start_time)
                            caption_clips.append(cap)
                    
                    if caption_clips:
                        clip = CompositeVideoClip([clip] + caption_clips).set_duration(clip.duration)
                
                is_zoomed = not is_zoomed
                final_clips.append(clip)
                
                if callback and idx % 5 == 0:
                    callback(f"Rendering segment {idx+1}/{total_seq}...")

            if not final_clips: 
                logger.error("❌ No clips generated.")
                if callback: callback("❌ Error: No clips generated.")
                return

            # Use SEO title for filename with robust sanitization
            # Remove any non-alphanumeric characters except underscores and hyphens
            safe_title = "".join(c for c in seo_title if c.isalnum() or c in ('_', '-'))
            safe_title = safe_title.strip()
            if not safe_title: safe_title = "Viral_Edit"
            
            output_file = os.path.join(folder_path, f"{safe_title}.mp4")
            if os.path.exists(output_file):
                try: os.remove(output_file)
                except: pass

            logger.info(f"🎞️ Writing to disk: {output_file}")
            if callback: callback("💾 Saving Final Video (This takes time)...")
            
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(
                output_file, 
                codec="libx264", 
                audio_codec="aac", 
                preset="medium", 
                fps=24, 
                verbose=False, 
                logger=None
            )
            logger.info(f"✅ DONE! Saved in '{folder_path}'")
            if callback: callback("✅ Video Processing Complete!")

        except Exception as e:
            logger.error(f"Render failed: {e}")
            if callback: callback(f"❌ Render Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            for v in open_source_handles:
                try: v.close()
                except: pass

    def run_pipeline(self, folder_path, enable_captions=True, enable_broll=True, callback=None):
        if not self.is_loaded:
            self.load_heavy_modules(callback)
            
        videos = glob.glob(os.path.join(folder_path, "*.mp4"))
        video_files = [v for v in videos if "FINAL_" not in v]
        
        if not video_files:
            if callback: callback("❌ No valid videos found in folder.")
            return

        if callback: callback(f"🚀 Found {len(video_files)} videos. Starting...")
        
        full_library = []
        for i, v_path in enumerate(video_files):
            if self.stop_event.is_set(): return
            if callback: callback(f"Processing Video {i+1}/{len(video_files)}: {os.path.basename(v_path)}")
            
            result = self.process_single_video(v_path, folder_path, callback)
            if result:
                full_library.append(result)
        
        if not full_library:
            if callback: callback("❌ No videos could be processed.")
            return

        if callback: callback("🧠 AI Director is analyzing footage...")
        result = self.get_director_cut(full_library)
        
        # Handle different return types from get_director_cut
        if isinstance(result, tuple) and len(result) == 3:
            sequence_ids, all_sentences, seo_title = result
        elif isinstance(result, tuple) and len(result) == 2:
            # Error cases return 2 values
            sequence_ids, all_sentences = result
            seo_title = "Viral_Edit"
        else:
            sequence_ids = result
            all_sentences = []
            seo_title = "Viral_Edit"
        
        if sequence_ids == "LIMIT_REACHED":
            if callback: callback("🚫 Daily Limit Reached (3/3). Upgrade to Pro.")
            raise Exception("Daily Limit Reached")
            
        if sequence_ids == "EMPTY_TRANSCRIPT":
            if callback: callback("⚠️ No speech detected in videos. Cannot edit.")
            return

        if sequence_ids == "SERVER_ERROR":
            msg = all_sentences # In this case, we returned error msg in second arg
            if callback: callback(f"❌ {msg}")
            return

        if sequence_ids == "CONNECTION_ERROR":
            msg = all_sentences
            if callback: callback(f"❌ Connection Failed: {msg}")
            return

        if sequence_ids:
            self.render_story(sequence_ids, all_sentences, full_library, folder_path, seo_title, enable_captions, enable_broll, callback)
        else:
            if callback: callback("❌ Director returned 0 clips (AI found nothing interesting).")
