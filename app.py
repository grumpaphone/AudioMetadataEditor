#!/usr/bin/env python3
"""
Audio Metadata Editor application.

This application allows users to read, view, and edit metadata of WAV audio files.
It features a drag-and-drop interface, advanced metadata editing with undo/redo,
background agents for auto-save and file monitoring, parallel processing for
fast file operations, real-time search and filtering, and file organization tools.
"""
import sys
import os
import re
import shutil
import multiprocessing
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget, QFileDialog,
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView,
                             QLineEdit, QLabel, QComboBox, QGroupBox, QFormLayout,
                             QDialog, QSplitter, QFrame,
                             QStyle, QStyledItemDelegate,
                             QCheckBox, QProgressDialog,
                             QMenu, QScrollArea, QTabWidget)
from PyQt6.QtCore import (Qt, QTimer, QPoint,
                          QThread, pyqtSignal, QFileSystemWatcher, QObject)
from PyQt6.QtGui import (QColor, QIcon,
                         QPen, QAction, QKeySequence, QShortcut)

from mirror_panel import MirrorPanel
import wav_metadata


class UndoRedoCommand:
    """Base class for undo/redo commands."""
    def __init__(self, description):
        self.description = description
    def execute(self): # TODO: Add docstring
        pass
    def undo(self): # TODO: Add docstring
        pass
    def redo(self): # TODO: Add docstring
        self.execute()

class MetadataEditCommand(UndoRedoCommand):
    """Command for editing metadata."""
    def __init__(self, editor, file_index, field, old_value, new_value):
        super().__init__(f"Edit {field}")
        self.editor, self.file_index, self.field, self.old_value, self.new_value = (
            editor, file_index, field, old_value, new_value
        )
    def execute(self):
        """Executes the metadata edit command."""
        _, metadata = self.editor.all_files[self.file_index]
        metadata[self.field] = self.new_value
        self.editor.update_table_cell(self.file_index, self.field, self.new_value)
        self.editor.changes_pending = True
    def undo(self):
        """Undoes the metadata edit command."""
        _, metadata = self.editor.all_files[self.file_index]
        metadata[self.field] = self.old_value
        self.editor.update_table_cell(self.file_index, self.field, self.old_value)
        self.editor.changes_pending = True

class FileRenameCommand(UndoRedoCommand):
    """Command for renaming a file."""
    def __init__(self, editor, file_index, old_path, new_path):
        super().__init__(f"Rename '{os.path.basename(old_path)}'")
        self.editor, self.file_index, self.old_path, self.new_path = (
            editor, file_index, old_path, new_path
        )
    def execute(self):
        """Executes the file rename command."""
        try:
            os.rename(self.old_path, self.new_path)
            _, metadata = self.editor.all_files[self.file_index]
            self.editor.all_files[self.file_index] = (self.new_path, metadata)
            self.editor.update_filename_in_table(
                self.file_index, os.path.basename(self.new_path)
            )
        except OSError as e:
            QMessageBox.critical(self.editor, "Error", f"Could not rename file: {e}")
    def undo(self):
        """Undoes the file rename command."""
        try:
            os.rename(self.new_path, self.old_path)
            _, metadata = self.editor.all_files[self.file_index]
            self.editor.all_files[self.file_index] = (self.old_path, metadata)
            self.editor.update_filename_in_table(
                self.file_index, os.path.basename(self.old_path)
            )
        except OSError as e:
            QMessageBox.critical(self.editor, "Error", f"Could not undo rename: {e}")

class BatchCommand(UndoRedoCommand):
    """Command for executing a batch of commands."""
    def __init__(self, description, commands):
        super().__init__(description)
        self.commands = commands
    def execute(self):
        """Executes all commands in the batch."""
        for command in self.commands:
            command.execute()
    def undo(self):
        """Undoes all commands in the batch in reverse order."""
        for command in reversed(self.commands):
            command.undo()

class FileRemoveCommand(UndoRedoCommand):
    """Command for removing files."""
    def __init__(self, editor, files_to_remove):
        super().__init__(f"Remove {len(files_to_remove)} files")
        self.editor, self.files_to_remove = editor, files_to_remove
    def execute(self):
        """Executes the file removal command."""
        indices_to_remove = {data[0] for data in self.files_to_remove}
        self.editor.all_files = [
            file for i, file in enumerate(self.editor.all_files)
            if i not in indices_to_remove
        ]
        self.editor.filter_table()
    def undo(self):
        """Undoes the file removal command."""
        for index, file_path, metadata in sorted(self.files_to_remove, key=lambda x: x[0]):
            self.editor.all_files.insert(index, (file_path, metadata))
        self.editor.filter_table()

class UndoRedoStack:
    """Manages the undo and redo stacks."""
    def __init__(self, max_size=50):
        self.undo_stack, self.redo_stack, self.max_size = [], [], max_size
    def push(self, command):
        """Pushes a command to the undo stack."""
        command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)
    def undo(self):
        """Undoes the last command."""
        if self.can_undo():
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
    def redo(self):
        """Redoes the last undone command."""
        if self.can_redo():
            command = self.redo_stack.pop()
            command.redo()
            self.undo_stack.append(command)
    def can_undo(self): # TODO: Add docstring
        return bool(self.undo_stack)
    def can_redo(self): # TODO: Add docstring
        return bool(self.redo_stack)
    def command_to_undo(self): # TODO: Add docstring
        return self.undo_stack[-1] if self.can_undo() else None
    def command_to_redo(self): # TODO: Add docstring
        return self.redo_stack[-1] if self.can_redo() else None
    def clear(self): # TODO: Add docstring
        self.undo_stack.clear()
        self.redo_stack.clear()

class MacStyleDelegate(QStyledItemDelegate):
    """Delegate for painting table items with a macOS style."""
    # def __init__(self, parent=None): # W0246: Useless parent or super() delegation
    #     super().__init__(parent)
    def paint(self, painter, option, index):
        """Paints the table item."""
        main_window = self.parent().window()
        theme = main_window.theme
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(theme['selection_bg']))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(theme['bg_tertiary']))
        else:
            painter.fillRect(
                option.rect,
                QColor(theme['bg_primary'] if index.row() % 2 == 0 else theme['bg_secondary'])
            )
        painter.setPen(QPen(QColor(theme['border_primary'])))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        painter.setPen(
            QColor(theme['selection_fg'] if option.state & QStyle.StateFlag.State_Selected
                   else theme['content_primary'])
        )
        painter.drawText(option.rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter, str(text))
        painter.restore()

class AnimatedPushButton(QPushButton):
    """A QPushButton with animations and theme support."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button_style()
    def get_theme(self): # TODO: Add docstring
        widget = self
        while widget:
            if hasattr(widget, 'theme'):
                return widget.theme
            widget = widget.parent()
        return AudioMetadataEditor.THEMES['dark']  # Fallback to dark theme
    def update_button_style(self): # TODO: Add docstring
        theme = self.get_theme()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['button_secondary_bg']};
                color: {theme['button_secondary_fg']};
                border: 1px solid {theme['border_primary']}; border-radius: 6px;
                font-size: 16px; font-weight: 400;
                min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {theme['button_secondary_hover_bg']};
            }}
            QPushButton:pressed {{
                background-color: {theme['button_secondary_pressed_bg']};
            }}
        """)

