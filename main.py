import os
import logging
import json
import glob
import threading
import uuid
import random
import textwrap
import warnings
from dotenv import load_dotenv
from colorlog import ColoredFormatter

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

# --- CONFIG ---
ENABLE_CAPTIONS = True
BROLL_FOLDER = "brolls"

# Logging
formatter = ColoredFormatter(
    "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
    datefmt=None,
    reset=True,
    log_colors={'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red'}
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger('LazyCut')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

vad_file_lock = threading.Lock()

# --- LAZY LOADER ---
def load_heavy_modules():
    global torch, sf, genai, PIL, whisper, whisper_model
    global VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

    if whisper_model is not None:
        return # Already loaded

    logger.info("🔌 Loading AI Engines (Lazy Load)...")
    
    import torch
    import soundfile as sf
    import google.generativeai as genai
    import PIL.Image
    import whisper
    from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
    from moviepy.config import change_settings

    # --- 🛠️ COMPATIBILITY FIXES ---
    warnings.filterwarnings("ignore")
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

    # --- 🎨 IMAGEMAGICK CONFIG ---
    IM_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe"
    if os.path.exists(IM_PATH):
        change_settings({"IMAGEMAGICK_BINARY": IM_PATH})

    # --- SETUP GENAI ---
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)

    # --- LOAD WHISPER ---
    logger.info("🔌 Loading Whisper (Global)...")
    whisper_model = whisper.load_model("base")

# --- 3. PREMIUM CAPTIONS 🎨 ---
def generate_premium_captions(text, duration, video_w, video_h):
    """
    Creates a clean, professional caption graphic (Hormozi Style).
    """
    # 1. Clean the text
    clean_text = text.strip().upper()
    
    # 2. Sizing (Hardcoded 4.5% of video height)
    FONT_SIZE = int(video_h * 0.045)
    
    # 3. Create the Text (Foreground)
    txt_clip = TextClip(
        clean_text,
        fontsize=FONT_SIZE,
        font="Arial-Bold", 
        color='white',
        stroke_color='black',
        stroke_width=4,
        method='label'
    )
    
    # 4. Positioning (Safe Zone: Bottom 15% reserved)
    # We place it at 75% height (0.75). 
    txt_clip = txt_clip.set_position(('center', 0.75), relative=True)
    txt_clip = txt_clip.set_start(0).set_duration(duration)
    
    return txt_clip

# --- 3.5 B-ROLL MANAGER ---
def setup_brolls():
    if not os.path.exists(BROLL_FOLDER):
        os.makedirs(BROLL_FOLDER)
        logger.info(f"📁 Created B-Roll folder: {BROLL_FOLDER}")
        return []
    
    files = glob.glob(os.path.join(BROLL_FOLDER, "*.mp4"))
    logger.info(f"🎥 Found {len(files)} B-Roll clips.")
    return files

def get_broll_clip(keyword_text, duration, broll_files, used_brolls):
    if not broll_files: return None
    
    # 1. Keyword Match
    matching = [f for f in broll_files if os.path.basename(f).lower().split('.')[0] in keyword_text.lower()]
    
    # 2. Fallback to Random (avoid repeats)
    if not matching:
        available = [f for f in broll_files if f not in used_brolls]
        if not available: 
            available = broll_files # Reset if all used
            used_brolls.clear()
        selected_path = random.choice(available)
    else:
        selected_path = random.choice(matching)
        
    used_brolls.append(selected_path)
    
    try:
        # Load and process B-Roll
        bc = VideoFileClip(selected_path)
        # Loop if too short
        if bc.duration < duration:
            bc = bc.loop(duration=duration)
        else:
            bc = bc.subclip(0, duration)
            
        bc = bc.resize(height=1080) # Normalize height (assuming 1080p target)
        # Crop to 9:16 if needed (simple center crop)
        if bc.w > bc.h * (9/16):
            bc = bc.crop(x_center=bc.w/2, width=bc.h*(9/16), height=bc.h)
            
        bc = bc.without_audio()
        return bc
    except Exception as e:
        logger.warning(f"⚠️ Failed to load B-Roll {selected_path}: {e}")
        return None

