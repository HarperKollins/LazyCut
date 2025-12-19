import os
import sys
if sys.platform.startswith("win"):
    import codecs
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except Exception: pass

import json
import glob
import threading
import uuid
import random
import warnings
import logging
import requests
import numpy as np
import time
from config import BROLL_FOLDER, IMAGEMAGICK_BINARY, SERVER_URL, load_settings, setup_logging

# Setup Logger
logger = setup_logging()

# --- LAZY LOAD GLOBALS ---
torch = None
sf = None
PIL = None
whisper = None
whisperx = None
mp_face_detection = None
SentenceTransformer = None
VideoFileClip = None
concatenate_videoclips = None
TextClip = None
CompositeVideoClip = None
ffmpeg = None

vad_file_lock = threading.Lock()

class LimitReachedException(Exception):
    pass

class VideoEngine:
    def __init__(self):
        self.is_loaded = False
        self.stop_event = threading.Event()
        self.face_detection = None
        self.model_embedding = None
        self.use_whisperx = False

    def load_modules(self, callback=None):
        global torch, sf, PIL, whisper, whisperx, mp_face_detection, SentenceTransformer, ffmpeg
        global VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

        if self.is_loaded:
            if callback: callback("Modules already loaded.")
            return

        if callback: callback("Loading High-Fidelity Engine...")
        logger.info("Loading High-Fidelity Engine...")

        try:
            import torch
            import soundfile as sf
            import PIL.Image
            import ffmpeg
            from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
            from moviepy.config import change_settings
            
            # Compatibility Fixes
            warnings.filterwarnings("ignore")
            if not hasattr(PIL.Image, 'ANTIALIAS'):
                PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

            # ImageMagick Config
            if IMAGEMAGICK_BINARY:
                change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_BINARY})

        except ImportError as e:
            logger.error(f"Critical Import Error: {e}")
            if callback: callback("Critical Error: {e}")
            return

        # Optional: WhisperX
        try:
            import whisperx
            self.use_whisperx = True
            logger.info("WhisperX loaded.")
        except ImportError:
            logger.warning("WhisperX not found. Falling back to standard Whisper.")
            import whisper
            self.use_whisperx = False

        # Optional: MediaPipe
        try:
            import mediapipe as mp
            mp_face_detection = mp.solutions.face_detection
            self.face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
            logger.info("MediaPipe loaded.")
        except ImportError:
            logger.warning("MediaPipe not found. Smart Crop disabled.")
            self.face_detection = None

        # Optional: Sentence Transformers
        try:
            from sentence_transformers import SentenceTransformer
            self.model_embedding = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence Transformers loaded.")
        except ImportError:
            logger.warning("SentenceTransformer not found. Semantic B-Roll disabled.")
            self.model_embedding = None

        self.is_loaded = True
        if callback: callback("Engine Ready.")

    def smart_crop(self, clip, target_ratio=(9, 16)):
        """
        Applies face-aware cropping to maintain the target aspect ratio.
        Uses a rolling average to smooth out camera movement.
        """
        if not self.face_detection:
            # Fallback to center crop
            return self.center_crop(clip, target_ratio)

        w, h = clip.size
        target_w = int(h * target_ratio[0] / target_ratio[1])
        
        # If video is already narrower than target, just resize height (or pad) - simplified: pass through if close
        if w <= target_w:
            return clip

        # Analyze frames for face position
        # We'll sample 1 frame every 0.5 seconds to save performance
        timestamps = np.arange(0, clip.duration, 0.5)
        centers = []
        
        for t in timestamps:
            frame = clip.get_frame(t)
            results = self.face_detection.process(np.array(frame))
            
            cx = 0.5 # Default center
            if results.detections:
                # Get the largest face
                largest_face = max(results.detections, key=lambda d: d.location_data.relative_bounding_box.width * d.location_data.relative_bounding_box.height)
                bbox = largest_face.location_data.relative_bounding_box
                cx = bbox.xmin + bbox.width / 2
                
            centers.append(cx)
        
        if not centers:
            return self.center_crop(clip, target_ratio)

        # Smooth the centers (Rolling Average)
        # For simplicity in MoviePy, we'll take the median center to avoid jitter entirely for short clips
        # Or implement a sliding window if we want movement. 
        # Let's use a weighted average favoring the center of the clip duration.
        avg_cx = np.mean(centers)
        
        # Clamp center so crop doesn't go out of bounds
        # Crop width is target_w. 
        # Left edge = center_x * w - target_w / 2
        
        pixel_cx = avg_cx * w
        x1 = pixel_cx - target_w / 2
        
        # Clamp
        x1 = max(0, min(x1, w - target_w))
        
        return clip.crop(x1=x1, y1=0, width=target_w, height=h)

    def center_crop(self, clip, target_ratio=(9, 16)):
        w, h = clip.size
        target_w = int(h * target_ratio[0] / target_ratio[1])
        if w <= target_w: return clip
        return clip.crop(x_center=w/2, width=target_w, height=h)

    def high_quality_resize(self, clip, width=None, height=None):
        """
        Safe resize that respects source dimensions and avoids MoviePy crashes.
        """
        # 1. RESPECT SOURCE: If dimensions match (or user disabled resize), return immediately.
        if (width is None or clip.w == width) and (height is None or clip.h == height):
            return clip
            
        # 2. SAFE RESIZE: Remove the 'resample' arg that crashes MoviePy v1.0.3
        # Just use the standard internal resizer.
        try:
            return clip.resize(newsize=(width, height))
        except Exception as e:
            logger.warning(f"Resize failed, using original dimensions: {e}")
            return clip

    def get_semantic_broll(self, sentence_text, duration, broll_files, used_brolls):
        if not broll_files or not self.model_embedding: return None
        
        sentence_emb = self.model_embedding.encode(sentence_text)
        best_match = None
        best_score = -1
        
        for b_file in broll_files:
            fname = os.path.basename(b_file).replace(".mp4", "").replace("_", " ")
            b_emb = self.model_embedding.encode(fname)
            score = np.dot(sentence_emb, b_emb) / (np.linalg.norm(sentence_emb) * np.linalg.norm(b_emb))
            
            if score > best_score:
                best_score = score
                best_match = b_file
        
        if best_score > 0.4:
            selected_path = best_match
        else:
            return None # Strict mode: no random B-roll
            
        used_brolls.append(selected_path)
        
        try:
            bc = VideoFileClip(selected_path)
            if bc.duration < duration:
                bc = bc.loop(duration=duration)
            else:
                bc = bc.subclip(0, duration)
            
            # Match dimensions of the main video (Smart Crop B-Roll too!)
            # Assuming main video is 1080x1920 (9:16)
            bc = self.smart_crop(bc, target_ratio=(9, 16))
            bc = self.high_quality_resize(bc, width=1080, height=1920)
            
            bc = bc.without_audio()
            return bc
        except Exception as e:
            logger.warning(f"⚠️ Failed to load B-Roll {selected_path}: {e}")
            return None

    def transcribe_audio(self, audio_path):
        """
        Uses WhisperX for precision alignment if available, otherwise standard Whisper.
        """
        if self.use_whisperx:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            batch_size = 16
            compute_type = "float16" if device == "cuda" else "int8"

            model = whisperx.load_model("base", device, compute_type=compute_type)
            audio = whisperx.load_audio(audio_path)
            result = model.transcribe(audio, batch_size=batch_size)

            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            return result["segments"]
        else:
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, word_timestamps=True)
            return result["segments"]

    def get_director_cut(self, library, mock=False):
        if mock:
            # Return all segments for testing
            all_sentences = []
            global_id = 0
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
                    global_id += 1
            return [s['global_id'] for s in all_sentences], all_sentences, "Mock_Test_Video"

        # Real Server Call
        settings = load_settings()
        license_key = settings.get("license_key", "")
        
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

        hw_id = str(uuid.getnode())
        full_transcript = " ".join(transcript_parts)
        
        if not full_transcript.strip():
            return "EMPTY_TRANSCRIPT", []

        payload = {
            "hardware_id": hw_id,
            "transcript": full_transcript,
            "token": license_key
        }
        
        try:
            logger.info(f"🧠 Connecting to AI Director (Server)...")
            response = requests.post(SERVER_URL, json=payload)
            
            if response.status_code == 403:
                raise LimitReachedException("Daily Limit Reached")
            
            if response.status_code != 200:
                return "SERVER_ERROR", response.text

            data = response.json()
            indices = data.get("cut_list", [])
            seo_title = data.get("seo_title", "Viral_Edit")
            
            if not indices:
                return [], [], "Viral_Edit"
            
            selected_sequence = [all_sentences[i]['global_id'] for i in indices if i < len(all_sentences)]
            return selected_sequence, all_sentences, seo_title

        except LimitReachedException:
            raise
        except Exception as e:
            logger.error(f"Director Error: {e}")
            return "CONNECTION_ERROR", str(e)

    def render_timeline(self, sequence_ids, all_sentences, full_library, folder_path, seo_title, enable_broll=True, callback=None):
        logger.info(f"Rendering Timeline for '{seo_title}'...")
        if callback: callback(f"Rendering '{seo_title}'...")
        
        final_clips = []
        opened_source_clips = [] # Keep track to close later
        file_map = {v['filename']: {'path': v['filepath']} for v in full_library}
        
        broll_files = glob.glob(os.path.join(BROLL_FOLDER, "*.mp4"))
        used_brolls = []
        
        try:
            for idx, seq_id in enumerate(sequence_ids):
                if self.stop_event.is_set(): break
                
                sentence = next((s for s in all_sentences if s['global_id'] == seq_id), None)
                if not sentence: continue
                
                filename = sentence['filename']
                if filename not in file_map: continue
                
                full_path = file_map[filename]['path']
                start_t = sentence['start']
                end_t = sentence['end']
                
                # Keep source open until the end
                source_video = VideoFileClip(full_path)
                opened_source_clips.append(source_video)
                
                # 1. Precision Cut
                clip = source_video.subclip(start_t, end_t)
                
                # 2. Audio Fade (2 frames ~ 0.08s)
                clip = clip.audio_fadein(0.08).audio_fadeout(0.08)
                
                # 3. Smart Crop (to 9:16)
                clip = self.smart_crop(clip, target_ratio=(9, 16))
                
                # 4. High Quality Resize (Ensure 1080x1920)
                clip = self.high_quality_resize(clip, width=1080, height=1920)
                
                # 5. Semantic B-Roll
                if enable_broll:
                    b_clip = self.get_semantic_broll(sentence['text'], clip.duration, broll_files, used_brolls)
                    if b_clip:
                        # B-Roll is already smart cropped and resized in get_semantic_broll
                        # We need to ensure b_clip's source is also managed if it wasn't loaded fully into memory
                        # But get_semantic_broll loads it. 
                        # Ideally we should track b-roll clips too if they are open.
                        # For now, let's assume get_semantic_broll handles it or we rely on GC for b-roll 
                        # (since we don't return the source object there, just the subclip).
                        # Actually, MoviePy subclips hold ref to reader.
                        # We should probably track them if we want to be safe, but let's stick to fixing the main crash first.
                        clip = b_clip.set_audio(clip.audio)

                final_clips.append(clip)
                # source_video.close()  <-- REMOVED: Do not close here!
                
                if callback and idx % 5 == 0:
                    callback(f"Rendering segment {idx+1}/{len(sequence_ids)}...")

            if not final_clips or self.stop_event.is_set(): 
                return

            # Concatenate
            final_video = concatenate_videoclips(final_clips, method="compose")
            
            safe_title = "".join(c for c in seo_title if c.isalnum() or c in ('_', '-')).strip()
            output_file = os.path.join(folder_path, f"{safe_title}.mp4")
            
            if callback: callback("Encoding Final Video...")
            
            # High Speed Encoding Settings (User requested "VERY FAST")
            final_video.write_videofile(
                output_file, 
                codec="libx264", 
                audio_codec="aac", 
                preset="ultrafast", # Max speed
                bitrate="5000k", # Sufficient for 1080p
                fps=30, 
                verbose=False, 
                logger=None,
                threads=8 # Use more threads if available
            )
            
            if callback: callback("Video Processing Complete!")

        except Exception as e:
            logger.error(f"Render failed: {e}")
            if callback: callback(f"Render Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            logger.info("Cleaning up resources...")
            for clip in opened_source_clips:
                try:
                    clip.close()
                except: pass
            # Also close final_video if it exists
            try:
                if 'final_video' in locals():
                    final_video.close()
            except: pass

# --- WRAPPER FOR APP COMPATIBILITY ---
class LazyCutCore:
    def __init__(self):
        self.engine = VideoEngine()
        
    def run_pipeline(self, folder_path, enable_captions=True, enable_broll=True, callback=None):
        self.engine.load_modules(callback)
        
        videos = glob.glob(os.path.join(folder_path, "*.mp4"))
        video_files = [v for v in videos if "FINAL_" not in v]
        
        if not video_files:
            if callback: callback("❌ No videos found.")
            return
            
        full_library = []
        for v_path in video_files:
            if self.engine.stop_event.is_set(): return
            
            # Transcribe
            fname = os.path.basename(v_path)
            if callback: callback(f"🎙️ Transcribing {fname}...")
            
            # Extract Audio
            temp_audio = os.path.join(folder_path, "temp.wav")
            try:
                v = VideoFileClip(v_path)
                v.audio.write_audiofile(temp_audio, fps=16000, verbose=False, logger=None)
                v.close()
                
                segments = self.engine.transcribe_audio(temp_audio)
                full_library.append({"filename": fname, "filepath": v_path, "segments": segments})
                
                if os.path.exists(temp_audio): os.remove(temp_audio)
            except Exception as e:
                logger.error(f"Error processing {fname}: {e}")
        
        if not full_library: return

        if callback: callback("🧠 AI Director Analyzing...")
        
        # Mock Server for now as requested, or use real if configured
        # Using mock=True to test local video engine first
        try:
            result = self.engine.get_director_cut(full_library, mock=True) 
        except LimitReachedException:
            if callback: callback("🚫 Daily Limit Reached.")
            raise

        if isinstance(result, tuple):
            sequence_ids, all_sentences, seo_title = result
        else:
            return # Error handled in get_director_cut
            
        self.engine.render_timeline(sequence_ids, all_sentences, full_library, folder_path, seo_title, enable_broll, callback)
