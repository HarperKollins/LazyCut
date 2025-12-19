"""
Subtitle Editor Widget

Panel for adding and editing subtitles manually.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QDoubleSpinBox, QListWidget,
    QListWidgetItem, QFrame, QTextEdit, QSplitter,
    QGroupBox, QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from manual_editor.models.project import Project, Subtitle


class SubtitleEditor(QWidget):
    """
    Subtitle editing panel.
    
    Features:
    - Add/Edit/Delete subtitles
    - Text input
    - Start time and duration controls
    - List of all subtitles
    
    Signals:
        subtitle_added: Emitted when a subtitle is added (Subtitle)
        subtitle_updated: Emitted when a subtitle is updated (subtitle_id, text, start, duration)
        subtitle_deleted: Emitted when a subtitle is deleted (subtitle_id)
        subtitle_selected: Emitted when a subtitle is selected (subtitle_id)
    """
    
    subtitle_added = Signal(object)  # Subtitle
    subtitle_updated = Signal(str, str, float, float)  # id, text, start, duration
    subtitle_deleted = Signal(str)  # id
    subtitle_selected = Signal(str)  # id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.project: Optional["Project"] = None
        self._current_subtitle_id: Optional[str] = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("📝 Subtitles")
        header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #fff;
            padding: 5px;
        """)
        layout.addWidget(header)
        
        # Editor group
        editor_group = QGroupBox("Edit Subtitle")
        editor_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                color: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        editor_layout = QVBoxLayout(editor_group)
        
        # Text input
        text_label = QLabel("Text:")
        text_label.setStyleSheet("color: #ccc;")
        editor_layout.addWidget(text_label)
        
        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(80)
        self.text_input.setPlaceholderText("Enter subtitle text...")
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        editor_layout.addWidget(self.text_input)
        
        # Time controls
        time_layout = QHBoxLayout()
        
        # Start time
        start_frame = QVBoxLayout()
        start_label = QLabel("Start (sec):")
        start_label.setStyleSheet("color: #ccc; font-size: 11px;")
        start_frame.addWidget(start_label)
        
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0, 36000)  # Up to 10 hours
        self.start_spin.setDecimals(2)
        self.start_spin.setSingleStep(0.1)
        self.start_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        start_frame.addWidget(self.start_spin)
        time_layout.addLayout(start_frame)
        
        # Duration
        duration_frame = QVBoxLayout()
        duration_label = QLabel("Duration (sec):")
        duration_label.setStyleSheet("color: #ccc; font-size: 11px;")
        duration_frame.addWidget(duration_label)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 60)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setValue(3.0)
        self.duration_spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        duration_frame.addWidget(self.duration_spin)
        time_layout.addLayout(duration_frame)
        
        editor_layout.addLayout(time_layout)
        
        # Use current time button
        self.btn_use_current = QPushButton("📍 Use Playhead Time")
        self.btn_use_current.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #fff;
                border: none;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        editor_layout.addWidget(self.btn_use_current)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ Add")
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #5CBF60;
            }
        """)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_update = QPushButton("✏️ Update")
        self.btn_update.setEnabled(False)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #42A6F3;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        btn_layout.addWidget(self.btn_update)
        
        self.btn_delete = QPushButton("🗑️ Delete")
        self.btn_delete.setEnabled(False)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f55346;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        btn_layout.addWidget(self.btn_delete)
        
        editor_layout.addLayout(btn_layout)
        layout.addWidget(editor_group)
        
        # Subtitle list
        list_label = QLabel("Subtitle List:")
        list_label.setStyleSheet("color: #ccc; margin-top: 10px;")
        layout.addWidget(list_label)
        
        self.subtitle_list = QListWidget()
        self.subtitle_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: #fff;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #4285f4;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
        layout.addWidget(self.subtitle_list, stretch=1)
        
        # Clear button
        self.btn_clear = QPushButton("Clear Selection")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        layout.addWidget(self.btn_clear)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.btn_add.clicked.connect(self._on_add_clicked)
        self.btn_update.clicked.connect(self._on_update_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_clear.clicked.connect(self._clear_selection)
        self.subtitle_list.itemClicked.connect(self._on_item_clicked)
        self.subtitle_list.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def set_project(self, project: "Project") -> None:
        """Set the project and refresh the list."""
        self.project = project
        self.refresh_list()
    
    def set_current_time(self, time_seconds: float) -> None:
        """Update the start time spinner to the current playhead time."""
        self.start_spin.setValue(time_seconds)
    
    def refresh_list(self) -> None:
        """Refresh the subtitle list from the project."""
        self.subtitle_list.clear()
        
        if not self.project:
            return
        
        # Sort subtitles by start time
        subtitles = sorted(self.project.subtitles, key=lambda s: s.start_time)
        
        for sub in subtitles:
            # Format: [00:05 - 00:08] "Hello world"
            start = self._format_time(sub.start_time)
            end = self._format_time(sub.start_time + sub.duration)
            text_preview = sub.text[:30] + "..." if len(sub.text) > 30 else sub.text
            
            item = QListWidgetItem(f"[{start} - {end}] \"{text_preview}\"")
            item.setData(Qt.UserRole, sub.id)
            self.subtitle_list.addItem(item)
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        from manual_editor.models.project import Subtitle
        
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Please enter subtitle text.")
            return
        
        subtitle = Subtitle.create_new(
            text=text,
            start_time=self.start_spin.value(),
            duration=self.duration_spin.value()
        )
        
        self.subtitle_added.emit(subtitle)
        
        # Clear form
        self.text_input.clear()
        self.refresh_list()
    
    def _on_update_clicked(self) -> None:
        """Handle update button click."""
        if not self._current_subtitle_id:
            return
        
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Please enter subtitle text.")
            return
        
        self.subtitle_updated.emit(
            self._current_subtitle_id,
            text,
            self.start_spin.value(),
            self.duration_spin.value()
        )
        
        self.refresh_list()
    
    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        if not self._current_subtitle_id:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this subtitle?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.subtitle_deleted.emit(self._current_subtitle_id)
            self._clear_selection()
            self.refresh_list()
    
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle subtitle item selection."""
        subtitle_id = item.data(Qt.UserRole)
        self._current_subtitle_id = subtitle_id
        
        # Enable edit buttons
        self.btn_update.setEnabled(True)
        self.btn_delete.setEnabled(True)
        
        # Load subtitle into form
        if self.project:
            subtitle = self.project.get_subtitle_by_id(subtitle_id)
            if subtitle:
                self.text_input.setPlainText(subtitle.text)
                self.start_spin.setValue(subtitle.start_time)
                self.duration_spin.setValue(subtitle.duration)
        
        self.subtitle_selected.emit(subtitle_id)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click to seek to subtitle time."""
        subtitle_id = item.data(Qt.UserRole)
        if self.project:
            subtitle = self.project.get_subtitle_by_id(subtitle_id)
            if subtitle:
                self.subtitle_selected.emit(subtitle_id)
    
    def _clear_selection(self) -> None:
        """Clear the current selection."""
        self._current_subtitle_id = None
        self.subtitle_list.clearSelection()
        self.btn_update.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.text_input.clear()
        self.start_spin.setValue(0)
        self.duration_spin.setValue(3.0)