class AnimatedPrimaryButton(AnimatedPushButton):
    """A primary animated button with different styling."""
    def update_button_style(self): # TODO: Add docstring
        theme = self.get_theme()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['button_primary_bg']};
                color: {theme['button_primary_fg']};
                border: none; border-radius: 6px;
                font-size: 16px; font-weight: 400;
                min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {theme['button_primary_hover_bg']};
            }}
            QPushButton:pressed {{
                background-color: {theme['button_primary_pressed_bg']};
            }}
        """)

class SettingsDialog(QDialog):
    """Comprehensive settings dialog with multiple sections."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Settings")
        self.setFixedSize(680, 520)
        self.setModal(True)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget
        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_general_tab()
        self.create_guide_tab()
        self.create_shortcuts_tab()
        self.create_about_tab()

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedSize(80, 32)
        button_layout.addWidget(close_btn)

        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        button_widget.setFixedHeight(50)
        main_layout.addWidget(button_widget)

        self.apply_dialog_styling()

    def create_general_tab(self):
        """Create the general settings tab with theme toggle and other settings."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Theme section
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout(theme_group)

        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_row.addWidget(theme_label)
        theme_row.addStretch()

        self.dark_mode_checkbox = QCheckBox("Dark Mode")
        self.dark_mode_checkbox.setChecked(self.parent_window.current_theme == 'dark')
        self.dark_mode_checkbox.toggled.connect(self.toggle_theme)
        theme_row.addWidget(self.dark_mode_checkbox)

        theme_layout.addLayout(theme_row)
        layout.addWidget(theme_group)

        # Background Agents section
        agents_group = QGroupBox("Background Agents")
        agents_layout = QVBoxLayout(agents_group)

        agents_info = QLabel("• AutoSave Agent: Saves changes every 30 seconds\n"
                           "• FileWatcher Agent: Monitors external file changes\n"
                           "• Validation Agent: Validates metadata integrity")
        agents_info.setStyleSheet("color: #666;")
        agents_layout.addWidget(agents_info)

        layout.addWidget(agents_group)

        # Performance section
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)

        cpu_info = QLabel(f"Available CPU cores: {os.cpu_count()}")
        cpu_info.setStyleSheet("color: #666;")
        perf_layout.addRow("Processing:", cpu_info)

        layout.addWidget(perf_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "General")

    def create_guide_tab(self):
        """Create the user guide tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        # Create scrollable area for guide content
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        guide_text = """
<h2>Audio Metadata Editor Guide</h2>

<h3>🚀 Getting Started</h3>
<p><strong>Loading Files:</strong></p>
<ul>
<li>Drag and drop a folder containing WAV files into the application</li>
<li>Or use the "📂" button to browse for a folder</li>
<li>Files will be loaded with parallel processing for speed</li>
</ul>

<h3>📝 Editing Metadata</h3>
<p><strong>Basic Editing:</strong></p>
<ul>
<li>Double-click any cell to edit metadata fields</li>
<li>Edit filename, show, scene, take, category, subcategory, and more</li>
<li>Changes are tracked and can be undone/redone</li>
</ul>

<p><strong>Bulk Operations:</strong></p>
<ul>
<li>Select multiple rows to mirror files</li>
<li>Use extraction tool (⚙) to parse metadata from filenames</li>
<li>Right-click selected rows to remove files from list</li>
</ul>

<h3>🔍 Search & Filter</h3>
<p><strong>Smart Search:</strong></p>
<ul>
<li>Use the search bar to filter files by any field</li>
<li>Click the dropdown arrow to search specific fields</li>
<li>Search is real-time and case-insensitive</li>
</ul>

<h3>💾 Saving Changes</h3>
<p><strong>Auto-Save:</strong></p>
<ul>
<li>Background agent automatically saves changes every 30 seconds</li>
<li>Manual save with Cmd+S or the "💾" button</li>
<li>Unsaved changes are highlighted in the status bar</li>
</ul>

<h3>🔄 Undo/Redo System</h3>
<p><strong>Full History:</strong></p>
<ul>
<li>All metadata edits and file operations can be undone</li>
<li>Up to 50 operations stored in history</li>
<li>Tooltips show what will be undone/redone</li>
</ul>

<h3>⧉ Mirror Panel</h3>
<p><strong>File Organization:</strong></p>
<ul>
<li>Use the mirror button to open the file organization panel</li>
<li>Select files and choose destination for organized copying</li>
<li>Supports day-based organization and overwrite options</li>
</ul>
        """

        guide_label = QLabel(guide_text)
        guide_label.setWordWrap(True)
        guide_label.setTextFormat(Qt.TextFormat.RichText)
        guide_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.addWidget(guide_label)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        self.tab_widget.addTab(tab, "User Guide")

    def create_shortcuts_tab(self):
        """Create the keyboard shortcuts tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        # Create scrollable area for shortcuts
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        shortcuts_text = """
<h2>Keyboard Shortcuts</h2>

<h3>📁 File Operations</h3>
<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+O</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Open folder</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+S</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Save all changes</td></tr>
</table>

<h3>✏️ Edit Operations</h3>
<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+Z</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Undo last change</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+Shift+Z</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Redo last change</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+A</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Select all rows</td></tr>
</table>

 <h3>🔍 Search & Navigation</h3>
 <table style="width: 100%; border-collapse: collapse;">
 <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+F</strong></td>
 <td style="padding: 8px; border-bottom: 1px solid #ddd;">Focus search field</td></tr>
 <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Double-click</strong></td>
 <td style="padding: 8px; border-bottom: 1px solid #ddd;">Edit cell content</td></tr>
 <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Click header</strong></td>
 <td style="padding: 8px; border-bottom: 1px solid #ddd;">Sort by column</td></tr>
 </table>

 <h3>🛠️ Application</h3>
 <table style="width: 100%; border-collapse: collapse;">
 <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Cmd+,</strong></td>
 <td style="padding: 8px; border-bottom: 1px solid #ddd;">Open Settings</td></tr>
 </table>

<h3>🖱️ Mouse Operations</h3>
<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Drag & Drop</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Load folder of WAV files</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Right-click</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Context menu (remove files)</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Shift/Cmd+Click</strong></td>
<td style="padding: 8px; border-bottom: 1px solid #ddd;">Multi-select rows</td></tr>
</table>

