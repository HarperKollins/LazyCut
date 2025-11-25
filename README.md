# LazyCut v2.0

LazyCut is an automated video editing tool that uses AI to create professional clips from raw footage.

## Features
- **AI Editing**: Uses Gemini 2.5 Pro to curate narratives.
- **Auto-Captions**: "Hormozi-style" animated captions.
- **Smart B-Roll**: Context-aware B-roll injection.
- **Cross-Platform**: Runs on Windows and Linux.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/HarperKollins/LazyCut.git
   cd LazyCut
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install ImageMagick (Required for Captions):**
   - **Windows:** Download and install from [ImageMagick.org](https://imagemagick.org/script/download.php#windows). Ensure `magick.exe` is in your PATH.
   - **Linux:** `sudo apt-get install imagemagick`

4. **Setup API Keys:**
   - Create a `.env` file in the root directory:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

## Usage

Run the GUI application:
```bash
python app.py
```

1. Select your input folder containing `.mp4` files.
2. Toggle "Pro Captions" and "Smart B-Roll" as desired.
3. Click **START PROCESSING**.
4. The final video will be saved in the input folder as `FINAL_HUMAN_EDIT.mp4`.

## Troubleshooting
- **ImageMagick Error:** Ensure ImageMagick is installed and accessible. On Linux, you might need to edit `/etc/ImageMagick-6/policy.xml` to allow PDF/Text operations if restricted.
- **FFmpeg Error:** `moviepy` should install a binary, but if it fails, install ffmpeg system-wide.

## License
MIT
