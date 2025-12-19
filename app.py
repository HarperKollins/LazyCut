import customtkinter as ctk
import threading
import sys
if sys.platform.startswith("win"):
    import codecs
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
    except Exception: pass

import os
import logging
from tkinter import filedialog, messagebox, simpledialog
from core import LazyCutCore, LimitReachedException
from config import APP_NAME, VERSION, save_settings, load_settings
from updater import check_for_updates, download_and_install_update

# --- THEME CONFIG ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str_val):
        try:
            self.widget.configure(state="normal")
            # Filter out characters that might cause encoding issues in Tkinter/Console if needed
            # But usually Tkinter handles unicode fine. The error was in logging stream.
            # We just ensure we don't crash.
            self.widget.insert("end", str_val, (self.tag,))
            self.widget.see("end")
            self.widget.configure(state="disabled")
        except Exception:
            pass
        
    def flush(self):
        pass

class LazyCutApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.core = LazyCutCore()
        self.processing_thread = None
        self.selected_folder = None

        # Window Setup
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("900x650")
        self.resizable(True, True)
        
        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")

        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- 1. HEADER ---
        self.header_frame = ctk.CTkFrame(self, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        
        self.header_label = ctk.CTkLabel(
            self.header_frame, 
            text=f"{APP_NAME} v{VERSION}", 
            font=("Roboto Medium", 20)
        )
        self.header_label.pack(side="left", padx=20, pady=10)

        # Manual Editor Button
        self.btn_manual_editor = ctk.CTkButton(
            self.header_frame,
            text="🎬 Manual Editor",
            width=140,
            fg_color="#6c5ce7",
            text_color="white",
            hover_color="#5b4cdb",
            command=self.launch_manual_editor
        )
        self.btn_manual_editor.pack(side="right", padx=10, pady=10)

        # Auth Button
        self.btn_auth = ctk.CTkButton(
            self.header_frame,
            text="🔑 Login / Upgrade",
            width=120,
            fg_color="#E5B80B", # Gold color
            text_color="black",
            hover_color="#C49B09",
            command=self.open_auth_dialog
        )
        self.btn_auth.pack(side="right", padx=20, pady=10)

        # --- 2. CONTROLS ---
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        self.control_frame.grid_columnconfigure(1, weight=1)

        # Folder Selection
        self.btn_folder = ctk.CTkButton(
            self.control_frame, 
            text="Select Input Folder", 
            command=self.select_folder
        )
        self.btn_folder.grid(row=0, column=0, padx=10, pady=10)

        self.lbl_folder = ctk.CTkLabel(self.control_frame, text="No folder selected", text_color="gray")
        self.lbl_folder.grid(row=0, column=1, sticky="w", padx=10)

        # Settings
        self.check_captions = ctk.CTkCheckBox(self.control_frame, text="Pro Captions")
        self.check_captions.select()
        self.check_captions.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.check_broll = ctk.CTkCheckBox(self.control_frame, text="Smart B-Roll")
        self.check_broll.select()
        self.check_broll.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # Start Button
        self.btn_start = ctk.CTkButton(
            self.control_frame, 
            text="START PROCESSING", 
            fg_color="green", 
            hover_color="darkgreen",
            height=40,
            command=self.start_processing
        )
        self.btn_start.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=15)

        # --- 3. CONSOLE ---
        self.console_frame = ctk.CTkFrame(self)
        self.console_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        self.console_label = ctk.CTkLabel(self.console_frame, text="Log Console", anchor="w")
        self.console_label.pack(fill="x", padx=5, pady=5)
        
        self.console_text = ctk.CTkTextbox(self.console_frame, state="disabled", font=("Consolas", 12))
        self.console_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Redirect Stdout
        sys.stdout = TextRedirector(self.console_text, "stdout")
        sys.stderr = TextRedirector(self.console_text, "stderr")

        # --- 4. AUTO UPDATE CHECK ---
        self.after(1000, self.run_update_check)
        self.update_auth_status()

    def launch_manual_editor(self):
        """Launch the Manual Video Editor as a separate process."""
        import subprocess
        print("🎬 Launching Manual Editor...")
        try:
            subprocess.Popen(
                [sys.executable, "-m", "manual_editor.app"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            print("✅ Manual Editor launched successfully!")
        except Exception as e:
            print(f"❌ Failed to launch Manual Editor: {e}")
            messagebox.showerror("Error", f"Failed to launch Manual Editor:\n{e}")

    def update_auth_status(self):
        settings = load_settings()
        key = settings.get("license_key")
        if key:
            self.btn_auth.configure(text="👑 Pro Active", fg_color="green", text_color="white")
        else:
            self.btn_auth.configure(text="🔑 Login / Upgrade", fg_color="#E5B80B", text_color="black")

    def open_auth_dialog(self):
        key = simpledialog.askstring("License Key", "Enter your Pro License Key:")
        if key:
            save_settings("license_key", key.strip())
            messagebox.showinfo("Success", "License Key Saved!")
            self.update_auth_status()

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder = folder
            videos = [f for f in os.listdir(folder) if f.endswith('.mp4')]
            self.lbl_folder.configure(text=f"{folder} ({len(videos)} videos)", text_color="white")
            print(f"📂 Selected: {folder}")

    def log_callback(self, message):
        self.after(0, lambda: print(message))

    def start_processing(self):
        if not self.selected_folder:
            messagebox.showwarning("No Folder", "Please select an input folder first.")
            return

        if self.processing_thread and self.processing_thread.is_alive():
            return

        self.btn_start.configure(state="disabled", text="Processing...")
        
        self.processing_thread = threading.Thread(target=self.run_core)
        self.processing_thread.start()

    def run_core(self):
        try:
            self.core.run_pipeline(
                self.selected_folder,
                enable_captions=self.check_captions.get(),
                enable_broll=self.check_broll.get(),
                callback=self.log_callback
            )
        except LimitReachedException:
            self.after(0, lambda: messagebox.showwarning("Limit Reached", "🚫 Daily Limit Reached (4/4).\n\nPlease Upgrade to Pro for unlimited access."))
        except Exception as e:
            print(f"❌ Critical Error: {e}")
        finally:
            self.after(0, self.reset_ui)

    def reset_ui(self):
        self.btn_start.configure(state="normal", text="START PROCESSING")
        print("Done.")

    def run_update_check(self):
        def _check():
            avail, ver, url = check_for_updates()
            if avail:
                self.after(0, lambda: self.prompt_update(ver, url))
        
        threading.Thread(target=_check, daemon=True).start()

    def prompt_update(self, version, url):
        ans = messagebox.askyesno("Update Available", f"New version {version} is available. Update now?")
        if ans:
            print("⬇️ Downloading update...")
            threading.Thread(target=lambda: download_and_install_update(url, version), daemon=True).start()

if __name__ == "__main__":
    app = LazyCutApp()
    app.mainloop()