<h3>🎯 Tips</h3>
<ul>
<li>Use <strong>Tab</strong> to move between cells when editing</li>
<li>Press <strong>Enter</strong> to confirm cell edits</li>
<li>Press <strong>Escape</strong> to cancel cell edits</li>
<li>Column widths can be adjusted by dragging header borders</li>
</ul>
        """

        shortcuts_label = QLabel(shortcuts_text)
        shortcuts_label.setWordWrap(True)
        shortcuts_label.setTextFormat(Qt.TextFormat.RichText)
        shortcuts_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.addWidget(shortcuts_label)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        self.tab_widget.addTab(tab, "Keyboard Shortcuts")

    def create_about_tab(self):
        """Create the about/info tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # App info section
        app_group = QGroupBox("Application Information")
        app_layout = QVBoxLayout(app_group)

        app_info = f"""
<h3>Audio Metadata Editor</h3>
<p><strong>Version:</strong> 1.0.0</p>
<p><strong>Python Version:</strong> {sys.version.split()[0]}</p>
<p><strong>PyQt6 Version:</strong> 6.4.0+</p>
<p><strong>Platform:</strong> macOS</p>

<p>A sophisticated macOS application for reading, viewing, and editing
metadata of WAV audio files with advanced background processing capabilities.</p>
        """

        app_label = QLabel(app_info)
        app_label.setTextFormat(Qt.TextFormat.RichText)
        app_label.setWordWrap(True)
        app_layout.addWidget(app_label)

        layout.addWidget(app_group)

        # Features section
        features_group = QGroupBox("Key Features")
        features_layout = QVBoxLayout(features_group)

        features_info = """
• Drag & Drop Interface for easy file loading
• Advanced Metadata Editing with undo/redo support
• Background Agent System for auto-save and monitoring
• Parallel Processing for fast file operations
• Real-time Search and Filtering
• File Organization and Mirroring tools
• Comprehensive Keyboard Shortcuts
• Dark/Light Theme Support
        """

        features_label = QLabel(features_info)
        features_label.setStyleSheet("color: #555;")
        features_layout.addWidget(features_label)

        layout.addWidget(features_group)

        # System info section
        system_group = QGroupBox("System Information")
        system_layout = QFormLayout(system_group)

        system_layout.addRow("CPU Cores:", QLabel(str(os.cpu_count())))
        system_layout.addRow("Working Directory:", QLabel(os.getcwd()))

        layout.addWidget(system_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "About")

    def toggle_theme(self, checked):
        """Handle theme toggle from settings."""
        if self.parent_window:
            if checked != (self.parent_window.current_theme == 'dark'):
                self.parent_window.toggle_dark_mode()
                self.apply_dialog_styling()

    def apply_dialog_styling(self):
        """Apply theme-appropriate styling to the settings dialog."""
        if not self.parent_window:
            return

        theme = self.parent_window.theme

        self.setStyleSheet(f"""
        QDialog {{
            background-color: {theme['bg_primary']};
            color: {theme['content_primary']};
        }}

        QTabWidget::pane {{
            border: 1px solid {theme['border_primary']};
            background-color: {theme['bg_primary']};
        }}

        QTabBar::tab {{
            background-color: {theme['bg_secondary']};
            color: {theme['content_secondary']};
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid {theme['border_primary']};
            border-bottom: none;
        }}

        QTabBar::tab:selected {{
            background-color: {theme['bg_primary']};
            color: {theme['content_primary']};
        }}

        QTabBar::tab:hover {{
            background-color: {theme['bg_tertiary']};
        }}

        QGroupBox {{
            font-weight: bold;
            border: 1px solid {theme['border_primary']};
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
            background-color: {theme['bg_secondary']};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 8px 0 8px;
            color: {theme['content_primary']};
        }}

        QLabel {{
            color: {theme['content_primary']};
        }}

        QCheckBox {{
            color: {theme['content_primary']};
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {theme['border_primary']};
            border-radius: 3px;
            background-color: {theme['bg_primary']};
        }}

        QCheckBox::indicator:checked {{
            background-color: {theme['button_primary_bg']};
            border-color: {theme['button_primary_bg']};
        }}

        QPushButton {{
            background-color: {theme['button_secondary_bg']};
            color: {theme['button_secondary_fg']};
            border: 1px solid {theme['border_primary']};
            border-radius: 6px;
            padding: 6px 12px;
        }}

        QPushButton:hover {{
            background-color: {theme['button_secondary_hover_bg']};
        }}

        QPushButton:pressed {{
            background-color: {theme['button_secondary_pressed_bg']};
        }}

        QScrollArea {{
            border: 1px solid {theme['border_primary']};
            background-color: {theme['bg_primary']};
        }}

        QScrollBar:vertical {{
            background-color: {theme['bg_secondary']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {theme['border_primary']};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {theme['content_secondary']};
        }}
        """)

