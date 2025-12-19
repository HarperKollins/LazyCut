"""
Export Module

Orchestrates the export process from timeline to final video.
Handles progress reporting and cleanup.
"""

import os
import subprocess
import threading
import tempfile
import re
from typing import Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QThread

from manual_editor.export.ffmpeg_graph import (
    FFmpegGraphBuilder, 
    ExportSettings
)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from shared.ffmpeg_utils import get_ffmpeg_path
from shared.project_io import export_srt

if TYPE_CHECKING:
    from manual_editor.models.project import Project


class ExportWorker(QThread):
    """
    Worker thread for video export.
    
    Runs the FFmpeg process in a separate thread to keep
    the UI responsive during export.
    
    Signals:
        progress: Export progress (0.0 to 1.0)
        status: Status message
        finished: Export complete (success, error_message)
    """
    
    progress = Signal(float)
    status = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(
        self,
        project: "Project",
        output_path: str,
        settings: Optional[ExportSettings] = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.project = project
        self.output_path = output_path
        self.settings = settings or ExportSettings(output_path=output_path)
        
        self._cancelled = False
        self._process: Optional[subprocess.Popen] = None
    
    def run(self) -> None:
        """Execute the export process."""
        try:
            self.status.emit("Preparing export...")
            self.progress.emit(0.0)
            
            # Create temp directory for intermediate files
            temp_dir = tempfile.mkdtemp(prefix="lazycut_export_")
            srt_path = None
            
            # Export subtitles if any
            if self.project.subtitles:
                self.status.emit("Generating subtitles...")
                srt_path = os.path.join(temp_dir, "subtitles.srt")
                export_srt(self.project.subtitles, srt_path)
            
            # Build FFmpeg command
            self.status.emit("Building export graph...")
            builder = FFmpegGraphBuilder()
            
            try:
                cmd, temp_files = builder.build_export_command(
                    self.project,
                    self.settings,
                    srt_path
                )
            except ValueError as e:
                self.finished.emit(False, str(e))
                return
            
            # Calculate total duration for progress
            total_duration = self.project.duration
            
            # Run FFmpeg
            self.status.emit("Encoding video...")
            self.progress.emit(0.05)
            
            # Replace ffmpeg path
            cmd[0] = get_ffmpeg_path()
            
            # Add progress output
            cmd.insert(1, "-progress")
            cmd.insert(2, "pipe:1")
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            
            # Parse progress from FFmpeg output
            current_time = 0.0
            
            while True:
                if self._cancelled:
                    self._process.terminate()
                    self.finished.emit(False, "Export cancelled")
                    return
                
                line = self._process.stdout.readline()
                if not line:
                    break
                
                # Parse progress lines
                if line.startswith("out_time_ms="):
                    try:
                        time_ms = int(line.split("=")[1])
                        current_time = time_ms / 1_000_000
                        if total_duration > 0:
                            progress = min(0.95, 0.05 + (current_time / total_duration) * 0.9)
                            self.progress.emit(progress)
                    except (ValueError, IndexError):
                        pass
                
                elif line.startswith("progress="):
                    if "end" in line:
                        break
            
            # Wait for process to finish
            return_code = self._process.wait()
            
            # Cleanup
            builder.cleanup()
            
            if return_code == 0:
                self.progress.emit(1.0)
                self.status.emit("Export complete!")
                self.finished.emit(True, "")
            else:
                stderr = self._process.stderr.read()
                self.finished.emit(False, f"FFmpeg error: {stderr[:500]}")
        
        except Exception as e:
            self.finished.emit(False, str(e))
    
    def cancel(self) -> None:
        """Cancel the export process."""
        self._cancelled = True
        if self._process:
            self._process.terminate()


class Exporter(QObject):
    """
    High-level export interface.
    
    Usage:
        exporter = Exporter()
        exporter.progress.connect(update_progress_bar)
        exporter.finished.connect(on_export_complete)
        exporter.export(project, "/path/to/output.mp4")
    
    Signals:
        progress: Export progress (0.0 to 1.0)
        status: Status message
        finished: Export complete (success, output_path_or_error)
    """
    
    progress = Signal(float)
    status = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._worker: Optional[ExportWorker] = None
    
    def export(
        self,
        project: "Project",
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        quality: int = 18,
        burn_subtitles: bool = True
    ) -> None:
        """
        Start the export process.
        
        Args:
            project: Project to export
            output_path: Output file path
            width: Output width
            height: Output height
            fps: Output frame rate
            quality: Video quality (CRF, lower = better)
            burn_subtitles: Whether to burn subtitles into video
        """
        if self._worker and self._worker.isRunning():
            return
        
        settings = ExportSettings(
            output_path=output_path,
            width=width,
            height=height,
            fps=fps,
            video_crf=quality,
            burn_subtitles=burn_subtitles
        )
        
        self._worker = ExportWorker(project, output_path, settings)
        self._worker.progress.connect(self.progress)
        self._worker.status.connect(self.status)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
    
    def cancel(self) -> None:
        """Cancel the current export."""
        if self._worker:
            self._worker.cancel()
    
    def is_exporting(self) -> bool:
        """Check if an export is in progress."""
        return self._worker is not None and self._worker.isRunning()
    
    def _on_finished(self, success: bool, message: str) -> None:
        """Handle export completion."""
        if success:
            self.finished.emit(True, self._worker.output_path)
        else:
            self.finished.emit(False, message)
