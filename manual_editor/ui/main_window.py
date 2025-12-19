"""
Main Window for Manual Video Editor

The central window that integrates all components:
- Preview panel
- Timeline
- Media browser
- Subtitle editor
- Menu bar with shortcuts
"""

import os
import sys
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QFileDialog, QMessageBox,
    QDockWidget, QStatusBar, QProgressBar, QLabel,
    QApplication, QToolBar, QPushButton
)
from PySide6.QtCore import Qt, QSettings, Slot
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent, QIcon

# Local imports
from manual_editor.models.project import Project, Clip, AudioClip, Subtitle
from manual_editor.models.commands import (
    CommandHistory, AddClipCommand, DeleteClipCommand,
    MoveClipCommand, SplitClipCommand, AddSubtitleCommand,
    DeleteSubtitleCommand, EditSubtitleCommand
)
from manual_editor.ui.timeline_widget import TimelineWidget
from manual_editor.ui.preview_widget import PreviewWidget
from manual_editor.ui.subtitle_editor import SubtitleEditor
from manual_editor.export.exporter import Exporter

# Add shared to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.project_io import save_project, load_project
from shared.ffmpeg_utils import get_video_metadata


class MainWindow(QMainWindow):
    """
    Main application window for the Manual Video Editor.
    
    Layout:
        ┌───────────────────────────────────────────────────┐
        │ Menu Bar                                          │
        ├─────────────────────────┬─────────────────────────┤
        │                         │                         │
        │   Video Preview         │   Subtitle Editor       │
        │                         │                         │
        ├─────────────────────────┴─────────────────────────┤
        │                                                   │
        │                    Timeline                       │
        │                                                   │
        └───────────────────────────────────────────────────┘
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State
        self.project = Project("Untitled")
        self.command_history = CommandHistory()
        self.exporter = Exporter(self)
        self._unsaved_changes = False
        self._current_file: Optional[str] = None
        
        # Setup
        self._setup_window()
        self._setup_menu_bar()
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()
        
        # Load settings
        self._load_settings()
    
    def _setup_window(self) -> None:
        """Configure main window properties."""
        self.setWindowTitle("LazyCut Manual Editor - Untitled")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 850)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QMenuBar {
                background-color: #2d2d2d;
                color: #fff;
                padding: 4px;
            }
            QMenuBar::item:selected {
                background-color: #4285f4;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #fff;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #4285f4;
            }
            QToolBar {
                background-color: #2d2d2d;
                border: none;
                spacing: 3px;
                padding: 3px;
            }
            QStatusBar {
                background-color: #2d2d2d;
                color: #999;
            }
            QSplitter::handle {
                background-color: #444;
            }
            QDockWidget {
                color: #fff;
            }
            QDockWidget::title {
                background-color: #2d2d2d;
                padding: 6px;
            }
        """)
    
    def _setup_menu_bar(self) -> None:
        """Create menu bar with all menus and actions."""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        self.action_new = file_menu.addAction("New Project")
        self.action_new.setShortcut(QKeySequence.New)
        self.action_new.triggered.connect(self._on_new_project)
        
        self.action_open = file_menu.addAction("Open Project...")
        self.action_open.setShortcut(QKeySequence.Open)
        self.action_open.triggered.connect(self._on_open_project)
        
        file_menu.addSeparator()
        
        self.action_save = file_menu.addAction("Save")
        self.action_save.setShortcut(QKeySequence.Save)
        self.action_save.triggered.connect(self._on_save_project)
        
        self.action_save_as = file_menu.addAction("Save As...")
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.triggered.connect(self._on_save_project_as)
        
        file_menu.addSeparator()
        
        self.action_import = file_menu.addAction("Import Media...")
        self.action_import.setShortcut(QKeySequence("Ctrl+I"))
        self.action_import.triggered.connect(self._on_import_media)
        
        file_menu.addSeparator()
        
        self.action_export = file_menu.addAction("Export Video...")
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.triggered.connect(self._on_export)
        
        file_menu.addSeparator()
        
        self.action_exit = file_menu.addAction("Exit")
        self.action_exit.setShortcut(QKeySequence.Quit)
        self.action_exit.triggered.connect(self.close)
        
        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        
        self.action_undo = edit_menu.addAction("Undo")
        self.action_undo.setShortcut(QKeySequence.Undo)
        self.action_undo.triggered.connect(self._on_undo)
        
        self.action_redo = edit_menu.addAction("Redo")
        self.action_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        self.action_redo.triggered.connect(self._on_redo)
        
        edit_menu.addSeparator()
        
        self.action_delete = edit_menu.addAction("Delete Selected")
        self.action_delete.setShortcut(QKeySequence.Delete)
        self.action_delete.triggered.connect(self._on_delete_selected)
        
        self.action_split = edit_menu.addAction("Split at Playhead")
        self.action_split.setShortcut(QKeySequence("S"))
        self.action_split.triggered.connect(self._on_split_at_playhead)
        
        # View Menu
        view_menu = menubar.addMenu("&View")
        
        self.action_zoom_in = view_menu.addAction("Zoom In")
        self.action_zoom_in.setShortcut(QKeySequence("="))
        self.action_zoom_in.triggered.connect(lambda: self.timeline.view.zoom_in())
        
        self.action_zoom_out = view_menu.addAction("Zoom Out")
        self.action_zoom_out.setShortcut(QKeySequence("-"))
        self.action_zoom_out.triggered.connect(lambda: self.timeline.view.zoom_out())
        
        view_menu.addSeparator()
        
        self.action_fit_timeline = view_menu.addAction("Fit Timeline")
        self.action_fit_timeline.setShortcut(QKeySequence("0"))
        
        # Playback Menu
        playback_menu = menubar.addMenu("&Playback")
        
        self.action_play_pause = playback_menu.addAction("Play/Pause")
        self.action_play_pause.setShortcut(QKeySequence("Space"))
        self.action_play_pause.triggered.connect(self._on_toggle_playback)
        
        self.action_stop = playback_menu.addAction("Stop")
        self.action_stop.triggered.connect(self._on_stop)
        
        playback_menu.addSeparator()
        
        self.action_prev_frame = playback_menu.addAction("Previous Frame")
        self.action_prev_frame.setShortcut(QKeySequence("Left"))
        self.action_prev_frame.triggered.connect(lambda: self.preview.engine.seek_relative(-0.033))
        
        self.action_next_frame = playback_menu.addAction("Next Frame")
        self.action_next_frame.setShortcut(QKeySequence("Right"))
        self.action_next_frame.triggered.connect(lambda: self.preview.engine.seek_relative(0.033))
        
        self.action_prev_second = playback_menu.addAction("Previous Second")
        self.action_prev_second.setShortcut(QKeySequence("Shift+Left"))
        self.action_prev_second.triggered.connect(lambda: self.preview.engine.seek_relative(-1.0))
        
        self.action_next_second = playback_menu.addAction("Next Second")
        self.action_next_second.setShortcut(QKeySequence("Shift+Right"))
        self.action_next_second.triggered.connect(lambda: self.preview.engine.seek_relative(1.0))
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        self.action_about = help_menu.addAction("About")
        self.action_about.triggered.connect(self._on_about)
        
        self.action_shortcuts = help_menu.addAction("Keyboard Shortcuts")
        self.action_shortcuts.triggered.connect(self._on_show_shortcuts)
    
    def _setup_ui(self) -> None:
        """Create and arrange UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create splitters for resizable panels
        main_splitter = QSplitter(Qt.Vertical)
        
        # Top section: Preview + Subtitle Editor
        top_splitter = QSplitter(Qt.Horizontal)
        
        # Preview widget
        self.preview = PreviewWidget()
        top_splitter.addWidget(self.preview)
        
        # Subtitle editor in a dock-like container
        subtitle_container = QWidget()
        subtitle_layout = QVBoxLayout(subtitle_container)
        subtitle_layout.setContentsMargins(0, 0, 0, 0)
        self.subtitle_editor = SubtitleEditor()
        subtitle_layout.addWidget(self.subtitle_editor)
        top_splitter.addWidget(subtitle_container)
        
        # Set initial sizes (70/30 split)
        top_splitter.setSizes([700, 300])
        
        main_splitter.addWidget(top_splitter)
        
        # Bottom section: Timeline
        self.timeline = TimelineWidget()
        main_splitter.addWidget(self.timeline)
        
        # Set initial sizes (60/40 split)
        main_splitter.setSizes([400, 300])
        
        main_layout.addWidget(main_splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Initialize with project
        self.timeline.set_project(self.project)
        self.subtitle_editor.set_project(self.project)
    
    def _setup_shortcuts(self) -> None:
        """Setup additional keyboard shortcuts."""
        # Most shortcuts are in the menu bar, but we can add more here
        pass
    
    def _connect_signals(self) -> None:
        """Connect component signals."""
        # Timeline signals
        self.timeline.time_changed.connect(self._on_timeline_time_changed)
        self.timeline.clip_deleted.connect(self._on_clip_delete_requested)
        self.timeline.clip_split_requested.connect(self._on_clip_split_requested)
        
        # Preview signals
        self.preview.position_changed.connect(self._on_preview_position_changed)
        
        # Subtitle editor signals
        self.subtitle_editor.subtitle_added.connect(self._on_subtitle_added)
        self.subtitle_editor.subtitle_updated.connect(self._on_subtitle_updated)
        self.subtitle_editor.subtitle_deleted.connect(self._on_subtitle_deleted)
        self.subtitle_editor.btn_use_current.clicked.connect(
            lambda: self.subtitle_editor.set_current_time(self.timeline.get_playhead_time())
        )
        
        # Exporter signals
        self.exporter.progress.connect(self._on_export_progress)
        self.exporter.status.connect(self._on_export_status)
        self.exporter.finished.connect(self._on_export_finished)
    
    # ========================================================================
    # File Operations
    # ========================================================================
    
    def _on_new_project(self) -> None:
        """Create a new project."""
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before creating a new project?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self._on_save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        self.project = Project("Untitled")
        self.command_history.clear()
        self._current_file = None
        self._unsaved_changes = False
        self._update_title()
        
        self.timeline.set_project(self.project)
        self.subtitle_editor.set_project(self.project)
        self.status_label.setText("New project created")
    
    def _on_open_project(self) -> None:
        """Open an existing project."""
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before opening another project?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self._on_save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project",
            "", "LazyCut Project (*.lcproj)"
        )
        
        if file_path:
            try:
                self.project = load_project(file_path)
                self.command_history.clear()
                self._current_file = file_path
                self._unsaved_changes = False
                self._update_title()
                
                self.timeline.set_project(self.project)
                self.subtitle_editor.set_project(self.project)
                self.status_label.setText(f"Opened: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")
    
    def _on_save_project(self) -> None:
        """Save the current project."""
        if self._current_file:
            self._save_to_file(self._current_file)
        else:
            self._on_save_project_as()
    
    def _on_save_project_as(self) -> None:
        """Save project to a new file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As",
            f"{self.project.name}.lcproj",
            "LazyCut Project (*.lcproj)"
        )
        
        if file_path:
            if not file_path.endswith(".lcproj"):
                file_path += ".lcproj"
            self._save_to_file(file_path)
    
    def _save_to_file(self, file_path: str) -> None:
        """Save project to specified file."""
        try:
            save_project(self.project, file_path)
            self._current_file = file_path
            self._unsaved_changes = False
            self._update_title()
            self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")
    
    def _on_import_media(self) -> None:
        """Import media files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Media",
            "",
            "Video Files (*.mp4 *.mov *.avi *.mkv);;Audio Files (*.mp3 *.wav *.aac);;All Files (*)"
        )
        
        for file_path in files:
            self._import_file(file_path)
    
    def _import_file(self, file_path: str) -> None:
        """Import a single media file and add to timeline."""
        if not os.path.exists(file_path):
            return
        
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                # Video file
                metadata = get_video_metadata(file_path)
                
                # Create clip
                clip = Clip.create_new(
                    source_file=file_path,
                    in_time=0,
                    out_time=metadata.duration,
                    timeline_start=self.project.duration,  # Add at end
                    track_index=0
                )
                
                # Add via command for undo support
                cmd = AddClipCommand(self.project, clip)
                self.command_history.execute(cmd)
                
                # Set as preview source
                self.preview.set_source(file_path)
                
                self._mark_unsaved()
                self.timeline.refresh()
                self.status_label.setText(f"Imported: {os.path.basename(file_path)}")
                
            elif ext in ['.mp3', '.wav', '.aac', '.m4a']:
                # Audio file - would need audio metadata
                self.status_label.setText(f"Audio import not yet implemented")
                
        except Exception as e:
            QMessageBox.warning(self, "Import Error", f"Failed to import file:\n{e}")
    
    def _on_export(self) -> None:
        """Export the project to video."""
        if not self.project.get_all_clips():
            QMessageBox.warning(self, "No Content", "There are no clips to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Video",
            f"{self.project.name}.mp4",
            "MP4 Video (*.mp4)"
        )
        
        if file_path:
            if not file_path.endswith(".mp4"):
                file_path += ".mp4"
            
            self.progress_bar.show()
            self.progress_bar.setValue(0)
            self.exporter.export(self.project, file_path)
    
    def _on_export_progress(self, progress: float) -> None:
        """Handle export progress update."""
        self.progress_bar.setValue(int(progress * 100))
    
    def _on_export_status(self, status: str) -> None:
        """Handle export status update."""
        self.status_label.setText(status)
    
    def _on_export_finished(self, success: bool, message: str) -> None:
        """Handle export completion."""
        self.progress_bar.hide()
        
        if success:
            QMessageBox.information(
                self, "Export Complete",
                f"Video exported successfully to:\n{message}"
            )
            self.status_label.setText("Export complete")
        else:
            QMessageBox.critical(self, "Export Failed", message)
            self.status_label.setText("Export failed")
    
    # ========================================================================
    # Edit Operations
    # ========================================================================
    
    def _on_undo(self) -> None:
        """Undo last action."""
        cmd = self.command_history.undo()
        if cmd:
            self.timeline.refresh()
            self.subtitle_editor.refresh_list()
            self.status_label.setText(f"Undid: {cmd.description}")
            self._mark_unsaved()
        self._update_undo_redo_state()
    
    def _on_redo(self) -> None:
        """Redo last undone action."""
        cmd = self.command_history.redo()
        if cmd:
            self.timeline.refresh()
            self.subtitle_editor.refresh_list()
            self.status_label.setText(f"Redid: {cmd.description}")
            self._mark_unsaved()
        self._update_undo_redo_state()
    
    def _update_undo_redo_state(self) -> None:
        """Update undo/redo action enabled state."""
        self.action_undo.setEnabled(self.command_history.can_undo())
        self.action_redo.setEnabled(self.command_history.can_redo())
        
        undo_desc = self.command_history.get_undo_description()
        redo_desc = self.command_history.get_redo_description()
        
        self.action_undo.setText(f"Undo {undo_desc}" if undo_desc else "Undo")
        self.action_redo.setText(f"Redo {redo_desc}" if redo_desc else "Redo")
    
    def _on_delete_selected(self) -> None:
        """Delete the currently selected clip."""
        # Get selected item from timeline
        scene = self.timeline.view._scene
        selected_items = scene.selectedItems()
        
        for item in selected_items:
            if hasattr(item, 'clip_id'):
                self._on_clip_delete_requested(item.clip_id)
                break
    
    def _on_split_at_playhead(self) -> None:
        """Split selected clip at playhead position."""
        playhead_time = self.timeline.get_playhead_time()
        
        # Find clip under playhead
        clips = self.project.get_clips_at_time(playhead_time)
        if clips:
            clip = clips[0]
            cmd = SplitClipCommand(self.project, clip.id, playhead_time)
            if self.command_history.execute(cmd):
                self.timeline.refresh()
                self._mark_unsaved()
                self.status_label.setText("Clip split at playhead")
    
    def _on_clip_delete_requested(self, clip_id: str) -> None:
        """Handle clip deletion request."""
        cmd = DeleteClipCommand(self.project, clip_id)
        if self.command_history.execute(cmd):
            self.timeline.refresh()
            self._mark_unsaved()
            self.status_label.setText("Clip deleted")
            self._update_undo_redo_state()
    
    def _on_clip_split_requested(self, clip_id: str) -> None:
        """Handle clip split request from context menu."""
        playhead_time = self.timeline.get_playhead_time()
        cmd = SplitClipCommand(self.project, clip_id, playhead_time)
        if self.command_history.execute(cmd):
            self.timeline.refresh()
            self._mark_unsaved()
            self.status_label.setText("Clip split")
            self._update_undo_redo_state()
    
    # ========================================================================
    # Playback Operations
    # ========================================================================
    
    def _on_toggle_playback(self) -> None:
        """Toggle play/pause."""
        self.preview.engine.toggle_playback()
    
    def _on_stop(self) -> None:
        """Stop playback."""
        self.preview.engine.stop()
    
    def _on_timeline_time_changed(self, time: float) -> None:
        """Handle timeline playhead change."""
        self.preview.seek(time)
    
    def _on_preview_position_changed(self, time: float) -> None:
        """Handle preview position change."""
        self.timeline.set_playhead_time(time)
    
    # ========================================================================
    # Subtitle Operations
    # ========================================================================
    
    def _on_subtitle_added(self, subtitle: Subtitle) -> None:
        """Handle subtitle added."""
        cmd = AddSubtitleCommand(self.project, subtitle)
        if self.command_history.execute(cmd):
            self._mark_unsaved()
            self._update_undo_redo_state()
    
    def _on_subtitle_updated(self, sub_id: str, text: str, start: float, duration: float) -> None:
        """Handle subtitle update."""
        cmd = EditSubtitleCommand(
            self.project, sub_id,
            new_text=text,
            new_start_time=start,
            new_duration=duration
        )
        if self.command_history.execute(cmd):
            self._mark_unsaved()
            self._update_undo_redo_state()
    
    def _on_subtitle_deleted(self, sub_id: str) -> None:
        """Handle subtitle deletion."""
        cmd = DeleteSubtitleCommand(self.project, sub_id)
        if self.command_history.execute(cmd):
            self._mark_unsaved()
            self._update_undo_redo_state()
    
    # ========================================================================
    # Help
    # ========================================================================
    
    def _on_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self, "About LazyCut Manual Editor",
            "<h2>LazyCut Manual Editor</h2>"
            "<p>Version 1.0.0</p>"
            "<p>A traditional timeline-based video editor.</p>"
            "<p>Part of the LazyCut video editing suite.</p>"
        )
    
    def _on_show_shortcuts(self) -> None:
        """Show keyboard shortcuts dialog."""
        shortcuts = """
        <h3>Keyboard Shortcuts</h3>
        <table>
        <tr><td><b>Space</b></td><td>Play / Pause</td></tr>
        <tr><td><b>S</b></td><td>Split clip at playhead</td></tr>
        <tr><td><b>Delete</b></td><td>Delete selected clip</td></tr>
        <tr><td><b>← / →</b></td><td>Move playhead by frame</td></tr>
        <tr><td><b>Shift + ← / →</b></td><td>Move playhead by 1 second</td></tr>
        <tr><td><b>Ctrl + Z</b></td><td>Undo</td></tr>
        <tr><td><b>Ctrl + Shift + Z</b></td><td>Redo</td></tr>
        <tr><td><b>Ctrl + S</b></td><td>Save project</td></tr>
        <tr><td><b>Ctrl + O</b></td><td>Open project</td></tr>
        <tr><td><b>Ctrl + I</b></td><td>Import media</td></tr>
        <tr><td><b>Ctrl + E</b></td><td>Export video</td></tr>
        <tr><td><b>+ / -</b></td><td>Zoom timeline</td></tr>
        </table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)
    
    # ========================================================================
    # Utility
    # ========================================================================
    
    def _mark_unsaved(self) -> None:
        """Mark project as having unsaved changes."""
        self._unsaved_changes = True
        self._update_title()
    
    def _update_title(self) -> None:
        """Update window title."""
        title = f"LazyCut Manual Editor - {self.project.name}"
        if self._unsaved_changes:
            title += " *"
        self.setWindowTitle(title)
    
    def _load_settings(self) -> None:
        """Load window settings."""
        settings = QSettings("LazyCut", "ManualEditor")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)
    
    def _save_settings(self) -> None:
        """Save window settings."""
        settings = QSettings("LazyCut", "ManualEditor")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close."""
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self._on_save_project()
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        self._save_settings()
        event.accept()