class FileLoadWorker(QThread):
    """Worker thread for loading files."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
    def run(self):
        """Runs the file loading process."""
        results = []
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_path = {
                executor.submit(self.safe_read_metadata, path): path for path in self.file_paths
            }

            for i, future in enumerate(concurrent.futures.as_completed(future_to_path)):
                path = future_to_path[future]
                if self.isInterruptionRequested():
                    executor.shutdown(wait=False, cancel_futures=True)
                    return

                try:
                    metadata = future.result()
                    if metadata:
                        results.append((path, metadata))
                except IOError as e: # More specific exception
                    print(f"I/O error processing file {path}: {e}")
                except ValueError as e: # More specific exception for parsing issues
                    print(f"Error parsing metadata for file {path}: {e}")
                except Exception as e: # Catch all for other errors
                    print(f"Unexpected error processing file {path}: {e}")

                self.progress.emit(i + 1, len(self.file_paths), os.path.basename(path))

        self.finished.emit(results)

    def safe_read_metadata(self, file_path):
        """Safely reads WAV metadata from a file."""
        try:
            return wav_metadata.read_wav_metadata(file_path)
        except IOError as e: # More specific exception
            print(f"Could not read WAV metadata from {file_path}: {e}")
            return None
        except ValueError as e: # More specific exception for parsing issues
            print(f"Could not parse WAV metadata from {file_path}: {e}")
            return None
        except Exception as e: # Catch all for other errors
            print(f"Unexpected error reading WAV metadata from {file_path}: {e}")
            return None

class AudioMetadataEditor(QMainWindow):
    """Main window for the Audio Metadata Editor application."""
    THEMES = {
        'dark': {
            "bg_primary": "#1E1F22", "bg_secondary": "#2B2D30", "bg_tertiary": "#383A3F",
            "content_primary": "#FFFFFF", "content_secondary": "#B0B3B8",
            "accent_primary": "#5865F2", "accent_danger": "#ED4245",
            "border_primary": "#404349", "selection_bg": "rgba(88,101,242,0.2)",
            "selection_fg": "#FFFFFF", "button_primary_bg": "#5865F2",
            "button_primary_fg": "#FFFFFF", "button_primary_hover_bg": "#4752C4",
            "button_primary_pressed_bg": "#3C45A5", "button_secondary_bg": "#404349",
            "button_secondary_fg": "#FFFFFF", "button_secondary_hover_bg": "#4E5058",
            "button_secondary_pressed_bg": "#585B62"
        },
        'light': {
            "bg_primary": "#FFFFFF", "bg_secondary": "#F2F3F5", "bg_tertiary": "#E3E5E8",
            "content_primary": "#060607", "content_secondary": "#4E5058",
            "accent_primary": "#5865F2", "accent_danger": "#D83C3E",
            "border_primary": "#DCDDDE", "selection_bg": "rgba(88,101,242,0.1)",
            "selection_fg": "#060607", "button_primary_bg": "#5865F2",
            "button_primary_fg": "#FFFFFF", "button_primary_hover_bg": "#4752C4",
            "button_primary_pressed_bg": "#3C45A5", "button_secondary_bg": "#E3E5E8",
            "button_secondary_fg": "#060607", "button_secondary_hover_bg": "#DCDDDE",
            "button_secondary_pressed_bg": "#B0B3B8"
        }
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Metadata Editor")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        self.setWindowFlags(Qt.WindowType.Window) # Use native macOS window
        self.current_theme = 'dark'
        self.theme = self.THEMES[self.current_theme]
        self.undo_redo_stack = UndoRedoStack()
        self.current_sort_column_index, self.current_sort_order = 0, Qt.SortOrder.AscendingOrder
        self.all_files, self.filtered_rows, self.changes_pending = [], [], False

        self._init_ui_elements() # Initialize UI elements before _init_ui
        self._init_ui()
        self.apply_stylesheet()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_table)
        QTimer.singleShot(0, self.finish_setup)

    def _init_ui_elements(self):
        """Initializes UI elements that are defined outside __init__."""
        self.open_btn = None
        self.save_btn = None
        self.undo_btn = None
        self.redo_btn = None
        self.search_container = None
        self.search_input = None
        self.search_field_btn = None
        self.mirror_btn = None
        self.extract_btn = None
        self.settings_btn = None
        self.splitter = None
        self.mirror_panel = None
        self.status_label = None
        self.table = None
        self.progress = None
        self.file_load_worker = None
        self.agent_manager = None


    def finish_setup(self): # TODO: Add docstring
        self.setup_shortcuts()
        self.setAcceptDrops(True)
        self.setup_agent_manager()
    def _init_ui(self): # TODO: Add docstring
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("central_widget")
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self._create_toolbar(main_layout)
        self._create_main_content(main_layout)
    def _create_toolbar(self, l): # TODO: Add docstring
        # Integrated toolbar below native title bar
        tb = QWidget(self)
        tb.setObjectName("integrated_toolbar")
        tb.setFixedHeight(52)
        lo = QHBoxLayout(tb)
        lo.setContentsMargins(12, 8, 12, 8)
        lo.setSpacing(12)

        # File operations group
        file_group = QWidget(self)
        file_group.setObjectName("file_group")
        file_layout = QHBoxLayout(file_group)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(4)

        self.open_btn = AnimatedPushButton("📂", self)
        self.open_btn.setToolTip("Open folder")
        self.open_btn.setFixedSize(36, 36)
        self.open_btn.clicked.connect(self.browse_folder)
        file_layout.addWidget(self.open_btn)

        self.save_btn = AnimatedPushButton("💾", self)
        self.save_btn.setToolTip("Save all changes")
        self.save_btn.setFixedSize(36, 36)
        self.save_btn.clicked.connect(self.save_all_changes)
        file_layout.addWidget(self.save_btn)

        lo.addWidget(file_group)

        # Add separator
        separator1 = QFrame(self)
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        separator1.setFixedHeight(32)
        lo.addWidget(separator1)

        # Edit operations group
        edit_group = QWidget(self)
        edit_group.setObjectName("edit_group")
        edit_layout = QHBoxLayout(edit_group)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(4)

        self.undo_btn = AnimatedPushButton("↶", self)
        self.undo_btn.setToolTip("Undo")
        self.undo_btn.setFixedSize(36, 36)
        self.undo_btn.clicked.connect(self.undo_last_change)
        self.undo_btn.setEnabled(False)
        edit_layout.addWidget(self.undo_btn)

        self.redo_btn = AnimatedPushButton("↷", self)
        self.redo_btn.setToolTip("Redo")
        self.redo_btn.setFixedSize(36, 36)
        self.redo_btn.clicked.connect(self.redo_last_change)
        self.redo_btn.setEnabled(False)
        edit_layout.addWidget(self.redo_btn)

        lo.addWidget(edit_group)

        # Flexible spacer
        lo.addStretch()

        # Search group with embedded dropdown
        search_group = QWidget(self)
        search_group.setObjectName("search_group")
        search_layout = QHBoxLayout(search_group)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)

        # Create custom search widget with embedded dropdown
        self.search_container = QWidget(self)
        self.search_container.setFixedWidth(280)
        self.search_container.setObjectName("search_container")
        container_layout = QHBoxLayout(self.search_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Search files...")
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.setObjectName("search_input_embedded")
        container_layout.addWidget(self.search_input)

        self.search_field_btn = QPushButton("All", self)
        self.search_field_btn.setObjectName("search_dropdown_btn")
        self.search_field_btn.setText("All ▼")
        self.search_field_btn.setFixedWidth(60)
        self.search_field_btn.clicked.connect(self.show_field_menu)
        container_layout.addWidget(self.search_field_btn)

        search_layout.addWidget(self.search_container)

        lo.addWidget(search_group)

        # Add separator
        separator2 = QFrame(self)
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        separator2.setFixedHeight(32)
        lo.addWidget(separator2)

        # Tool group
        tool_group = QWidget(self)
        tool_group.setObjectName("tool_group")
        tool_layout = QHBoxLayout(tool_group)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.setSpacing(4)

        self.mirror_btn = AnimatedPushButton("⧉", self)
        self.mirror_btn.setToolTip("Mirror files")
        self.mirror_btn.setFixedSize(36, 36)
        self.mirror_btn.clicked.connect(self.toggle_mirror_panel)
        tool_layout.addWidget(self.mirror_btn)

        self.extract_btn = AnimatedPushButton("📝", self)
        self.extract_btn.setToolTip("Extract metadata from filenames")
        self.extract_btn.setFixedSize(36, 36)
        self.extract_btn.clicked.connect(self.show_extraction_dialog)
        tool_layout.addWidget(self.extract_btn)

        self.settings_btn = AnimatedPushButton("⚙", self)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.clicked.connect(self.show_settings_dialog)
        tool_layout.addWidget(self.settings_btn)

        lo.addWidget(tool_group)

        l.addWidget(tb)
    def _create_main_content(self, l): # TODO: Add docstring
        cw = QWidget(self)
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        mv = QWidget(self)
        mvl = QVBoxLayout(mv)
        mvl.setContentsMargins(0,0,0,0)
        self._create_table(mvl)
        self.splitter.addWidget(mv)
        self.mirror_panel = MirrorPanel(self)
        self.mirror_panel.setVisible(False)
        self.splitter.addWidget(self.mirror_panel)
        self.splitter.setSizes([self.width(), 0])
        cl.addWidget(self.splitter)

        # Status bar with enhanced styling
        status_container = QWidget(self)
        status_container.setFixedHeight(24)  # Set a fixed small height
        status_container.setObjectName("status_container")
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(12, 2, 12, 2)
        self.status_label = QLabel("Ready", self)
        self.status_label.setObjectName("status_label")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        cl.addWidget(status_container)
        l.addWidget(cw)
    def _create_table(self, l): # TODO: Add docstring
        self.table = QTableWidget(0, 11, self)
        self.table.setObjectName("metadata_table")
        self.table.setHorizontalHeaderLabels([
            "Filename", "Show", "Scene", "Take", "Category", "Subcategory",
            "Slate", "iXML Note", "iXML Wildtrack", "iXML Circled", "File Path"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_table_by_column)
        h = self.table.horizontalHeader()
        h.setMinimumSectionSize(100)
        for c in range(self.table.columnCount()):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        # Set optimized column widths for better header visibility
        self.table.setColumnWidth(0, 180)  # Filename
        self.table.setColumnWidth(1, 80)   # Show
        self.table.setColumnWidth(2, 80)   # Scene
        self.table.setColumnWidth(3, 60)   # Take
        self.table.setColumnWidth(4, 100)  # Category
        self.table.setColumnWidth(5, 120)  # Subcategory
        self.table.setColumnWidth(6, 80)   # Slate
        self.table.setColumnWidth(7, 100)  # iXML Note
        self.table.setColumnWidth(8, 110)  # iXML Wildtrack
        self.table.setColumnWidth(9, 110)  # iXML Circled
        self.table.setColumnWidth(10, 200) # File Path
        self.table.setItemDelegate(MacStyleDelegate(self))
        self.table.itemChanged.connect(self.update_metadata)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.setup_table_context_menu()
        l.addWidget(self.table)
    def on_search_text_changed(self): # TODO: Add docstring
        self.search_timer.start(300)
    def apply_stylesheet(self): # TODO: Add docstring
        theme = self.theme
        self.setStyleSheet(f"""
        /* Main Window */
        #central_widget {{
            background-color: {theme['bg_primary']};
            border: none;
            border-radius: 0px;
        }}

        /* Toolbar */
        #integrated_toolbar {{
            background-color: {theme['bg_secondary']};
            border: none;
            border-bottom: 1px solid {theme['border_primary']};
            margin: 0;
        }}

        #app_title {{
            color: {theme['content_primary']};
            font-size: 14px;
            font-weight: bold;
        }}

        /* Window Controls */
        #minimize_button, #maximize_button, #close_button {{
            background-color: transparent;
            color: {theme['content_secondary']};
            border: none;
            font-size: 14px;
            font-weight: bold;
            border-radius: 6px;
            margin: 1px;
        }}

        #close_button:hover {{
            background-color: {theme['accent_danger']};
            color: white;
        }}

        #minimize_button:hover, #maximize_button:hover {{
            background-color: {theme['bg_tertiary']};
        }}

        /* Table Styling */
        #metadata_table {{
            background-color: {theme['bg_primary']};
            color: {theme['content_primary']};
            border: 1px solid {theme['border_primary']};
            border-radius: 8px;
            gridline-color: {theme['border_primary']};
            font-size: 13px;
            selection-background-color: {theme['selection_bg']};
            selection-color: {theme['selection_fg']};
        }}

        QHeaderView::section {{
            background-color: {theme['bg_secondary']};
            color: {theme['content_secondary']};
            padding: 4px 8px;
            border: none;
            border-bottom: 2px solid {theme['border_primary']};
            border-right: 1px solid {theme['border_primary']};
            font-weight: bold;
            font-size: 10px;
            text-transform: none;
            letter-spacing: 0px;
        }}

        QHeaderView::section:hover {{
            background-color: {theme['bg_tertiary']};
            color: {theme['content_primary']};
        }}

        QHeaderView::section:first {{
            border-top-left-radius: 6px;
        }}

        QHeaderView::section:last {{
            border-top-right-radius: 6px;
            border-right: none;
        }}

        /* Input Fields */
        QLineEdit {{
            background-color: {theme['bg_secondary']};
            color: {theme['content_primary']};
            border: 2px solid {theme['border_primary']};
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 13px;
        }}

        QLineEdit:hover {{
            border-color: {theme['bg_tertiary']};
        }}

        /* Search Container with Embedded Dropdown */
        #search_container {{
            background-color: {theme['bg_secondary']};
            border: 2px solid {theme['border_primary']};
            border-radius: 6px;
            padding: 0px;
        }}

        #search_container:hover {{
            border-color: {theme['bg_tertiary']};
        }}

        #search_input_embedded {{
            background-color: transparent;
            border: none;
            border-radius: 0px;
            padding: 8px 12px;
            font-size: 13px;
        }}

        #search_input_embedded:focus {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        #search_dropdown_btn {{
            background-color: {theme['bg_tertiary']};
            color: {theme['content_secondary']};
            border: none;
            border-left: 1px solid {theme['border_primary']};
            border-radius: 0px;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            padding: 8px 6px;
            font-size: 11px;
            font-weight: 500;
            min-width: 50px;
        }}

        #search_dropdown_btn:hover {{
            background-color: {theme['accent_primary']};
            color: white;
        }}

        #search_dropdown_btn:pressed {{
            background-color: {theme['button_secondary_pressed_bg']};
        }}

        /* Buttons */
        QPushButton {{
            font-size: 13px;
            font-weight: 500;
            border-radius: 6px;
            padding: 8px 16px;
        }}

        /* Dropdown/ComboBox */
        QComboBox {{
            background-color: {theme['bg_secondary']};
            color: {theme['content_primary']};
            border: 2px solid {theme['border_primary']};
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
        }}

        QComboBox:hover {{
            border-color: {theme['bg_tertiary']};
        }}

        QComboBox::drop-down {{
            border: none;
            background-color: transparent;
        }}

        /* Splitter */
        QSplitter::handle {{
            background-color: {theme['border_primary']};
            border-radius: 2px;
        }}

        QSplitter::handle:hover {{
            background-color: {theme['accent_primary']};
        }}

        /* Toolbar Separators */
        QFrame[frameShape="5"] {{
            color: {theme['border_primary']};
            background-color: {theme['border_primary']};
            margin: 4px 8px;
        }}

        /* Status Label */
        #status_container {{
            background-color: {theme['bg_secondary']};
            border-top: 1px solid {theme['border_primary']};
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        }}

        #status_label {{
            color: {theme['content_secondary']};
            font-size: 11px;
            padding: 0px;
            background-color: transparent;
            border: none;
        }}

        /* Menus */
        QMenu {{
            background-color: {theme['bg_secondary']};
            color: {theme['content_primary']};
            border: 1px solid {theme['border_primary']};
            border-radius: 8px;
            padding: 6px;
        }}

        QMenu::item {{
            padding: 8px 20px;
            border-radius: 4px;
        }}

        QMenu::item:selected {{
            background-color: {theme['accent_primary']};
            color: white;
        }}

        /* Progress Dialog */
        QProgressDialog {{
            background-color: {theme['bg_primary']};
            color: {theme['content_primary']};
            border: 1px solid {theme['border_primary']};
            border-radius: 8px;
        }}

        QProgressBar {{
            background-color: {theme['bg_secondary']};
            border: 1px solid {theme['border_primary']};
            border-radius: 4px;
            text-align: center;
            color: {theme['content_primary']};
        }}

        QProgressBar::chunk {{
            background-color: {theme['accent_primary']};
            border-radius: 3px;
        }}
        """)
        self.update_animated_button_styles()
    def toggle_maximized(self):
        """Toggles the maximized state of the window."""
        if self.isMaximized():
            self.showNormal()
            # self.max_btn.setText("▢") # max_btn is not defined
        else:
            self.showMaximized()
            # self.max_btn.setText("❐") # max_btn is not defined
    def setup_shortcuts(self): # TODO: Add docstring
        QShortcut(QKeySequence.StandardKey.Undo, self, self.undo_last_change)
        QShortcut(QKeySequence.StandardKey.Redo, self, self.redo_last_change)
        QShortcut(QKeySequence.StandardKey.Save, self, self.save_all_changes)
        QShortcut(QKeySequence.StandardKey.Open, self, self.browse_folder)
        QShortcut(QKeySequence.StandardKey.Find, self, self.focus_search)
        QShortcut(QKeySequence.StandardKey.SelectAll, self, self.table.selectAll)
        QShortcut(QKeySequence("Cmd+,"), self, self.show_settings_dialog)
    def focus_search(self): # TODO: Add docstring
        self.search_input.setFocus()
    def _get_sort_key(self, item, col): # TODO: Add docstring
        header = self.table.horizontalHeaderItem(col).text()
        val = item[1].get(header, "") if header != "Filename" else os.path.basename(item[0])
        return int(val) if header == 'Take' and val.isdigit() else str(val).lower()
    def sort_table_by_column(self, col): # TODO: Add docstring
        if self.current_sort_column_index == col and \
           self.current_sort_order == Qt.SortOrder.AscendingOrder:
            self.current_sort_order = Qt.SortOrder.DescendingOrder
        else:
            self.current_sort_order = Qt.SortOrder.AscendingOrder
        self.current_sort_column_index = col
        self.table.horizontalHeader().setSortIndicator(col, self.current_sort_order)
        self.all_files.sort(
            key=lambda item: self._get_sort_key(item, col),
            reverse=self.current_sort_order == Qt.SortOrder.DescendingOrder
        )
        self.filter_table()
    def on_selection_changed(self): # TODO: Add docstring
        selected_count = len(self.table.selectionModel().selectedRows())
        self.status_label.setText(f"{selected_count} items selected")

        if hasattr(self, 'mirror_panel') and self.mirror_panel.isVisible():
            selected_rows = self.get_selected_actual_rows()
            self.mirror_panel.set_selected_rows(selected_rows)
    def setup_table_context_menu(self): # TODO: Add docstring
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        remove_action = QAction("Remove Selected Files", self)
        remove_action.triggered.connect(self.prompt_remove_files)
        self.table.addAction(remove_action)
    def browse_folder(self): # TODO: Add docstring
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            wav_files = [
                os.path.join(r, f) for r, _, fs in os.walk(path)
                for f in fs if f.lower().endswith('.wav')
            ]
            self.load_files_from_paths(wav_files)
    def load_files_from_paths(self, paths): # TODO: Add docstring
        if not paths:
            return
        self.progress = QProgressDialog("Loading files...", "", 0, len(paths), self)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.all_files.clear()
        self.filtered_rows.clear()
        self.file_load_worker = FileLoadWorker(paths)
        self.file_load_worker.finished.connect(self.on_file_loaded)
        self.file_load_worker.progress.connect(self.on_file_load_progress)
        self.file_load_worker.start()
    def on_file_loaded(self, results): # TODO: Add docstring
        self.all_files.extend(results)
        self.filter_table()
    def on_file_load_progress(self, c, t, f): # TODO: Add docstring
        if c == t:
            if self.progress: # Check if progress dialog still exists
                self.progress.close()
            self.sort_table_by_column(self.current_sort_column_index)
        else:
            if self.progress: # Check if progress dialog still exists
                self.progress.setValue(c)
                self.progress.setLabelText(f"Loading: {f}")
    def update_table(self): # TODO: Add docstring
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.filtered_rows))
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        for row_idx, original_index in enumerate(self.filtered_rows):
            file_path, metadata = self.all_files[original_index]
            for col_idx, field in enumerate(headers):
                val = os.path.basename(file_path) if field == "Filename" \
                    else str(metadata.get(field, ""))
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, original_index)
                if field == "File Path":
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)
        self.table.setSortingEnabled(True)
    def filter_table(self): # TODO: Add docstring
        search_text = self.search_input.text().lower()
        search_field = self.search_field_btn.text().replace(" ▼", "")
        self.filtered_rows = []
        for i, (fp, meta) in enumerate(self.all_files):
            if not search_text:
                self.filtered_rows.append(i)
                continue
            if search_field == "All" and \
               (search_text in os.path.basename(fp).lower() or
                    any(search_text in str(v).lower() for v in meta.values())):
                self.filtered_rows.append(i)
            elif search_field != "All" and search_text in str(meta.get(search_field, "")).lower():
                self.filtered_rows.append(i)
        self.update_table()
    def update_metadata(self, item): # TODO: Add docstring
        original_index = item.data(Qt.ItemDataRole.UserRole)
        field = self.table.horizontalHeaderItem(item.column()).text()
        if field == "Filename":
            self.rename_file(original_index, item.text())
        else:
            old_val = self.all_files[original_index][1].get(field, "")
            if str(old_val) != item.text():
                cmd = MetadataEditCommand(self, original_index, field, old_val, item.text())
                self.undo_redo_stack.push(cmd)
                self.update_undo_redo_buttons()
    def rename_file(self, idx, name): # TODO: Add docstring
        op = self.all_files[idx][0]
        np = os.path.join(os.path.dirname(op), name)
        if op != np:
            cmd = FileRenameCommand(self, idx, op, np)
            self.undo_redo_stack.push(cmd)
            self.update_undo_redo_buttons()
    def save_all_changes(self): # TODO: Add docstring
        if not self.changes_pending:
            return
        try:
            for fp, meta in self.all_files:
                wav_metadata.write_wav_metadata(fp, meta)
            self.changes_pending = False
            self.status_label.setText("Changes saved.")
        except IOError as e:
            QMessageBox.critical(self, "Save Error", f"Could not save changes: {e}")
        except Exception as e: # Catch other potential errors during write
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during save: {e}")

    def get_selected_actual_rows(self): # TODO: Add docstring
        return sorted(list({
            self.table.item(i.row(), 0).data(Qt.ItemDataRole.UserRole)
            for i in self.table.selectedIndexes()
        }))
    def prompt_remove_files(self): # TODO: Add docstring
        rows = self.get_selected_actual_rows()
        if not rows:
            return
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Are you sure you want to remove {len(rows)} file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            files_to_remove_data = [
                (i, self.all_files[i][0], self.all_files[i][1]) for i in rows
            ]
            cmd = FileRemoveCommand(self, files_to_remove_data)
            self.undo_redo_stack.push(cmd)
            self.update_undo_redo_buttons()
    def toggle_mirror_panel(self): # TODO: Add docstring
        self.mirror_panel.setVisible(not self.mirror_panel.isVisible())
        self.splitter.setSizes([1, 1] if self.mirror_panel.isVisible() else [1, 0])
    def toggle_dark_mode(self): # TODO: Add docstring
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.theme = self.THEMES[self.current_theme]
        self.apply_stylesheet()
        if hasattr(self, 'mirror_panel'):
            self.mirror_panel.update() # TODO: ensure mirror_panel has an update method
    def update_animated_button_styles(self): # TODO: Add docstring
        for b in self.findChildren(AnimatedPushButton):
            b.update_button_style()
    def create_undo_icon(self): # TODO: Add docstring
        return QIcon()
    def create_redo_icon(self): # TODO: Add docstring
        return QIcon()
    def close_event(self, event): # Renamed from closeEvent
        """Handles the close event of the window."""
        if self.changes_pending:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_all_changes()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        if hasattr(self, 'agent_manager'):
            self.agent_manager.stop_agents()
        event.accept()
    def setup_agent_manager(self):
        """Initialize and start the background agent system."""
        try:
            self.agent_manager = BackgroundAgentManager(self, self)
            self.agent_manager.status_changed.connect(self.on_agent_status_changed)
            if self.all_files:
                self.agent_manager.start_agents()
        except Exception as e: # More specific logging for agent setup
            print(f"Error setting up agent manager: {type(e).__name__} - {e}")

    def on_agent_status_changed(self, status):
        """Handle status updates from background agents."""
        self.status_label.setText(status)

    def update_filename_in_table(self, idx, name):
        """Update filename in table for a specific file index."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)  # filename column
            if item and item.data(Qt.ItemDataRole.UserRole) == idx:
                item.setText(name)
                break

    def update_table_cell(self, idx, field, value):
        """Update a specific cell in the table for a file index and field."""
        field_column = -1
        for col in range(self.table.columnCount()):
            if self.table.horizontalHeaderItem(col).text() == field:
                field_column = col
                break

        if field_column == -1:
            return

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == idx:
                target_item = self.table.item(row, field_column)
                if target_item:
                    target_item.setText(str(value))
                break

    def undo_last_change(self):
        """Undo the last change operation."""
        if self.undo_redo_stack.can_undo():
            self.undo_redo_stack.undo()
            self.update_undo_redo_buttons()

    def redo_last_change(self):
        """Redo the last undone change operation."""
        if self.undo_redo_stack.can_redo():
            self.undo_redo_stack.redo()
            self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        """Update the state and tooltips of undo/redo buttons."""
        can_undo = self.undo_redo_stack.can_undo()
        can_redo = self.undo_redo_stack.can_redo()

        self.undo_btn.setEnabled(can_undo)
        self.redo_btn.setEnabled(can_redo)

        if can_undo:
            cmd = self.undo_redo_stack.command_to_undo()
            self.undo_btn.setToolTip(f"Undo: {cmd.description}")
        else:
            self.undo_btn.setToolTip("Undo")

        if can_redo:
            cmd = self.undo_redo_stack.command_to_redo()
            self.redo_btn.setToolTip(f"Redo: {cmd.description}")
        else:
            self.redo_btn.setToolTip("Redo")

    def show_field_menu(self):
        """Show dropdown menu for selecting search field."""
        menu = QMenu(self)
        menu.addAction("All", lambda: self.set_search_field("All"))

        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col)
            if header and header.text() != "File Path":
                field_name = header.text()
                menu.addAction(field_name, lambda f=field_name: self.set_search_field(f))

        container_rect = self.search_container.geometry()
        button_rect = self.search_field_btn.geometry()
        container_global_pos = self.search_container.mapToGlobal(container_rect.bottomLeft())
        menu_pos = container_global_pos + QPoint(button_rect.x(), 0)
        menu.exec(menu_pos)

    def set_search_field(self, field):
        """Set the current search field and update button text."""
        self.search_field_btn.setText(f"{field} ▼")
        self.filter_table()

    def mirror_files_qcode_take_review(
            self, selected_rows, destination_dir, day_number, overwrite
    ):
        """Mirror selected files to destination with QCODE take review structure."""
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "No files selected for mirroring.")
            return

        try:
            progress = QProgressDialog("Mirroring files...", "Cancel", 0, len(selected_rows), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            success_count = 0
            error_count = 0

            for i, row_idx in enumerate(selected_rows):
                if progress.wasCanceled():
                    break

                file_path, _ = self.all_files[row_idx] # metadata not used
                filename = os.path.basename(file_path)

                day_folder = f"Day{day_number:02d}"
                takes_folder = "Takes"
                dest_path = os.path.join(destination_dir, day_folder, takes_folder)

                os.makedirs(dest_path, exist_ok=True)

                dest_file = os.path.join(dest_path, filename)
                try:
                    if not os.path.exists(dest_file) or overwrite:
                        shutil.copy2(file_path, dest_file)
                        success_count += 1
                    else:
                        error_count += 1
                        print(f"Skipped existing file: {filename}")
                except IOError as e: # Specific exception for I/O errors
                    error_count += 1
                    print(f"I/O error copying {filename}: {e}")
                except Exception as e:
                    error_count += 1
                    print(f"Error copying {filename}: {e}")

                progress.setValue(i + 1)
                progress.setLabelText(f"Copying: {filename}")

            progress.close()

            if error_count == 0:
                QMessageBox.information(
                    self, "Mirror Complete",
                    f"Successfully mirrored {success_count} files to:\n{dest_path}"
                )
            else:
                QMessageBox.warning(
                    self, "Mirror Completed with Errors",
                    f"Mirrored {success_count} files successfully.\n"
                    f"{error_count} files had errors."
                )

        except OSError as e: # For os.makedirs
            QMessageBox.critical(self, "Mirror Error", f"Failed to create directory structure: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Mirror Error", f"Failed to mirror files: {e}")


    def show_extraction_dialog(self):
        """Show dialog for extracting metadata from filenames."""
        if not self.all_files:
            QMessageBox.information(self, "No Files", "Please load some files first.")
            return

        dialog = FilenameExtractorDialog(self)
        dialog.exec()

    def show_settings_dialog(self):
        """Show the comprehensive settings dialog."""
        dialog = SettingsDialog(self)
        dialog.exec()

    def drag_enter_event(self, event): # Renamed from dragEnterEvent
        """Handle drag enter events for file dropping."""
        if event.mimeData().hasUrls():
            audio_files = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.wav', '.wave')):
                        audio_files.append(file_path)
                    elif os.path.isdir(file_path):
                        audio_files.append(file_path)

            if audio_files:
                event.acceptProposedAction()
                return

        event.ignore()

    def drag_move_event(self, event): # Renamed from dragMoveEvent
        """Handle drag move events."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def drop_event(self, event): # Renamed from dropEvent
        """Handle drop events when files are dropped onto the application."""
        if event.mimeData().hasUrls():
            file_paths = []

            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()

                    if os.path.isfile(path) and path.lower().endswith(('.wav', '.wave')):
                        file_paths.append(path)
                    elif os.path.isdir(path):
                        for root, _dirs, files in os.walk(path): # dirs unused
                            for file_item in files: # renamed file to file_item
                                if file_item.lower().endswith('.wav'):
                                    file_paths.append(os.path.join(root, file_item))

            if file_paths:
                self.load_files_from_paths(file_paths)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

class BackgroundAgent(QThread):
    """Base class for background processing agents."""
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_active = False
        self.interval = 30000  # 30 seconds default

    def run(self):
        """Override in subclasses."""
        # TODO: Add docstring
        pass

    def stop_agent(self):
        """Stop the agent gracefully."""
        self.is_active = False
        self.quit()
        self.wait()

class AutoSaveAgent(BackgroundAgent):
    """Agent for automatically saving pending changes."""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.interval = 30000  # 30 seconds

    def run(self):
        """Runs the auto-save agent loop."""
        self.is_active = True
        while self.is_active:
            self.msleep(self.interval)
            if self.is_active and self.editor.changes_pending:
                try:
                    self.editor.save_all_changes()
                    self.status_changed.emit("Auto-save completed")
                except IOError as e: # More specific exception
                    self.error_occurred.emit(f"Auto-save failed (I/O): {e}")
                except Exception as e:
                    self.error_occurred.emit(f"Auto-save failed: {type(e).__name__} - {e}")


class FileWatcherAgent(BackgroundAgent):
    """Agent for monitoring external file changes."""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.watcher = QFileSystemWatcher(self)

    def run(self):
        """Runs the file watcher agent."""
        self.is_active = True
        file_paths = [fp for fp, _ in self.editor.all_files]
        if file_paths:
            self.watcher.addPaths(file_paths)
            self.watcher.fileChanged.connect(self.on_file_changed)

    def on_file_changed(self, path):
        """Handles file changed signal from QFileSystemWatcher."""
        self.status_changed.emit(f"External change detected: {os.path.basename(path)}")

class ValidationAgent(BackgroundAgent):
    """Agent for validating metadata integrity."""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.interval = 60000  # 1 minute

    def run(self):
        """Runs the validation agent loop."""
        self.is_active = True
        while self.is_active:
            self.msleep(self.interval)
            if self.is_active:
                try:
                    missing_files = 0
                    for file_path, _ in self.editor.all_files:
                        if not os.path.exists(file_path):
                            missing_files += 1

                    if missing_files > 0:
                        self.status_changed.emit(f"Warning: {missing_files} files missing")
                    else:
                        self.status_changed.emit("Validation passed")
                except Exception as e:
                    self.error_occurred.emit(f"Validation error: {type(e).__name__} - {e}")

class BackgroundAgentManager(QObject):
    """Manages all background agents."""
    status_changed = pyqtSignal(str)

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.agents = {}

    def start_agents(self):
        """Start all background agents."""
        try:
            self.agents['autosave'] = AutoSaveAgent(self.editor, self)
            self.agents['filewatcher'] = FileWatcherAgent(self.editor, self)
            self.agents['validation'] = ValidationAgent(self.editor, self)

            for agent_name, agent in self.agents.items(): # Iterate with name for better logging
                agent.status_changed.connect(self.status_changed.emit)
                agent.error_occurred.connect(self.status_changed.emit)
                agent.start()
                print(f"{agent_name.capitalize()} agent started.")


            self.status_changed.emit("Background agents started")
        except Exception as e:
            self.status_changed.emit(f"Agent startup error: {type(e).__name__} - {e}")

    def stop_agents(self):
        """Stop all background agents."""
        for agent_name, agent in self.agents.items(): # Iterate with name for better logging
            agent.stop_agent()
            print(f"{agent_name.capitalize()} agent stopped.")
        self.agents.clear()
        self.status_changed.emit("Background agents stopped")

class CSVMatchWizard(QDialog):
    """Dialog for matching CSV data with audio files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CSV Match Wizard")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("CSV matching functionality not yet implemented."))

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

class FilenameParser:
    """Class for parsing metadata from filenames using patterns."""

    PATTERNS = {
        "Show_Category_Scene_Take": {
            "pattern": r"^([^_]+)_([^_]+)_(?:Sc|Scene|S)([^_]+)_(?:T|Take|)(\d+)(?:\.wav|\.wave)?$",
            "fields": ["Show", "Category", "Scene", "Take"],
            "description": "Show_Category_SceneX_Take (e.g., PR2_Allen_Sc5.14D_01.wav)"
        },
        "Show_Scene_Take": {
            "pattern": r"^([^_]+)_(?:Sc|Scene|S)([^_]+)_(?:T|Take|)(\d+)(?:\.wav|\.wave)?$",
            "fields": ["Show", "Scene", "Take"],
            "description": "Show_SceneX_Take (e.g., PR2_Sc5.14D_01.wav)"
        },
        "Category_Scene_Take": {
            "pattern": r"^([^_]+)_(?:Sc|Scene|S)([^_]+)_(?:T|Take|)(\d+)(?:\.wav|\.wave)?$",
            "fields": ["Category", "Scene", "Take"],
            "description": "Category_SceneX_Take (e.g., Allen_Sc5.14D_01.wav)"
        },
        "Scene_Take_Category": {
            "pattern": r"^(?:Sc|Scene|S)([^_]+)_(?:T|Take|)(\d+)_([^_.]+)(?:\.wav|\.wave)?$",
            "fields": ["Scene", "Take", "Category"],
            "description": "SceneX_Take_Category (e.g., Sc5.14D_01_Allen.wav)"
        }
    }

    @classmethod
    def parse_filename(cls, filename, pattern_name):
        """Parse a filename using the specified pattern."""
        # Imports are already at module level
        if pattern_name not in cls.PATTERNS:
            return {}

        pattern_info = cls.PATTERNS[pattern_name]
        pattern_regex = pattern_info["pattern"] # Renamed pattern to pattern_regex
        fields = pattern_info["fields"]

        basename = os.path.basename(filename)

        match = re.match(pattern_regex, basename, re.IGNORECASE)
        if not match:
            return {}

        result = {}
        for i, field in enumerate(fields):
            if i < len(match.groups()):
                value = match.group(i + 1).strip()
                if value:
                    result[field] = value

        return result

    @classmethod
    def preview_extraction(cls, filenames, pattern_name):
        """Preview what would be extracted from a list of filenames."""
        results = []
        for filename in filenames:
            parsed = cls.parse_filename(filename, pattern_name)
            results.append({
                'filename': os.path.basename(filename),
                'extracted': parsed
            })
        return results

class FilenameExtractorDialog(QDialog):
    """Dialog for extracting metadata from filenames."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_editor = parent
        self.setWindowTitle("Extract Metadata from Filenames")
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        header = QLabel("Extract metadata from filenames using pattern matching")
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(header)

        pattern_group = QGroupBox("Pattern Selection")
        pattern_layout = QVBoxLayout(pattern_group)

        self.pattern_combo = QComboBox()
        for name, info in FilenameParser.PATTERNS.items():
            self.pattern_combo.addItem(f"{name}: {info['description']}", name)
        self.pattern_combo.currentTextChanged.connect(self.update_preview)
        pattern_layout.addWidget(QLabel("Select pattern:"))
        pattern_layout.addWidget(self.pattern_combo)

        layout.addWidget(pattern_group)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.selected_only_cb = QCheckBox("Apply to selected files only")
        self.overwrite_cb = QCheckBox("Overwrite existing metadata")
        self.overwrite_cb.setChecked(False)

        options_layout.addWidget(self.selected_only_cb)
        options_layout.addWidget(self.overwrite_cb)

        layout.addWidget(options_group)

        button_layout = QHBoxLayout()

        self.preview_btn = QPushButton("Update Preview")
        self.preview_btn.clicked.connect(self.update_preview)

        self.apply_btn = QPushButton("Apply Extraction")
        self.apply_btn.clicked.connect(self.apply_extraction)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.preview_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.update_preview()

    def get_target_files(self):
        """Get the list of files to process."""
        if not self.parent_editor or not hasattr(self.parent_editor, 'all_files'):
            return []

        if self.selected_only_cb.isChecked():
            selected_indices = {item.row() for item in self.parent_editor.table.selectedItems()}
            # Map visual row index to actual all_files index
            files = [
                self.parent_editor.all_files[self.parent_editor.table.item(row, 0).data(Qt.ItemDataRole.UserRole)][0]
                for row in selected_indices
                if row < self.parent_editor.table.rowCount() and self.parent_editor.table.item(row, 0)
            ]
            return files
        return [file_path for file_path, _ in self.parent_editor.all_files]

    def update_preview(self):
        """Update the preview table."""
        if not self.parent_editor:
            return

        pattern_name = self.pattern_combo.currentData()
        if not pattern_name:
            return

        files = self.get_target_files()
        if not files:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return

        results = FilenameParser.preview_extraction(files, pattern_name)

        if results:
            all_fields = set()
            for result in results:
                all_fields.update(result['extracted'].keys())
            all_fields_list = sorted(list(all_fields)) # Renamed to avoid conflict

            self.preview_table.setColumnCount(len(all_fields_list) + 1)
            headers = ['Filename'] + all_fields_list
            self.preview_table.setHorizontalHeaderLabels(headers)

            self.preview_table.setRowCount(min(len(results), 10))

            for row, result in enumerate(results[:10]):
                item = QTableWidgetItem(result['filename'])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.preview_table.setItem(row, 0, item)

                for col, field in enumerate(all_fields_list, 1):
                    value = result['extracted'].get(field, '')
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.preview_table.setItem(row, col, item)

            self.preview_table.resizeColumnsToContents()

            matched_count = sum(1 for r in results if r['extracted'])
            total_count = len(results)
            # status_text = f"Matched: {matched_count}/{total_count} files" # status_text unused
            # if total_count > 10:
            #     status_text += " (showing first 10)"

        else:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)

    def apply_extraction(self):
        """Apply the extraction to files."""
        if not self.parent_editor:
            return

        pattern_name = self.pattern_combo.currentData()
        if not pattern_name:
            return

        files_to_process = self.get_target_files() # Renamed to avoid conflict
        if not files_to_process:
            QMessageBox.warning(self, "No Files", "No files selected for extraction.")
            return

        commands = []
        extracted_count = 0

        for file_path in files_to_process:
            file_index = None
            for i, (fp, _) in enumerate(self.parent_editor.all_files):
                if fp == file_path:
                    file_index = i
                    break

            if file_index is None:
                continue

            extracted = FilenameParser.parse_filename(file_path, pattern_name)
            if not extracted:
                continue

            current_metadata = self.parent_editor.all_files[file_index][1]

            file_had_extraction = False # Flag to track if any field was extracted for this file
            for field, value in extracted.items():
                # Ensure field is a valid column in the table (excluding "File Path")
                # This check might be too restrictive if patterns extract fields not in table
                # valid_fields = [self.parent_editor.table.horizontalHeaderItem(c).text()
                #                 for c in range(self.parent_editor.table.columnCount())
                #                 if self.parent_editor.table.horizontalHeaderItem(c).text() != "File Path"]
                # if field not in valid_fields:
                #     continue

                old_value = current_metadata.get(field, '')

                if not self.overwrite_cb.isChecked() and old_value:
                    continue

                if old_value != value:
                    cmd = MetadataEditCommand(
                        self.parent_editor, file_index, field, old_value, value
                    )
                    commands.append(cmd)
                    file_had_extraction = True
            if file_had_extraction:
                extracted_count +=1


        if not commands:
            QMessageBox.information(
                self, "No Changes",
                "No metadata changes were made. "
                "Files may already contain the extracted metadata or fields were not targeted."
            )
            return

        if len(commands) > 1:
            batch_cmd_desc = f"Extract metadata from {extracted_count} filenames"
            batch_cmd = BatchCommand(batch_cmd_desc, commands)
            self.parent_editor.undo_redo_stack.push(batch_cmd)
        elif len(commands) == 1:
            self.parent_editor.undo_redo_stack.push(commands[0])


        self.parent_editor.update_table() # update_table was called filter_table before
        self.parent_editor.update_undo_redo_buttons()

        QMessageBox.information(
            self, "Extraction Complete",
            f"Successfully extracted metadata from {extracted_count} filenames.\n"
            f"{len(commands)} metadata fields updated."
        )

        self.accept()

def main():
    """Main function to run the application."""
    app = QApplication(sys.argv)
    window = AudioMetadataEditor()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support() # For PyInstaller/cx_Freeze
    main()