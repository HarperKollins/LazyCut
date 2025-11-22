import os
from moviepy.editor import ColorClip, TextClip, CompositeVideoClip
from moviepy.config import change_settings

# --- 1. TELL PYTHON EXACTLY WHERE IT IS ---
# We use the path you found: C:\Program Files\ImageMagick-7.1.2-Q16
IM_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe"

if os.path.exists(IM_PATH):
    change_settings({"IMAGEMAGICK_BINARY": IM_PATH})
    print(f"✅ Found ImageMagick at: {IM_PATH}")
else:
    print(f"⚠️ WARNING: Cannot find 'magick.exe' inside {IM_PATH}")
    print("👉 Go check that folder. Is there a file named 'magick.exe' or just 'magick'?")

def run_text_test():
    print("🎨 Testing Text Generation...")

    try:
        # Create background (Black, Vertical)
        background = ColorClip(size=(1080, 1920), color=(0,0,0), duration=3)

        # Create Text
        # We use method='caption' to wrap text automatically
        txt_clip = TextClip(
            "LAZYCUT\nIS WORKING", 
            fontsize=150, 
            color='white', 
            font='Arial',
            stroke_color='white', 
            stroke_width=2,
            size=(800, None), 
            method='caption'
        )
        
        txt_clip = txt_clip.set_position('center').set_duration(3)
        final = CompositeVideoClip([background, txt_clip])

        # Export
        final.write_videofile("test_caption_result.mp4", fps=24)
        print("\n✅ SUCCESS! Text Engine is READY.")

    except Exception as e:
        print("\n❌ TEXT FAILED!")
        print("Error:", e)

if __name__ == "__main__":
    run_text_test()