# --- 4. WORKER FUNCTION ---
def process_single_video(v_path, folder_path):
    fname = os.path.basename(v_path)
    unique_id = str(uuid.uuid4())[:8]
    temp_audio = os.path.join(folder_path, f"temp_{unique_id}.wav")
    
    try:
        video = VideoFileClip(v_path)
        if video.audio is None:
            video.close()
            return None

        video.audio.write_audiofile(temp_audio, fps=16000, verbose=False, logger=None)
        video.close()
        
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

        try:
            transcription = whisper_model.transcribe(v_path, word_timestamps=True)
            segments = transcription["segments"]
        except:
            segments = []

        if os.path.exists(temp_audio): os.remove(temp_audio)
        logger.info(f"✅ Processed: {fname}")
        return {"filename": fname, "filepath": v_path, "segments": segments, "vad": vad_data}

    except Exception as e:
        logger.error(f"❌ Error on {fname}: {e}")
        return None

# --- 5. FOLDER HUNTER ---
def find_newest_video_batch():
    IGNORE_LIST = ['.git', '.venv', 'venv', '__pycache__', '.idea', '.vscode', 'output', 'archive']
    all_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and d not in IGNORE_LIST]
    if not all_dirs: return None, None
    all_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    for folder in all_dirs:
        videos = glob.glob(os.path.join(folder, "*.mp4"))
        videos = [v for v in videos if "FINAL_" not in v]
        if videos:
            logger.info(f"📂 Detected Batch: '{folder}' ({len(videos)} videos)")
            return folder, videos
    return None, None

# --- 6. THE DIRECTOR (HUMAN PROMPT) ---
def get_director_cut(library):
    model = genai.GenerativeModel("models/gemini-2.5-pro")
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

    # --- OPTIMIZED PROMPT FOR HUMAN EDITING (PHASE 3) ---
    prompt = f"""
    Act as a World-Class Documentary Editor.
    
    GOAL: Create a cohesive, emotional narrative from these raw takes.
    
    INSTRUCTIONS:
    1. **Linear Storytelling:** Structure the video as Hook -> Problem -> Agitation -> Solution -> CTA.
    2. **The Anti-Loop Rule:** If multiple takes of the same sentence exist, select the ONE with the highest energy and discard the rest. Never output duplicate content.
    3. **Fluff Removal:** Aggressively remove "Umms", long pauses (>0.5s), and restarts.
    4. **Pacing:** Maintain a natural flow but cut dead air.
    
    RAW TRANSCRIPT DATA:
    {json.dumps(all_sentences, indent=2)}
    
    RETURN JSON: {{ "selected_sequence": [ID_LIST] }}
    """
    
    try:
        logger.info(f"🧠 The Director is crafting the narrative...")
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "")
        data = json.loads(text)
        return data.get("selected_sequence", []), all_sentences
    except Exception as e:
        logger.error(f"Director Error: {e}")
        return [], []

