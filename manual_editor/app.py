"""
Manual Video Editor - Entry Point

A traditional timeline-based video editor for LazyCut.

Usage:
    # Run standalone
    python -m manual_editor.app
    
    # Or import and use
    from manual_editor.app import launch_manual_editor
    launch_manual_editor()

This module is completely independent from the AI automation pipeline.
"""

import sys
import os

# Ensure the parent directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def launch_manual_editor():
    """
    Launch the Manual Video Editor.
    
    Returns:
        Exit code from the application
    """
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette, QColor
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("LazyCut Manual Editor")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("LazyCut")
    
    # Enable high DPI scaling
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # Set dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 35))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(45, 45, 50))
    palette.setColor(QPalette.AlternateBase, QColor(50, 50, 55))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(60, 60, 65))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(66, 133, 244))
    palette.setColor(QPalette.Highlight, QColor(66, 133, 244))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    # Apply global stylesheet
    app.setStyleSheet("""
        QToolTip {
            color: #ffffff;
            background-color: #2d2d2d;
            border: 1px solid #444;
            padding: 4px;
        }
        QScrollBar:vertical {
            background: #2d2d2d;
            width: 12px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #555;
            min-height: 20px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical:hover {
            background: #666;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            background: #2d2d2d;
            height: 12px;
            margin: 0;
        }
        QScrollBar::handle:horizontal {
            background: #555;
            min-width: 20px;
            border-radius: 6px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #666;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0;
        }
    """)
    
    # Import and create main window
    from manual_editor.ui.main_window import MainWindow
    
    window = MainWindow()
    window.show()
    
    # Run event loop
    return app.exec()


def main():
    """Main entry point."""
    sys.exit(launch_manual_editor())


if __name__ == "__main__":
    main()
