import customtkinter as ctk
import threading
import logging
import sys
import os
from main import start_lazycut, logger
import updater

# Redirect logging to GUI
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert("end", msg + "\n")
            self.text_widget.see("end")
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)

class LazyCutApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LazyCut v2.0")
        self.geometry("800x600")
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # 1. Title
        self.label_title = ctk.CTkLabel(self, text="LazyCut v2.0", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10))

        # 2. File Selection
        self.frame_files = ctk.CTkFrame(self)
        self.frame_files.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_folder = ctk.CTkButton(self.frame_files, text="Select Video Folder", command=self.select_folder)
        self.btn_folder.grid(row=0, column=0, padx=10, pady=10)
        
        self.lbl_folder = ctk.CTkLabel(self.frame_files, text="Current Directory (Default)")
        self.lbl_folder.grid(row=0, column=1, padx=10, pady=10)
        
        self.selected_folder = None

        # 3. Toggles
        self.frame_toggles = ctk.CTkFrame(self)
        self.frame_toggles.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.var_captions = ctk.BooleanVar(value=True)
        self.chk_captions = ctk.CTkCheckBox(self.frame_toggles, text="Add Captions", variable=self.var_captions)
        self.chk_captions.grid(row=0, column=0, padx=20, pady=10)
        
        self.var_broll = ctk.BooleanVar(value=True)
        self.chk_broll = ctk.CTkCheckBox(self.frame_toggles, text="Add B-Roll", variable=self.var_broll)
        self.chk_broll.grid(row=0, column=1, padx=20, pady=10)

        # 4. Process Button & Progress
        self.btn_process = ctk.CTkButton(self, text="PROCESS VIDEO", font=ctk.CTkFont(size=18, weight="bold"), height=50, command=self.start_processing)
        self.btn_process.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.progress_bar.set(0)

        # 5. Console Log
        self.txt_log = ctk.CTkTextbox(self, width=760, height=200)
        self.txt_log.grid(row=4, column=0, padx=20, pady=10, sticky="nsew")
        self.txt_log.configure(state='disabled')
        
        # Setup Logging
        text_handler = TextHandler(self.txt_log)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)
        
        # --- AUTO UPDATE CHECK ---
        threading.Thread(target=updater.check_for_updates, daemon=True).start()

    def select_folder(self):
        self.label_title.configure(text="Please select the FOLDER containing your videos (files will be hidden)...")
        folder = ctk.filedialog.askdirectory(title="Select Folder containing MP4s")
        
        if folder:
            self.selected_folder = folder
            # Count files
            try:
                video_files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov'))]
                self.lbl_folder.configure(text=f"✅ Found {len(video_files)} videos in: {os.path.basename(folder)}")
            except Exception as e:
                self.lbl_folder.configure(text=f"Error reading folder: {e}")
            
            self.label_title.configure(text="LazyCut v2.0")
        else:
            self.label_title.configure(text="LazyCut v2.0")

    def update_progress(self, msg):
        # Simple progress updates
        self.txt_log.after(0, lambda: self.label_title.configure(text=f"LazyCut v2.0 - {msg}"))
        if "Processing" in msg: self.progress_bar.set(0.3)
        elif "Editing" in msg: self.progress_bar.set(0.6)
        elif "Rendering" in msg: self.progress_bar.set(0.9)
        elif "Done" in msg: self.progress_bar.set(1.0)

    def start_processing(self):
        self.btn_process.configure(state="disabled")
        self.progress_bar.set(0.1)
        
        thread = threading.Thread(target=self.run_lazycut)
        thread.start()

    def run_lazycut(self):
        try:
            start_lazycut(
                target_folder=self.selected_folder,
                enable_captions=self.var_captions.get(),
                enable_broll=self.var_broll.get(),
                progress_callback=self.update_progress
            )
        except Exception as e:
            logger.error(f"GUI Error: {e}")
        finally:
            self.btn_process.configure(state="normal")
            self.progress_bar.set(0)

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = LazyCutApp()
    app.mainloop()