# --- 7. THE ASSEMBLER (SMOOTH & CLEAN) ---
def render_story(sequence_ids, all_sentences, full_library, folder_path, enable_broll=True):
    logger.info(f"🏗️ Assembling with Premium Captions & B-Roll...")
    
    final_clips = []
    open_source_handles = []
    is_zoomed = False
    file_map = {v['filename']: {'path': v['filepath'], 'vad': v['vad']} for v in full_library}
    
    # B-Roll State
    broll_files = setup_brolls()
    used_brolls = []
    last_broll_time = 0
    current_timeline_time = 0
    
    try:
        for seq_id in sequence_ids:
            sentence = next((s for s in all_sentences if s['global_id'] == seq_id), None)
            if not sentence: continue
            
            filename = sentence['filename']
            if filename not in file_map: continue
            
            file_data = file_map[filename]
            full_path = file_data['path']
            file_vad = file_data['vad']
            
            w_start = sentence['start']
            w_end = sentence['end']
            
            # --- HUMAN PACING FIX ---
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

            # 1. Create Clip
            clip = source_video.subclip(final_start, final_end)
            clip = clip.audio_fadein(0.05).audio_fadeout(0.05)
            
            # --- B-ROLL INJECTION ---
            clip_duration = clip.duration
            is_broll_candidate = (
                enable_broll and
                broll_files and
                current_timeline_time > 5.0 and # Hook protection
                (current_timeline_time - last_broll_time) > 10.0 # Frequency limit
            )
            
            if is_broll_candidate:
                # Determine B-Roll duration (max 3s, or clip duration)
                b_dur = min(clip_duration, 3.0)
                
                # Get B-Roll
                b_clip = get_broll_clip(sentence['text'], b_dur, broll_files, used_brolls)
                
                if b_clip:
                    b_clip = b_clip.set_start(0).set_position("center")
                    video_comp = CompositeVideoClip([clip, b_clip])
                    video_comp.audio = clip.audio
                    
                    clip = video_comp
                    last_broll_time = current_timeline_time
                    logger.info(f"🎞️ Inserted B-Roll for: '{sentence['text'][:20]}...'")

            current_timeline_time += clip_duration
            
            # 2. Natural Zoom
            if is_zoomed and clip.duration > 2.0:
                clip = clip.resize(height=int(source_video.h * 1.15)) 
                clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=source_video.w, height=source_video.h)
            
            # 3. Premium Captioning (Word-Level)
            if ENABLE_CAPTIONS and len(sentence.get('words', [])) > 0:
                words = sentence['words']
                caption_clips = []
                
                # Group words: Max 3-4 words per screen
                chunk_size = 3
                for i in range(0, len(words), chunk_size):
                    chunk = words[i:i+chunk_size]
                    text_chunk = " ".join([w['word'].strip() for w in chunk])
                    
                    # Timing relative to the clip
                    start_time = chunk[0]['start'] - final_start
                    end_time = chunk[-1]['end'] - final_start
                    
                    # Safety clamp
                    start_time = max(0, start_time)
                    end_time = min(clip.duration, end_time)
                    
                    if end_time - start_time < 0.2: continue 
                    
                    cap = generate_premium_captions(
                        text_chunk, 
                        end_time - start_time, 
                        source_video.w, 
                        source_video.h
                    )
                    cap = cap.set_start(start_time)
                    caption_clips.append(cap)
                
                if caption_clips:
                    clip = CompositeVideoClip([clip] + caption_clips).set_duration(clip.duration)
            
            # Fallback for old segments without words
            elif ENABLE_CAPTIONS and len(sentence['text']) > 2: 
                caption_graphic = generate_premium_captions(
                    sentence['text'], 
                    clip.duration, 
                    source_video.w, 
                    source_video.h
                )
                clip = CompositeVideoClip([clip, caption_graphic]).set_duration(clip.duration)

            is_zoomed = not is_zoomed
            final_clips.append(clip)

        if not final_clips: 
            logger.error("❌ No clips generated.")
            return

        output_file = os.path.join(folder_path, "FINAL_HUMAN_EDIT.mp4")
        if os.path.exists(output_file):
            try: os.remove(output_file)
            except: pass

        logger.info(f"🎞️ Rendering Final Human-Like Cut to: {output_file}")
        
        final_video = concatenate_videoclips(final_clips, method="compose")
        
        # CPU SAFE RENDER
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

    except Exception as e:
        logger.error(f"Render failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        logger.info("🧹 Cleaning up...")
        for v in open_source_handles:
            try: v.close()
            except: pass

# --- 8. MAIN ---
def start_lazycut(target_folder=None, enable_captions=True, enable_broll=True, progress_callback=None):
    # --- LOAD RESOURCES FIRST ---
    load_heavy_modules()

    global ENABLE_CAPTIONS
    ENABLE_CAPTIONS = enable_captions
    
    if target_folder:
        folder_path = target_folder
        videos = glob.glob(os.path.join(folder_path, "*.mp4"))
        video_files = [v for v in videos if "FINAL_" not in v]
        if not video_files:
            logger.error("❌ No videos found in target folder!")
            return
    else:
        folder_path, video_files = find_newest_video_batch()
    
    if not folder_path:
        logger.error("❌ No video folders found!")
        return

    logger.info(f"🚀 Processing {len(video_files)} videos...")
    if progress_callback: progress_callback("Processing Videos...")
    
    full_library = []
    # Safe Sequential Processing to prevent crashes
    for i, v_path in enumerate(video_files):
        result = process_single_video(v_path, folder_path)
        if result:
            full_library.append(result)
        if progress_callback: progress_callback(f"Processed {i+1}/{len(video_files)}")
    
    if progress_callback: progress_callback("AI Editing...")
    sequence_ids, all_sentences = get_director_cut(full_library)
    
    if sequence_ids:
        if progress_callback: progress_callback("Rendering Final Cut...")
        render_story(sequence_ids, all_sentences, full_library, folder_path, enable_broll)
        if progress_callback: progress_callback("Done!")

if __name__ == "__main__":
    start_lazycut()