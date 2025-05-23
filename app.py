#!/usr/bin/env python3
import sys
import os
import re
import shutil  # For file copying operations
import json
import wav_metadata
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, 
                             QTableWidgetItem, QVBoxLayout, QWidget, QFileDialog,
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView,
                             QLineEdit, QLabel, QComboBox, QGroupBox, QFormLayout,
                             QDialog, QSpinBox, QSplitter, QFrame, QToolBar, 
                             QStatusBar, QStyle, QSizePolicy, QStyledItemDelegate,
                             QGridLayout, QListWidget, QCheckBox, QProgressDialog,
                             QMenu, QScrollArea, QStackedWidget, QListWidgetItem,
                             QTextEdit)
from PyQt6.QtCore import Qt, QMimeData, QSortFilterProxyModel, QSize, QMargins, QPropertyAnimation, QEasingCurve, QTimer, QRect, pyqtProperty, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor, QIcon, QFont, QPainter, QBrush, QPen, QPainterPath, QPixmap, QAction, QKeySequence, QShortcut
from PyQt6.QtSvg import QSvgRenderer
import threading
import csv

# Undo/Redo Command framework
class UndoRedoCommand:
    """Base class for undo/redo commands"""
    
    def __init__(self, description):
        """Initialize with a description of what the command does"""
        self.description = description
    
    def execute(self):
        """Execute the command - to be overridden by subclasses"""
        # This method should perform the actual operation
        # and return True on success, False on failure
        return True
    
    def undo(self):
        """Undo the command - to be overridden by subclasses"""
        # This method should undo the operation performed by execute()
        # and return True on success, False on failure
        return True
    
    def redo(self):
        """Redo the command (typically the same as execute)"""
        # By default, redo is the same as execute
        # Subclasses can override if needed
        return self.execute()

class MetadataEditCommand(UndoRedoCommand):
    """Command to edit metadata in a WAV file"""
    
    def __init__(self, editor, file_index, field, old_value, new_value):
        """Initialize with file index and metadata changes"""
        super().__init__(f"Edit {field}")
        
        self.editor = editor
        self.file_index = file_index
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
    
    def execute(self):
        """Execute the metadata change"""
        try:
            # Update the metadata in memory
            file_path, metadata = self.editor.all_files[self.file_index]
            metadata[self.field] = self.new_value
            self.editor.all_files[self.file_index] = (file_path, metadata)
            
            # Update the UI
            self.editor.update_table_cell(self.file_index, self.field, self.new_value)
            
            # Mark changes as pending for save
            self.editor.changes_pending = True
            
            return True
        except Exception as e:
            print(f"Error executing metadata edit: {str(e)}")
            return False
    
    def undo(self):
        """Revert the metadata change"""
        try:
            # Revert metadata in memory
            file_path, metadata = self.editor.all_files[self.file_index]
            metadata[self.field] = self.old_value
            self.editor.all_files[self.file_index] = (file_path, metadata)
            
            # Update the UI
            self.editor.update_table_cell(self.file_index, self.field, self.old_value)
            
            # Still mark changes as pending since we're just reverting in memory
            self.editor.changes_pending = True
            
            # Show status message
            self.editor.status_label.setText(f"Undid edit to {self.field}")
            
            return True
        except Exception as e:
            print(f"Error undoing metadata edit: {str(e)}")
            return False

class FileRenameCommand(UndoRedoCommand):
    """Command to rename a file"""
    
    def __init__(self, editor, file_index, old_path, new_path):
        """Initialize with file paths and index"""
        # Get the simple filename for description
        old_name = os.path.basename(old_path)
        new_name = os.path.basename(new_path)
        super().__init__(f"Rename '{old_name}' to '{new_name}'")
        
        self.editor = editor
        self.file_index = file_index
        self.old_path = old_path
        self.new_path = new_path
    
    def execute(self):
        """Execute the rename operation"""
        # Check if the new file path already exists
        if os.path.exists(self.new_path) and self.new_path != self.old_path:
            # Show error message if file already exists
            QMessageBox.warning(
                self.editor, 
                "File Already Exists", 
                f"Cannot rename to '{os.path.basename(self.new_path)}': A file with this name already exists."
            )
            return False
            
        try:
            # Rename the file
            os.rename(self.old_path, self.new_path)
            
            # Update the metadata in memory
            file_path, metadata = self.editor.all_files[self.file_index]
            self.editor.all_files[self.file_index] = (self.new_path, metadata)
            
            # Update the filename in the table
            self.editor.update_filename_in_table(self.file_index, os.path.basename(self.new_path))
            
            # Update status message
            self.editor.status_label.setText(f"Renamed '{os.path.basename(self.old_path)}' to '{os.path.basename(self.new_path)}'")
            
            return True
        except Exception as e:
            # Show error message if rename fails
            QMessageBox.critical(
                self.editor, 
                "Rename Error", 
                f"Error renaming file: {str(e)}"
            )
            return False
    
    def undo(self):
        """Undo the rename operation"""
        # Check if the old file path already exists (would be overwritten)
        if os.path.exists(self.old_path) and self.old_path != self.new_path:
            QMessageBox.warning(
                self.editor, 
                "Cannot Undo", 
                f"Cannot undo rename: A file named '{os.path.basename(self.old_path)}' already exists."
            )
            return False
            
        try:
            # Rename back to the original
            os.rename(self.new_path, self.old_path)
            
            # Update the metadata in memory
            file_path, metadata = self.editor.all_files[self.file_index]
            self.editor.all_files[self.file_index] = (self.old_path, metadata)
            
            # Update the table
            self.editor.update_filename_in_table(self.file_index, self.old_filename)
            return True
            
        except Exception as e:
            print(f"Error undoing rename: {str(e)}")
            return False

class BatchCommand(UndoRedoCommand):
    """Command that groups multiple commands together as a single operation"""
    
    def __init__(self, description, commands):
        """Initialize with a list of commands"""
        super().__init__(description)
        self.commands = commands
    
    def execute(self):
        """Execute all commands in sequence"""
        success_count = 0
        failed_commands = []
        
        # Try to execute all commands
        for i, command in enumerate(self.commands):
            try:
                if command.execute():
                    success_count += 1
                else:
                    failed_commands.append((i, command))
            except Exception as e:
                print(f"Error executing command in batch: {str(e)}")
                failed_commands.append((i, command))
        
        # If any commands failed, try to undo the successful ones
        if failed_commands:
            print(f"Batch command partially failed: {len(failed_commands)} of {len(self.commands)} failed")
            
            # Undo the successful commands in reverse order
            for i in range(success_count - 1, -1, -1):
                try:
                    self.commands[i].undo()
                except Exception as e:
                    print(f"Error undoing command during rollback: {str(e)}")
            
            return False
        
        return True
    
    def undo(self):
        """Undo all commands in reverse order"""
        success_count = 0
        failed_commands = []
        
        # Undo commands in reverse order
        for i in range(len(self.commands) - 1, -1, -1):
            try:
                if self.commands[i].undo():
                    success_count += 1
                else:
                    failed_commands.append((i, self.commands[i]))
            except Exception as e:
                print(f"Error undoing command in batch: {str(e)}")
                failed_commands.append((i, self.commands[i]))
        
        return len(failed_commands) == 0
    
    def redo(self):
        """Redo all commands in sequence"""
        return self.execute()

class FileRemoveCommand(UndoRedoCommand):
    """Command to remove one or more files from the disk and the application list."""
    
    def __init__(self, editor, file_data_list_to_remove):
        """
        Initialize with the editor and a list of file data to remove.
        Each item in file_data_list_to_remove should be a tuple:
        (original_index_in_all_files, file_path, metadata_dict)
        """
        description = f"Remove {len(file_data_list_to_remove)} file(s) from list" # Updated description
        super().__init__(description)
        self.editor = editor
        # Store a copy of the list and its items to avoid modification issues
        self.files_to_remove_data = [(idx, path, data.copy()) for idx, path, data in file_data_list_to_remove]
        # self.successfully_removed_paths = [] # Keep track of files actually deleted from disk - Now tracks files removed from list
        self.removed_file_paths_for_undo = []

    def execute(self):
        """Execute the file removal operation (from list only)."""
        self.removed_file_paths_for_undo = [] # Reset for current execution
        
        # Collect paths of files to be removed from the list
        paths_to_remove_from_list = {data[1] for data in self.files_to_remove_data}

        if not paths_to_remove_from_list:
            self.editor.status_label.setText("No files selected to remove from the list.")
            return False

        # Store paths that are actually found and will be removed, for undo purposes
        original_all_files_count = len(self.editor.all_files)
        
        # Filter out the files from self.editor.all_files
        new_all_files = []
        for path, meta in self.editor.all_files:
            if path in paths_to_remove_from_list:
                self.removed_file_paths_for_undo.append(path) # Track for undo
            else:
                new_all_files.append((path, meta))
        
        self.editor.all_files = new_all_files
        
        removed_count = original_all_files_count - len(self.editor.all_files)

        if removed_count == 0:
            self.editor.status_label.setText("Files to remove were not found in the current list.")
            return False # Indicate no change was made

        self.editor.changes_pending = True # Assuming removing from list is a pending change
        self.editor.filter_table()  # This will update filtered_rows and refresh the UI
        self.editor.status_label.setText(f"Removed {removed_count} file(s) from the list.")
        self.editor.update_undo_redo_buttons()
        return True

    def undo(self):
        """Undo the file removal (restores to list only)."""
        if not self.removed_file_paths_for_undo:
            self.editor.status_label.setText("Undo: No files were previously removed from the list by this action.")
            return True

        files_re_added_count = 0
        # Find the original data for the files that were removed
        # This relies on self.files_to_remove_data holding all originally targeted files
        for original_idx, file_path, metadata in self.files_to_remove_data:
            if file_path in self.removed_file_paths_for_undo: # Check if this specific file was indeed removed by execute()
                # Check if it's already back (e.g. if undo was called multiple times or manually added)
                if not any(f[0] == file_path for f in self.editor.all_files):
                    self.editor.all_files.append((file_path, metadata))
                    files_re_added_count +=1
        
        if files_re_added_count == 0:
             self.editor.status_label.setText(f"Undo: Files were already present in the list.")
             return True


        # Re-sort if a sort order is active
        if self.editor.current_sort_column_index != -1:
            try:
                self.editor.all_files.sort(
                    key=lambda item: self.editor._get_sort_key(item, self.editor.current_sort_column_index),
                    reverse=(self.editor.current_sort_order == Qt.SortOrder.DescendingOrder)
                )
            except Exception as e:
                print(f"Error during undo re-sorting: {e}")
        
        self.editor.changes_pending = True # Re-adding to list is a pending change
        self.editor.filter_table()
        self.editor.status_label.setText(f"Undo: Restored {files_re_added_count} file(s) to the list.")
        self.editor.update_undo_redo_buttons()
        # QMessageBox.information(self.editor, "Undo Information",
        #                         "The selected file(s) have been restored to the application list. "
        #                         "They were not previously deleted from your computer's file system by this application.")
        return True

class UndoRedoStack:
    """Stack to manage undo and redo operations"""
    
    def __init__(self, max_size=50):
        self.undo_stack = []
        self.redo_stack = []
        self.max_size = max_size
    
    def push(self, command):
        """Push a command onto the stack and execute it"""
        try:
            # Execute the command
            command.execute()
            
            # Add to undo stack
            self.undo_stack.append(command)
            
            # Clear the redo stack when a new command is added
            self.redo_stack.clear()
            
            # Limit the stack size
            if len(self.undo_stack) > self.max_size:
                self.undo_stack.pop(0)
                
            return True
        except Exception as e:
            print(f"Error executing command: {str(e)}")
            return False
    
    def undo(self):
        """Undo the last command"""
        if not self.undo_stack:
            return False
            
        try:
            # Pop the last command from the undo stack
            command = self.undo_stack.pop()
            
            # Undo the command
            command.undo()
            
            # Add to redo stack
            self.redo_stack.append(command)
            
            return True
        except Exception as e:
            print(f"Error undoing command: {str(e)}")
            return False
    
    def redo(self):
        """Redo the last undone command"""
        if not self.redo_stack:
            return False
            
        try:
            # Pop the last command from the redo stack
            command = self.redo_stack.pop()
            
            # Redo the command
            command.redo()
            
            # Add back to undo stack
            self.undo_stack.append(command)
            
            return True
        except Exception as e:
            print(f"Error redoing command: {str(e)}")
            return False
    
    def can_undo(self):
        """Check if there are commands to undo"""
        return len(self.undo_stack) > 0
    
    def can_redo(self):
        """Check if there are commands to redo"""
        return len(self.redo_stack) > 0
    
    def command_to_undo(self):
        """Get the command that would be undone next"""
        if not self.undo_stack:
            return None
        return self.undo_stack[-1]
    
    def command_to_redo(self):
        """Get the command that would be redone next"""
        if not self.redo_stack:
            return None
        return self.redo_stack[-1]
    
    def clear(self):
        """Clear both undo and redo stacks"""
        self.undo_stack.clear()
        self.redo_stack.clear()

class MacStyleDelegate(QStyledItemDelegate):
    """Custom delegate for macOS style table items"""
    def paint(self, painter, option, index):
        # These colors will be sourced from the main app's theme in a real scenario
        # For this example, we'll use common theme colors directly.
        # In a full refactor, these would be passed or accessed from a central theme manager.
        
        # Get theme colors (assuming they are somehow accessible, e.g. from parent app or a global theme)
        # This is a simplified approach for the edit. A more robust solution might involve
        # passing the theme to the delegate or having a singleton theme manager.
        # For now, we'll hardcode the intended new theme colors here for demonstration of the delegate part.
        
        # Core Palette
        CP_MEDIUM_TEAL = "#589DA4"
        CP_OFF_WHITE_BG = "#F0F5E2"
        
        # Text Colors
        TC_PRIMARY_ON_DARK = "#FFFFFF"
        TC_PRIMARY_ON_LIGHT = "#1A1A1A"

        # Slightly darker version of off_white_bg for alternating rows if not handled by stylesheet
        # ALT_ROW_BG = "#E6EBD5" # Example: darken_color(CP_OFF_WHITE_BG, 0.95)

        painter.save()
        
        if option.state & QStyle.StateFlag.State_Selected:
            # Use a theme color for selection
            painter.fillRect(option.rect, QColor(CP_MEDIUM_TEAL))
            painter.setPen(QColor(TC_PRIMARY_ON_DARK))
        else:
            # The QTableWidget's alternate-background-color stylesheet property should handle this.
            # Delegate just needs to paint a base background.
            painter.fillRect(option.rect, QColor(CP_OFF_WHITE_BG))
            painter.setPen(QColor(TC_PRIMARY_ON_LIGHT))

        text_rect = option.rect.adjusted(12, 6, -12, -6)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, index.data())
        
        painter.restore()


class AnimatedPushButton(QPushButton):
    """Custom button with click animation"""
    def __init__(self, text="", parent=None, normal_color_hex=None, hover_color_hex=None, click_color_hex=None, text_color_hex=None):
        super().__init__(text, parent)
        self.setObjectName("animated_button")
        self.setProperty("class", "secondary")

        # Theme colors to be passed or sourced from a central theme manager
        # Defaults are set if specific colors are not provided via constructor
        self._normal_color_hex = normal_color_hex if normal_color_hex else "#85A156" # CP_LIGHT_OLIVE_GREEN
        self._hover_color_hex = hover_color_hex if hover_color_hex else "#748D44"   # CP_OLIVE_GREEN
        self._click_color_hex = click_color_hex if click_color_hex else "#6A7F3C"   # Darker CP_OLIVE_GREEN
        self._text_color_hex = text_color_hex if text_color_hex else "#1A1A1A"       # TC_PRIMARY_ON_LIGHT

        self._normal_color = QColor(self._normal_color_hex)
        self._hover_color = QColor(self._hover_color_hex)
        self._click_color = QColor(self._click_color_hex)
        self._current_color = self._normal_color
        
        self._animation = QPropertyAnimation(self, b"background_color")
        self._animation.setDuration(150)
        
        # No inline styling here - use the stylesheet from apply_stylesheet
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def get_background_color(self):
        return self._current_color
        
    def set_background_color(self, color):
        if self._current_color != color:
            self._current_color = color
            # Update only the background color property
            self.setStyleSheet(f"background-color: {color.name()}");
            
    background_color = pyqtProperty(QColor, get_background_color, set_background_color)
    
    def enterEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._hover_color)
        self._animation.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._animation.stop()
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._normal_color)
        self._animation.start()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._animation.stop()
            self._animation.setStartValue(self._current_color)
            self._animation.setEndValue(self._click_color)
            self._animation.start()
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._animation.stop()
            self._animation.setStartValue(self._current_color)
            self._animation.setEndValue(self._hover_color if self.underMouse() else self._normal_color)
            self._animation.start()
        super().mouseReleaseEvent(event)


class AnimatedPrimaryButton(AnimatedPushButton):
    """Primary styled animated button"""
    def __init__(self, text="", parent=None):
        # These would come from the new theme definition
        normal_hex = "#27768A"  # CP_DARK_TEAL
        hover_hex = "#589DA4"    # CP_MEDIUM_TEAL
        click_hex = "#748D44"    # CP_OLIVE_GREEN (for distinct click)
        text_hex = "#FFFFFF"     # TC_PRIMARY_ON_DARK

        super().__init__(text, parent, normal_color_hex=normal_hex, hover_color_hex=hover_hex, click_color_hex=click_hex, text_color_hex=text_hex)
        # Override the class property to use primary button styling from stylesheet
        self.setProperty("class", "primary")
        self.setObjectName("animated_primary_button")

    # Override set_background_color to maintain primary button style (no border)
    def set_background_color(self, color):
        if self._current_color != color:
            self._current_color = color
            # Only update the background color while maintaining other styles from stylesheet
            self.setStyleSheet(f"background-color: {color.name()}");


class FileLoadWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    
    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
        
    def run(self):
        results = []
        total_files = len(self.file_paths)
        
        # Create a pool of workers for parallel processing
        cpu_count = max(1, multiprocessing.cpu_count() - 1)  # Leave one CPU free
        
        # Process files in batches to avoid memory issues
        batch_size = 50
        for i in range(0, total_files, batch_size):
            if self.isInterruptionRequested():
                break
                
            batch = self.file_paths[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=cpu_count) as executor:
                # Create a list to store futures and their corresponding file paths
                futures_with_paths = []
                for file_path in batch:
                    future = executor.submit(self.safe_read_metadata, file_path)
                    futures_with_paths.append((future, file_path))
                
                for j, (future, file_path) in enumerate(futures_with_paths):
                    if self.isInterruptionRequested():
                        break
                        
                    current_idx = i + j
                    try:
                        # Get the metadata result from the future (or empty metadata if it failed)
                        metadata = future.result()
                        # Add filename to metadata
                        metadata["Filename"] = os.path.basename(file_path)
                        results.append((file_path, metadata))
                    except Exception as e:
                        # If an exception occurred during metadata reading, create empty metadata
                        print(f"Error reading metadata for {file_path}: {str(e)}")
                        metadata = {
                            "Filename": os.path.basename(file_path),
                            "Show": "",
                            "Scene": "",
                            "Take": "",
                            "Category": "",
                            "Subcategory": "",
                            "Slate": "",
                            "ixmlNote": "",
                            "ixmlWildtrack": "",
                            "ixmlCircled": "",
                            "File Path": file_path,
                            "Error": str(e)
                        }
                    results.append((file_path, metadata))
                    
                    # Emit progress
                    self.progress.emit(current_idx + 1, total_files, os.path.basename(file_path))
                    
                    # Check if we should stop
                    if self.isInterruptionRequested():
                        break
            
            if self.isInterruptionRequested():
                break
                
        self.finished.emit(results)
        
    def safe_read_metadata(self, file_path):
        """Safely read metadata with proper error handling"""
        try:
            return wav_metadata.read_wav_metadata(file_path)
        except Exception as e:
            # Log the error and return empty metadata
            print(f"Error reading metadata: {str(e)}")
            # Create empty metadata dictionary
            return {
                "Show": "",
                "Scene": "",
                "Take": "",
                "Category": "",
                "Subcategory": "",
                "Slate": "",
                "ixmlNote": "",
                "ixmlWildtrack": "",
                "ixmlCircled": "",
                "File Path": file_path,
                "Error": str(e)
            }


class AudioMetadataEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Metadata Editor")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)
        
        # Configure for frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Theme setting - 'light' or 'dark'
        self.current_theme = 'light'
        
        # Set the application style
        self.apply_stylesheet()
        
        # Setup UI
        self.central_widget = QWidget()
        self.central_widget.setObjectName("central_widget")
        self.setCentralWidget(self.central_widget)
        
        # Initialize undo/redo stack
        self.undo_redo_stack = UndoRedoStack()
        
        # Initialize sort state
        self.current_sort_column_index = -1  # No column sorted initially
        self.current_sort_order = Qt.SortOrder.AscendingOrder
        
        # Main layout with optimized margins
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)  # Slightly increased margins for better spacing
        main_layout.setSpacing(10)  # Increased spacing between elements
        
        # Add integrated title bar with window controls and app controls
        self.create_integrated_title_bar(main_layout)
        
        # Set up keyboard shortcuts
        # Commenting this out temporarily as the method is not yet implemented
        # self.setup_shortcuts()
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Create the main splitter for content and side panel
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(1)
        self.main_splitter.setChildrenCollapsible(False)
        
        # Main content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(15)
        
        # Create mirror panel (hidden by default)
        self.mirror_panel = MirrorPanel(self)
        self.mirror_panel.setVisible(False)  # Start hidden
        self.mirror_panel.setMinimumWidth(350)
        self.mirror_panel.setMaximumWidth(400)
        
        # Add widgets to splitter
        self.main_splitter.addWidget(self.content_widget)
        self.main_splitter.addWidget(self.mirror_panel)
        
        # Set splitter sizes to show content and hide panel initially
        self.main_splitter.setSizes([1, 0])
        
        # Add splitter to main layout
        main_layout.addWidget(self.main_splitter)
        
        # Search and table container
        content_container = QWidget()
        content_container.setProperty("class", "content-container")
        content_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Table container with macOS-style rounded corners and shadow
        table_container = QWidget()
        table_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table_container.setProperty("class", "table-container")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Metadata table
        self.metadata_table = QTableWidget(0, 11)  # rows, cols - increased to 11 for Filename and File Path
        self.metadata_table.setHorizontalHeaderLabels([
            "Filename", "Show", "Scene", "Take", "Category", 
            "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled", "File Path"
        ])
        self.metadata_table.setAlternatingRowColors(True)
        self.metadata_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.metadata_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.SelectedClicked)
        self.metadata_table.verticalHeader().setVisible(False)
        
        # Enable sorting by column header click
        self.metadata_table.setSortingEnabled(False)
        self.metadata_table.horizontalHeader().sectionClicked.connect(self.sort_table_by_column)
        
        # Set horizontal header properties
        header = self.metadata_table.horizontalHeader()
        
        # Make all columns resizable (Interactive mode)
        for col in range(self.metadata_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            
        # Initially size columns to their content
        self.metadata_table.resizeColumnsToContents()
        
        # Set minimum size for all columns
        header.setMinimumSectionSize(100)
        
        # Make filename and file path columns wider initially
        self.metadata_table.setColumnWidth(0, 200)  # Filename column
        self.metadata_table.setColumnWidth(10, 250)  # File Path column
        
        # Set delegate for macOS-style appearance
        self.metadata_table.setItemDelegate(MacStyleDelegate())
        
        # Connect signals
        self.metadata_table.itemChanged.connect(self.update_metadata)
        self.metadata_table.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Set up right-click context menu
        self.setup_table_context_menu()
        
        table_layout.addWidget(self.metadata_table)
        
        content_layout.addWidget(table_container, 1)  # 1 = stretch factor
        
        self.content_layout.addWidget(content_container, 1)  # 1 = stretch factor
        
        # Status bar at the bottom - subtle, Apple-style
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "status-label")
        self.content_layout.addWidget(self.status_label)
        
        # Initialize search components (temporary fix)
        self.search_input = QLineEdit()
        self.current_search_field = "All Fields"
        
        # Data storage
        self.all_files = []
        self.filtered_rows = []
        self.changes_pending = False
        
        # Enable animations in the application
        self.animations_enabled = True
        
        # For debounced search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_table)
        
        # File load worker
        self.file_load_worker = None
        self.progress_dialog = None
    
    def _get_sort_key(self, item, column_index):
        """Helper function to get the sort key for a given item and column index."""
        file_path, metadata = item
        
        # Column mapping based on self.metadata_table.setHorizontalHeaderLabels
        # ["Filename", "Show", "Scene", "Take", "Category", "Subcategory", "Slate", 
        #  "ixmlNote", "ixmlWildtrack", "ixmlCircled", "File Path"]
        
        value = ""
        if column_index == 0:  # Filename
            value = os.path.basename(file_path)
        elif column_index == 1:  # Show
            value = metadata.get("Show", "")
        elif column_index == 2:  # Scene
            value = metadata.get("Scene", "")
        elif column_index == 3:  # Take
            take_str = metadata.get("Take", "")
            try:
                # Convert to int, then to a zero-padded string for correct lexicographical sorting
                return "{:08d}".format(int(take_str)) 
            except ValueError:
                # If not an int, return as a lowercase string to sort with other strings
                return take_str.lower()
        elif column_index == 4:  # Category
            value = metadata.get("Category", "")
        elif column_index == 5:  # Subcategory
            value = metadata.get("Subcategory", "")
        elif column_index == 6:  # Slate
            value = metadata.get("Slate", "")
        elif column_index == 7:  # ixmlNote
            value = metadata.get("ixmlNote", "")
        elif column_index == 8:  # ixmlWildtrack
            value = metadata.get("ixmlWildtrack", "") 
        elif column_index == 9:  # ixmlCircled
            value = metadata.get("ixmlCircled", "")
        elif column_index == 10: # File Path
            value = file_path
            
        # Ensure consistent string type for sorting, and make it case-insensitive
        return str(value).lower()

    def sort_table_by_column(self, logical_index):
        """Sorts the table by the clicked column header."""
        if self.current_sort_column_index == logical_index:
            # Toggle sort order
            if self.current_sort_order == Qt.SortOrder.AscendingOrder:
                self.current_sort_order = Qt.SortOrder.DescendingOrder
            else:
                self.current_sort_order = Qt.SortOrder.AscendingOrder
        else:
            # New column clicked, default to ascending
            self.current_sort_column_index = logical_index
            self.current_sort_order = Qt.SortOrder.AscendingOrder
            
        # Update header sort indicator
        self.metadata_table.horizontalHeader().setSortIndicator(
            self.current_sort_column_index,
            self.current_sort_order
        )
            
        # Sort self.all_files
        if self.all_files:
            try:
                self.all_files.sort(
                    key=lambda item: self._get_sort_key(item, self.current_sort_column_index),
                    reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder)
                )
            except Exception as e:
                print(f"Error during sorting: {e}")
                # Optionally, revert sort or show an error to the user
                return

        # After sorting all_files, the filter_table method will rebuild
        # filtered_rows based on the new order and then update the display.
        self.filter_table()

    def apply_stylesheet(self):
        """Apply a modern macOS-inspired stylesheet with translucent elements and dark mode support"""

        # Helper function to darken a color
        def darken_color(hex_color, factor):
            if hex_color.startswith('#'):
                hex_color = hex_color[1:]
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            r = max(0, int(r * factor))
            g = max(0, int(g * factor))
            b = max(0, int(b * factor))
            return f"#{r:02x}{g:02x}{b:02x}"

        # Helper function to lighten a color
        def lighten_color(hex_color, factor):
            if hex_color.startswith('#'):
                hex_color = hex_color[1:]
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            r = min(255, int(r * factor))
            g = min(255, int(g * factor))
            b = min(255, int(b * factor))
            return f"#{r:02x}{g:02x}{b:02x}"

        # --- Theme Definition based on current mode ---
        if self.current_theme == 'light':
            # Light Theme Colors - Inspired by ClickUp (Brighter, clean aesthetic)
            CP = {
                "purple": "#7B61FF", # ClickUp Purple as primary accent
                "blue_accent": "#40DDFF",
                "pink_accent": "#FA12E3",
                "navy_deep": "#101F52", # For dark text or accents

                "light_bg_primary": "#FFFFFF", # Pure white for main background
                "light_bg_secondary": "#F7F7F9", # Very light grey for secondary elements
                "light_bg_tertiary": "#EFF0F2",  # Slightly darker grey for cards/borders

                "accent_teal_clickup": "#40c4aa", # Teal accent from ClickUp
                "grey_text_light": "#5E6C84",  # Softer grey for secondary text on light bg
                "dark_text_primary": "#172B4D", # Primary dark text (near black/navy)
                
                # Additional colors needed for buttons
                "light_olive_green": "#85A156",
                "olive_green": "#748D44",
                "dark_teal": "#27768A",
                "medium_teal": "#589DA4"
            }

            TC = {
                "primary_on_light": CP["dark_text_primary"],
                "secondary_on_light": CP["grey_text_light"],
                "primary_on_dark_accent": CP["light_bg_primary"], # Text for on accent-colored backgrounds
                "primary_on_dark": "#FFFFFF", # Adding this for button text on dark backgrounds
                "link": CP["purple"],
            }
            
            UA = {
                "border_light": CP["light_bg_tertiary"],
                "border_medium": darken_color(CP["light_bg_tertiary"], 0.95),
                
                "scrollbar_track": CP["light_bg_secondary"],
                "scrollbar_handle": CP["accent_teal_clickup"],
                "scrollbar_handle_hover": darken_color(CP["accent_teal_clickup"], 0.9),
    
                "title_bar_bg": CP["light_bg_secondary"],
                
                "selection_bg": CP["purple"],
                "selection_fg": TC["primary_on_dark_accent"],
    
                "window_bg": CP["light_bg_primary"],
                "content_bg": CP["light_bg_primary"],
                
                "table_bg": CP["light_bg_primary"],
                "table_alt_bg": CP["light_bg_secondary"],
    
                "tooltip_bg": CP["dark_text_primary"],
                "tooltip_fg": CP["light_bg_primary"],

                # Button specific variations - ClickUp inspired for light mode
                "button_secondary_bg": CP["light_bg_tertiary"],
                "button_secondary_fg": TC["primary_on_light"],
                "button_secondary_hover_bg": darken_color(CP["light_bg_tertiary"], 0.95),
                "button_secondary_pressed_bg": darken_color(CP["light_bg_tertiary"], 0.9),
                "button_secondary_border": darken_color(CP["light_bg_tertiary"], 0.9),
    
                "button_primary_bg": CP["purple"],
                "button_primary_fg": TC["primary_on_dark_accent"],
                "button_primary_hover_bg": lighten_color(CP["purple"], 1.1),
                "button_primary_pressed_bg": lighten_color(CP["purple"], 1.2), 
            }
        else:
            # Dark Theme Colors - Inspired by ClickUp
            CP = {
                "purple": "#7B61FF",  # ClickUp's primary purple (slightly adjusted from #7612FA for better visibility if needed)
                "blue_accent": "#40DDFF", # ClickUp's Blue
                "pink_accent": "#FA12E3",  # ClickUp's Pink
                "yellow_accent": "#FFD700", # ClickUp's Yellow
                "navy_deep": "#101F52",    # ClickUp's Navy

                # Core UI Colors for Dark Mode based on common ClickUp screenshots
                "dark_bg_primary": "#1E1F21", # A common dark background in ClickUp
                "dark_bg_secondary": "#2C2D30", # Slightly lighter for elements
                "dark_bg_tertiary": "#3A3B3F",  # For cards, modals, etc.

                "accent_teal_clickup": "#40c4aa", # A teal/turquoise often seen as accent
                "grey_text_clickup": "#c1c2c6",  # Common secondary text color
                "almost_white_text": "#F0F0F0" # Primary text on dark
            }

            TC = {
                "primary_on_dark": CP["almost_white_text"],
                "secondary_on_dark": CP["grey_text_clickup"],
                "primary_on_light_accent": CP["dark_bg_primary"], # Text for on accent-colored backgrounds
                "link": CP["blue_accent"],
            }

            UA = {
                "border_light": lighten_color(CP["dark_bg_primary"], 1.2), # e.g. #2A2B2E
                "border_medium": lighten_color(CP["dark_bg_primary"], 1.4), # e.g. #38393D

                "scrollbar_track": CP["dark_bg_secondary"],
                "scrollbar_handle": CP["accent_teal_clickup"],
                "scrollbar_handle_hover": lighten_color(CP["accent_teal_clickup"], 1.1),

                "title_bar_bg": CP["dark_bg_secondary"], # "#242424", - original value
                
                "selection_bg": CP["purple"], # Using ClickUp Purple for selection
                "selection_fg": TC["primary_on_dark"],

                "window_bg": CP["dark_bg_primary"],
                "content_bg": CP["dark_bg_primary"],
                
                "table_bg": CP["dark_bg_primary"],
                "table_alt_bg": CP["dark_bg_secondary"], # darken_color(CP["dark_bg_primary"], 1.1) for subtle difference

                "tooltip_bg": CP["dark_bg_tertiary"],
                "tooltip_fg": TC["primary_on_dark"],
                
                # Button specific variations - ClickUp inspired
                "button_secondary_bg": CP["dark_bg_tertiary"],
                "button_secondary_fg": TC["primary_on_dark"],
                "button_secondary_hover_bg": lighten_color(CP["dark_bg_tertiary"], 1.1),
                "button_secondary_pressed_bg": lighten_color(CP["dark_bg_tertiary"], 1.2),
                "button_secondary_border": CP["dark_bg_tertiary"],

                "button_primary_bg": CP["purple"], # ClickUp Purple
                "button_primary_fg": TC["primary_on_dark"],
                "button_primary_hover_bg": lighten_color(CP["purple"], 1.15),
                "button_primary_pressed_bg": lighten_color(CP["purple"], 1.25),
            }
            
        # Common button styles regardless of theme
        if self.current_theme == 'light':
            UA.update({
                # Button specific variations
                "button_secondary_bg": CP["light_olive_green"],
                "button_secondary_fg": TC["primary_on_light"],
                "button_secondary_hover_bg": CP["olive_green"],
                "button_secondary_pressed_bg": darken_color(CP["olive_green"], 0.9),
                "button_secondary_border": CP["olive_green"],
    
                "button_primary_bg": CP["dark_teal"],
                "button_primary_fg": TC["primary_on_dark"],
                "button_primary_hover_bg": CP["medium_teal"],
                "button_primary_pressed_bg": CP["olive_green"], # Using olive for distinct pressed
            })
        # --- End of New Theme Definition ---

        if sys.platform == "darwin":
            app_font = QFont(".AppleSystemUIFont", 12)
        else:
            app_font = QFont("Segoe UI", 12)
        QApplication.setFont(app_font)
        
        # ClickUp style requires less transparency in dark mode, more defined elements in light
        bg_opacity_dark = "1.0"
        bg_opacity_light = "1.0" # ClickUp light mode is typically opaque
        
        current_bg_opacity = bg_opacity_dark if self.current_theme == 'dark' else bg_opacity_light
        
        stylesheet = f"""
        QMainWindow {{
            background-color: {UA["window_bg"]};
            border: 1px solid {UA["border_medium"] if self.current_theme == 'dark' else UA["border_light"]}; /* Subtle border for dark, slightly more for light */
            border-radius: 8px; /* Softer radius like ClickUp */
        }}
        
        #central_widget {{
            background-color: {UA["window_bg"]}; /* Use window_bg instead of transparent */
            border-radius: 8px;
        }}
        
        .content-container {{
            background-color: {UA["content_bg"]};
            border-radius: 6px; /* Inner content slightly less rounded */
            padding: 5px; /* Add some padding */
        }}
        
        /* Default QPushButton: Secondary action button style - ClickUp like */
        QPushButton {{
            background-color: {UA["button_secondary_bg"]};
            color: {UA["button_secondary_fg"]};
            border: 1px solid {UA["button_secondary_border"] if self.current_theme == 'dark' else UA["border_medium"]};
            border-radius: 6px; 
            font-weight: 500; /* Medium weight, common in ClickUp */
            font-size: 13px;
            padding: 8px 14px; /* ClickUp buttons have generous padding */
            min-height: 30px; 
        }}
        
        QPushButton:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        QPushButton:pressed {{
            background-color: {UA["button_secondary_pressed_bg"]};
        }}

        QPushButton.secondary {{
            background-color: {UA["button_secondary_bg"]};
            color: {UA["button_secondary_fg"]};
            border: 1px solid {UA["button_secondary_border"] if self.current_theme == 'dark' else UA["border_medium"]};
            border-radius: 6px;
            font-weight: 500;
            font-size: 13px;
            padding: 8px 14px;
            min-height: 30px;
        }}
        
        QPushButton.secondary:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        QPushButton.secondary:pressed {{
            background-color: {UA["button_secondary_pressed_bg"]};
        }}

        #title_bar QPushButton {{
            padding: 6px 10px; /* Slightly less padding for title bar buttons */
            min-height: 28px;
        }}

        /* Primary action button style - ClickUp like */
        QPushButton.primary {{
            background-color: {UA["button_primary_bg"]};
            color: {UA["button_primary_fg"]};
            border: none;
            border-radius: 6px;
            font-weight: bold; /* Bold for primary actions */
            font-size: 13px;
            padding: 8px 14px;
            min-height: 30px;
        }}
        
        QPushButton.primary:hover {{
            background-color: {UA["button_primary_hover_bg"]};
        }}
        
        QPushButton.primary:pressed {{
            background-color: {UA["button_primary_pressed_bg"]};
        }}
        
        QLineEdit {{
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 8px 10px; /* More padding for better feel */
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 13px;
        }}
        
        QLineEdit:focus {{
            border: 1px solid {CP["purple"]}; 
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
        }}
        
        QLabel {{
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 13px;
            background-color: transparent; /* Ensure labels don't obscure backgrounds */
        }}
        
        #title_label {{ 
            font-size: 16px; /* Slightly smaller for a cleaner look */
            font-weight: 600; /* Semibold */
            color: {CP["purple"]};
        }}

        #app_title {{ 
            font-weight: 600; /* Semibold */
            font-size: 15px;
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
        }}
        
        QTableWidget {{
            border: 1px solid {UA["border_medium"]};
            background-color: {UA["table_bg"]}; 
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
            alternate-background-color: {UA["table_alt_bg"]}; 
            gridline-color: {UA["border_light"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            border-radius: 6px;
            font-size: 13px;
        }}
        
        QHeaderView::section {{
            background-color: {UA["title_bar_bg"]}; 
            padding: 10px 8px; /* More padding */
            border: none;
            border-bottom: 1px solid {UA["border_medium"]};
            font-weight: 600; /* Semibold headers */
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 12px; /* Slightly smaller header font */
        }}
        
        .status-label {{
            color: {TC["secondary_on_light"] if self.current_theme == 'light' else TC["secondary_on_dark"]};
            font-size: 12px;
            padding: 6px 4px;
        }}
        
        QDialog {{
            background-color: {UA["window_bg"]}; /* Use window_bg for consistency */
            border: 1px solid {UA["border_medium"]};
            border-radius: 8px;
        }}
        
        QComboBox {{
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 7px 10px;
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
            font-size: 13px;
        }}
        
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 22px;
            border-left: 1px solid {UA["border_light"]};
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }}
        
        QComboBox::down-arrow {{
            image: url(none); /* Consider using an SVG icon if possible or a char like ▼ */
            width: 10px;
            height: 10px;
        }}
        
        QComboBox QAbstractItemView {{ 
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_tertiary"]}; 
            border: 1px solid {UA["border_medium"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
            padding: 4px;
            border-radius: 4px;
        }}
        
        QSpinBox {{
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 7px 10px;
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 13px;
        }}

        QSplitter::handle {{
            background-color: {UA["border_light"]}; /* Thinner, less obtrusive handles */
            width: 1px; /* For vertical splitter */
            height: 1px; /* For horizontal splitter */
        }}
        
        QMenu {{
            background-color: {CP["light_bg_secondary"] if self.current_theme == 'light' else CP["dark_bg_tertiary"]};
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 5px;
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 13px;
        }}
        
        QMenu::item {{
            padding: 8px 20px 8px 12px;
            border-radius: 4px;
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
        }}
        
        QMenu::item:selected {{
            background-color: {UA["selection_bg"]};
            color: {UA["selection_fg"]};
        }}
        
        QScrollBar:vertical {{
            border: none;
            background: {UA["scrollbar_track"]};
            width: 12px; /* Slightly wider for easier interaction */
            margin: 0px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {UA["scrollbar_handle"]};
            min-height: 25px;
            border-radius: 6px;
            border: 1px solid {darken_color(UA["scrollbar_handle"], 0.9) if self.current_theme == 'light' else lighten_color(UA["scrollbar_handle"], 1.1)}; /* Subtle border on handle */
        }}
        QScrollBar::handle:vertical:hover {{
            background: {UA["scrollbar_handle_hover"]};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px; /* No arrows for a cleaner look */
        }}
        
        QScrollBar:horizontal {{
            border: none;
            background: {UA["scrollbar_track"]};
            height: 12px;
            margin: 0px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:horizontal {{
            background: {UA["scrollbar_handle"]};
            min-width: 25px;
            border-radius: 6px;
            border: 1px solid {darken_color(UA["scrollbar_handle"], 0.9) if self.current_theme == 'light' else lighten_color(UA["scrollbar_handle"], 1.1)};
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {UA["scrollbar_handle_hover"]};
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* Custom title bar */
        #title_bar {{
            background-color: {UA["title_bar_bg"]};
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom: 1px solid {UA["border_medium"]};
            min-height: 44px; /* Ensure enough height */
        }}
        
        /* Title bar buttons need alignment */
        /* Title bar general button styles */
        #title_bar QPushButton {{
            vertical-align: middle;
            border-radius: 4px;
            min-height: 28px;
            max-height: 28px;
            padding: 3px;
        }}
        
        /* Text buttons in the title bar should have consistent width */
        #title_bar QPushButton[text]:not([text=""]) {{
            min-width: 64px;
            max-width: 64px;
            padding: 3px 2px;
        }}
        
        /* Action container buttons */
        #browse_button {{
            background-color: {UA["button_secondary_bg"]};
            border: 1px solid {UA["button_secondary_border"]};
        }}
        
        #browse_button:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        #extract_button {{
            background-color: {UA["button_secondary_bg"]};
            color: {UA["button_secondary_fg"]};
            border: 1px solid {UA["button_secondary_border"]};
            border-radius: 4px;
            font-weight: 500;
            font-size: 11px;
            padding: 3px 5px;
            text-align: center;
            max-height: 28px;
            min-height: 28px;
        }}
        
        #extract_button:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        /* Dark mode button */
        #dark_mode_button {{
            font-size: 11px;
            background-color: {UA["button_secondary_bg"]};
            border: 1px solid {UA["button_secondary_border"]};
        }}
        
        #dark_mode_button:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        /* Mirror panel button */
        #mirror_panel_button {{
            background-color: {UA["button_secondary_bg"]};
            border: 1px solid {UA["button_secondary_border"]};
        }}
        
        #mirror_panel_button:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        /* App title styling */
        #app_title {{
            font-weight: bold;
            font-size: 14px;
            color: {CP["dark_text_primary"] if self.current_theme == 'light' else CP["almost_white_text"]};
        }}
        
        /* Animated buttons styling */
        #animated_button {{
            background-color: {UA["button_secondary_bg"]};
            color: {UA["button_secondary_fg"]};
            border: 1px solid {UA["button_secondary_border"]};
            border-radius: 4px;
            font-weight: 500;
            font-size: 11px;
            padding: 3px 8px;
            max-height: 28px;
            min-height: 26px;
        }}
        
        #animated_button:hover {{
            background-color: {UA["button_secondary_hover_bg"]};
        }}
        
        #animated_button:pressed {{
            background-color: {UA["button_secondary_pressed_bg"]};
        }}
        
        #animated_primary_button {{
            background-color: {UA["button_primary_bg"]};
            color: {UA["button_primary_fg"]};
            border: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
            padding: 3px 5px;
            text-align: center;
            max-height: 28px;
            min-height: 28px;
        }}
        
        #animated_primary_button:hover {{
            background-color: {UA["button_primary_hover_bg"]};
        }}
        
        #animated_primary_button:pressed {{
            background-color: {UA["button_primary_pressed_bg"]};
        }}

        /* macOS-like window control buttons - standard fixed colors */
        #close_button, #minimize_button, #maximize_button {{
            min-width: 12px; min-height: 12px;
            max-width: 12px; max-height: 12px;
            border-radius: 6px;
            border: 1px solid rgba(0, 0, 0, 0.1);
            padding: 0;
            text-align: center;
            font-weight: bold;
        }}
        
        #close_button {{
            background-color: #ff5f57;
            color: #640a03;
        }}
        #close_button:hover {{
            background-color: #ff7b76;
        }}
        #close_button:pressed {{
            background-color: #bf4943;
        }}
        
        #minimize_button {{
            background-color: #ffbd2e;
            color: #654600;
        }}
        #minimize_button:hover {{
            background-color: #ffcc51;
        }}
        #minimize_button:pressed {{
            background-color: #bf8e23;
        }}
        
        #maximize_button {{
            background-color: #28c941;
            color: #0a4513;
        }}
        #maximize_button:hover {{
            background-color: #54d465;
        }}
        #maximize_button:pressed {{
            background-color: #1e9731;
        }}
        
        #search_frame {
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 0px;
        }
        #search_frame QLineEdit {
             background: transparent;
             border: none;
             padding: 6px 8px; /* Slightly more left padding */
        }
        #field_indicator, #dropdown_button {
            color: {TC["secondary_on_light"] if self.current_theme == 'light' else TC["secondary_on_dark"]};
            background: transparent;
            border: none;
            padding: 6px 4px;
            margin: 0px;
        }
        #field_indicator {
            margin-right: 0px;
            font-size: 12px;
        }
        #dropdown_button {
            margin-left: 0px;
            margin-right: 4px;
            font-size: 10px;
        }
        #dropdown_button:hover {
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
        }

        /* Mirror Panel specific styles */
        QWidget#MirrorPanel {{
            background-color: {CP["light_bg_secondary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            border-left: 1px solid {UA["border_medium"]};
        }}
        QWidget#MirrorPanelContent {{
            background-color: transparent; 
        }}
        QWidget#MirrorPanelContent QGroupBox {{
            background-color: {UA["content_bg"]}; /* Match main content bg */
            border: 1px solid {UA["border_light"]};
            border-radius: 6px;
            margin-top: 10px;
            padding: 8px;
            font-weight: 600; /* Semibold */
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
        }}
        QWidget#MirrorPanel QListWidget {{
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_tertiary"]};
            border: 1px solid {UA["border_light"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            min-height: 80px;
            border-radius: 4px;
            font-size: 13px;
        }}
        QWidget#MirrorPanel QListWidget::item {{
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            padding: 5px;
        }}
        QWidget#MirrorPanel QListWidget::item:selected {{
            background-color: {UA["selection_bg"]};
            color: {UA["selection_fg"]};
        }}

        QWidget#MirrorPanelContent QPushButton.primary {{ 
            background-color: {UA["button_primary_bg"]};
            color: {UA["button_primary_fg"]};
            border: none;
            font-weight: bold; 
        }}
        QWidget#MirrorPanelContent QPushButton.primary:hover {{
            background-color: {UA["button_primary_hover_bg"]};
        }}
        QWidget#MirrorPanel QLineEdit, QWidget#MirrorPanel QSpinBox {{
            padding: 7px;
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 13px;
        }}
        QWidget#MirrorPanel QCheckBox {{
            color: {TC["primary_on_light"] if self.current_theme == 'light' else TC["primary_on_dark"]};
            font-size: 13px;
            padding: 3px 0px;
        }}
        QWidget#MirrorPanel QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        QWidget#MirrorPanel QSplitter::handle {{
            background-color: {UA["border_light"]};
            height: 1px;
        }}
        QWidget#MirrorPanel QFrame[frameShape="4"] {{  /* HLine */
            background-color: {UA["border_light"]};
            max-height: 1px;
        }}
        
        /* QScrollBar styling within MirrorPanel - make them slimmer */
        QWidget#MirrorPanel QScrollBar:vertical {{
            width: 10px;
            border-radius: 5px;
        }}
        
        QWidget#MirrorPanel QScrollBar::handle:vertical {{
            min-height: 20px;
            border-radius: 5px;
        }}
                
        QWidget#MirrorPanel QScrollBar:horizontal {{
            height: 10px;
            border-radius: 5px;
        }}
        
        QWidget#MirrorPanel QScrollBar::handle:horizontal {{
            min-width: 20px;
            border-radius: 5px;
        }}
        """
        self.setStyleSheet(stylesheet)
    
    def on_search_changed(self):
        """Debounced search that triggers after user stops typing."""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms debounce

    def on_selection_changed(self):
        """Update the mirror panel when selection changes"""
        selected_rows = self.get_selected_actual_rows()
        if self.mirror_panel.isVisible() and selected_rows:
            self.mirror_panel.set_selected_rows(selected_rows)
            self.mirror_panel.update_selected_count()
    
    def setup_table_context_menu(self):
        """Set up context menu for the metadata table"""
        self.metadata_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.metadata_table.customContextMenuRequested.connect(self.show_table_context_menu)
    
    def show_table_context_menu(self, position):
        """Show context menu for the metadata table"""
        # Get the selected rows
        selected_rows = self.get_selected_actual_rows()
        if not selected_rows:
            return
            
        # Create menu
        menu = QMenu(self)
        
        # Get row and column under cursor
        item = self.metadata_table.itemAt(position)
        if not item:
            return
            
        row = item.row()
        col = item.column()
        
        # Options for filename column
        if col == 0:
            # Add rename action
            rename_action = QAction("Edit Filename", self)
            rename_action.triggered.connect(lambda: self.metadata_table.editItem(item))
            menu.addAction(rename_action)
            
            # Add batch rename action if multiple rows are selected
            if len(selected_rows) > 1:
                batch_rename_action = QAction("Batch Rename...", self)
                batch_rename_action.triggered.connect(lambda: self.show_batch_rename_dialog(selected_rows))
                menu.addAction(batch_rename_action)
            
            # Add revert action if there's just one selected row
            if len(selected_rows) == 1:
                # Get actual row in all_files
                actual_row = self.filtered_rows[row]
                file_path = self.all_files[actual_row][0]
                orig_filename = os.path.basename(file_path)
                current_filename = item.text()
                
                if current_filename != orig_filename:
                    revert_action = QAction("Revert Filename", self)
                    revert_action.triggered.connect(lambda: self.revert_filename(row))
                    menu.addAction(revert_action)
        
        # Options for other columns
        else:
            # Add edit action
            edit_action = QAction("Edit Cell", self)
            edit_action.triggered.connect(lambda: self.metadata_table.editItem(item))
            menu.addAction(edit_action)
            
            # Add copy action
            copy_action = QAction("Copy", self)
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(item.text()))
            menu.addAction(copy_action)
            
            # Add paste action
            if QApplication.clipboard().text():
                paste_action = QAction("Paste", self)
                paste_action.triggered.connect(lambda: self.paste_to_selected_cells(col))
                menu.addAction(paste_action)
        
        # Add separator before remove action if other actions are present
        if menu.actions():
            menu.addSeparator()
            
        # Add remove file(s) action
        remove_action = QAction(f"Remove Selected File{'s' if len(selected_rows) > 1 else ''}", self)
        if not selected_rows: # Should not happen if menu is shown for selected items
            remove_action.setEnabled(False)
        remove_action.triggered.connect(self.prompt_and_execute_remove_files)
        menu.addAction(remove_action)
        
        # Show the menu
        menu.exec(self.metadata_table.mapToGlobal(position))
    
    def prompt_and_execute_remove_files(self):
        """Prompt the user for confirmation and then execute file removal for selected files."""
        selected_actual_indices = self.get_selected_actual_rows()
        
        if not selected_actual_indices:
            QMessageBox.information(self, "No Selection", "No files selected to remove.")
            return

        num_selected = len(selected_actual_indices)
        file_s = "file" if num_selected == 1 else "files"
        
        reply = QMessageBox.question(
            self, 
            "Confirm Removal from List", 
            f"Are you sure you want to remove the selected {num_selected} {file_s} from the application list?\\n\\n" \
            f"This action will NOT delete the file(s) from your computer's disk, only from the list in this application.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            file_data_to_remove = []
            # Iterate over a copy of indices, as all_files might change if an error occurs mid-process (though unlikely with current setup)
            for index in sorted(selected_actual_indices, reverse=True): # Sort reverse to simplify removal from all_files if done by index
                if 0 <= index < len(self.all_files):
                    file_path, metadata = self.all_files[index]
                    file_data_to_remove.append((index, file_path, metadata))
            
            if not file_data_to_remove:
                self.status_label.setText("No valid files found for removal.")
                return

            # The FileRemoveCommand expects data sorted by original index if it were to reinsert at original_index for undo.
            # Since our current undo appends and re-sorts, the order fed to command init isn't super critical,
            # but good practice to pass it consistently.
            # We reversed for potential indexed removal, but for storing, original order is fine.
            file_data_to_remove.sort(key=lambda x: x[0]) # Sort by original index for consistency

            command = FileRemoveCommand(self, file_data_to_remove)
            if self.undo_redo_stack.push(command):
                # Status is updated by the command's execute method
                pass
            else:
                self.status_label.setText("File removal failed or was cancelled.")
            self.update_undo_redo_buttons()

    def show_batch_rename_dialog(self, selected_rows):
        """Show a dialog for batch renaming multiple files"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Batch Rename Files")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: rgba(245, 236, 220, 0.92);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Instructions
        instructions = QLabel(
            "Enter a pattern for renaming files. Use the following placeholders:\n"
            "- {original}: Original filename (without extension)\n"
            "- {num}: Sequential number\n"
            "- {show}, {scene}, {take}, etc.: Metadata fields\n\n"
            "Example: {show}_{scene}_{category}_{num}"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Pattern input
        pattern_layout = QHBoxLayout()
        pattern_label = QLabel("Pattern:")
        pattern_input = QLineEdit()
        pattern_input.setPlaceholderText("Enter rename pattern...")
        pattern_input.setText("{original}")
        
        pattern_layout.addWidget(pattern_label)
        pattern_layout.addWidget(pattern_input, 1)
        layout.addLayout(pattern_layout)
        
        # Start number input
        start_num_layout = QHBoxLayout()
        start_num_label = QLabel("Start Number:")
        start_num_input = QLineEdit()
        start_num_input.setText("1")
        start_num_input.setFixedWidth(80)
        
        # Padding input
        padding_label = QLabel("Padding:")
        padding_input = QLineEdit()
        padding_input.setText("2")
        padding_input.setFixedWidth(80)
        padding_input.setToolTip("Number of digits to pad with zeros (e.g. 2 = 01, 02, etc.)")
        
        start_num_layout.addWidget(start_num_label)
        start_num_layout.addWidget(start_num_input)
        start_num_layout.addWidget(padding_label)
        start_num_layout.addWidget(padding_input)
        start_num_layout.addStretch()
        layout.addLayout(start_num_layout)
        
        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        preview_list = QListWidget()
        preview_layout.addWidget(preview_list)
        
        layout.addWidget(preview_group)
        
        # Update preview function
        def update_preview():
            try:
                pattern = pattern_input.text()
                start_num = int(start_num_input.text())
                padding = int(padding_input.text())
                
                preview_list.clear()
                
                for i, idx in enumerate(selected_rows):
                    file_path, metadata = self.all_files[idx]
                    original = os.path.splitext(os.path.basename(file_path))[0]
                    extension = os.path.splitext(file_path)[1]
                    
                    # Prepare replacement dict
                    replacements = {
                        'original': original,
                        'num': str(start_num + i).zfill(padding)
                    }
                    
                    # Add metadata fields
                    for key, value in metadata.items():
                        if isinstance(value, str):
                            replacements[key.lower()] = value
                    
                    # Format the new filename
                    try:
                        new_name = pattern.format(**replacements) + extension
                        preview_list.addItem(f"{original}{extension} → {new_name}")
                    except KeyError as e:
                        preview_list.addItem(f"Error: {str(e)} not found in metadata")
                
            except ValueError:
                preview_list.clear()
                preview_list.addItem("Invalid number input")
        
        # Connect signals
        pattern_input.textChanged.connect(update_preview)
        start_num_input.textChanged.connect(update_preview)
        padding_input.textChanged.connect(update_preview)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        
        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(lambda: self.batch_rename_files(
            selected_rows, 
            pattern_input.text(), 
            int(start_num_input.text()), 
            int(padding_input.text()), 
            dialog
        ))
        rename_button.setProperty("class", "primary")
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(rename_button)
        
        layout.addLayout(button_layout)
        
        # Initial preview
        update_preview()
        
        # Show dialog
        dialog.exec()
    
    def batch_rename_files(self, selected_rows, pattern, start_num, padding, dialog):
        """Perform batch renaming of files"""
        # First check for file name collisions
        new_paths = []
        rename_commands = []
        
        # Set up progress dialog for checking
        progress = QProgressDialog("Checking filenames...", "Cancel", 0, len(selected_rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)  # Only show if operation takes longer than 500ms
        
        for i, idx in enumerate(selected_rows):
            if progress.wasCanceled():
                dialog.reject()
                return
                
            progress.setValue(i)
            QApplication.processEvents()
            
            file_path, metadata = self.all_files[idx]
            original = os.path.splitext(os.path.basename(file_path))[0]
            extension = os.path.splitext(file_path)[1]
            directory = os.path.dirname(file_path)
            
            # Prepare replacement dict
            replacements = {
                'original': original,
                'num': str(start_num + i).zfill(padding)
            }
            
            # Add metadata fields
            for key, value in metadata.items():
                if isinstance(value, str):
                    replacements[key.lower()] = value
            
            # Format the new filename
            try:
                new_name = pattern.format(**replacements) + extension
                new_path = os.path.join(directory, new_name)
                
                # Skip if the file is being renamed to itself
                if new_path == file_path:
                    continue
                    
                # Check for collisions
                if new_path in new_paths:
                    QMessageBox.warning(
                        self, 
                        "Naming Conflict", 
                        f"The pattern would result in duplicate filename: {new_name}\nBatch rename canceled."
                    )
                    dialog.reject()
                    return
                
                # Check if the file already exists on disk
                if os.path.exists(new_path) and new_path != file_path:
                    QMessageBox.warning(
                        self, 
                        "File Already Exists", 
                        f"Cannot rename to '{new_name}': A file with this name already exists in the directory."
                    )
                    dialog.reject()
                    return
                    
                new_paths.append(new_path)
                
                # Create rename command
                command = FileRenameCommand(self, idx, file_path, new_path)
                rename_commands.append(command)
                
            except KeyError as e:
                QMessageBox.warning(
                    self, 
                    "Pattern Error", 
                    f"Error in pattern: {str(e)} not found in metadata\nBatch rename canceled."
                )
                dialog.reject()
                return
        
        # Close the progress dialog
        progress.setValue(len(selected_rows))
        
        # If no files to rename, just return
        if not rename_commands:
            self.status_label.setText("No files need to be renamed")
            dialog.accept()
            return
        
        # Create a batch command for the entire rename operation
        batch_command = BatchCommand(f"Batch Rename {len(rename_commands)} Files", rename_commands)
        if self.undo_redo_stack.push(batch_command):
            self.status_label.setText(f"Successfully renamed {len(rename_commands)} files")
            # Update undo/redo button states
            self.update_undo_redo_buttons()
            dialog.accept()
        else:
            self.status_label.setText("Failed to rename files")
            dialog.reject()
    
    def revert_filename(self, row):
        """Revert the filename at the given row to its original value"""
        if row < 0 or row >= self.metadata_table.rowCount():
            return
            
        # Get actual row in all_files
        actual_row = self.filtered_rows[row]
        file_path, _ = self.all_files[actual_row]
        orig_filename = os.path.basename(file_path)
        
        # Update the table
        self.metadata_table.blockSignals(True)
        self.metadata_table.item(row, 0).setText(orig_filename)
        self.metadata_table.blockSignals(False)
    
    def paste_to_selected_cells(self, column):
        """Paste clipboard content to all selected cells in the given column"""
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text:
            return
            
        # Get all selected items in the specified column
        ranges = self.metadata_table.selectedRanges()
        for selection_range in ranges:
            for row in range(selection_range.topRow(), selection_range.bottomRow() + 1):
                item = self.metadata_table.item(row, column)
                if item:
                    item.setText(clipboard_text)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if os.path.isdir(file_path):
                self.load_files_from_folder(file_path)
                
    def browse_folder(self):
        """Browse for a folder and load WAV files."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.load_files_from_folder(folder_path)
    
    def load_files_from_folder(self, folder_path):
        """Load WAV files from a folder with progress tracking."""
        import glob
        
        # Find all WAV files in the folder and subfolders
        self.status_label.setText("Finding WAV files...")
        QApplication.processEvents()
        wav_files = glob.glob(os.path.join(folder_path, "**", "*.wav"), recursive=True)
        
        if not wav_files:
            QMessageBox.warning(self, "No WAV Files", f"No WAV files found in {folder_path}")
            return
        
        # Set up a progress dialog
        self.progress_dialog = QProgressDialog("Loading WAV files...", "Cancel", 0, len(wav_files), self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(500)  # Only show if operation takes longer than 500ms
        
        # Clear existing data first
        self.metadata_table.setRowCount(0)
        self.all_files = []
        
        # Create and start the worker thread
        self.file_load_worker = FileLoadWorker(wav_files)
        self.file_load_worker.progress.connect(self.update_load_progress)
        self.file_load_worker.finished.connect(self.on_files_loaded)
        self.progress_dialog.canceled.connect(self.cancel_file_loading)
        self.file_load_worker.start()
    
    def update_load_progress(self, current, total, filename):
        """Update the progress dialog"""
        if self.progress_dialog is None:
            return
        
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(f"Loading {current}/{total}: {filename}")
            QApplication.processEvents()
    
    def cancel_file_loading(self):
        """Cancel the file loading process"""
        if self.file_load_worker and self.file_load_worker.isRunning():
            self.file_load_worker.requestInterruption()
            self.file_load_worker.wait()
    
    def on_files_loaded(self, results):
        """Handle completed file loading"""
        self.all_files = results
        
        # Close the progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        # Check for files with errors
        files_with_errors = []
        for file_path, metadata in results:
            if metadata.get("Error"):
                files_with_errors.append((file_path, metadata.get("Error", "Unknown error")))
        
        # Update the UI
        self.update_table()
        
        # Show status message
        if files_with_errors:
            error_count = len(files_with_errors)
            total_count = len(results)
            self.status_label.setText(f"Loaded {total_count - error_count} of {total_count} WAV files ({error_count} with errors)")
            
            # Show a notification about errors
            if error_count <= 5:
                # If few errors, show details
                error_msg = "The following files had errors:\n"
                for file_path, error in files_with_errors:
                    error_msg += f"• {os.path.basename(file_path)}: {error}\n"
                QMessageBox.warning(self, "Loading Errors", error_msg)
            else:
                # If many errors, show summary
                QMessageBox.warning(
                    self, 
                    "Loading Errors", 
                    f"{error_count} of {total_count} files had errors during loading.\n"
                    "Files with errors will be shown in the table but may have incomplete metadata."
                )
        else:
            self.status_label.setText(f"Loaded {len(self.all_files)} WAV files")
    
    def update_table(self):
        """Update the table with current metadata (optimized)."""
        # Disconnect the signal temporarily to avoid triggering updates
        self.metadata_table.blockSignals(True)
        
        # Clear the table
        self.metadata_table.setRowCount(0)
        
        # Reset filtered rows
        self.filtered_rows = list(range(len(self.all_files)))
        
        # Apply current filter
        self.filter_table()
        
        # Reconnect the signal
        self.metadata_table.blockSignals(False)
    
    def filter_table(self):
        """Filter the table based on search term (optimized)."""
        search_term = self.search_input.text().lower()
        search_field = self.current_search_field
        
        # Disconnect signals temporarily and disable updates
        self.metadata_table.blockSignals(True)
        self.metadata_table.setUpdatesEnabled(False)
        
        # Clear the table
        self.metadata_table.setRowCount(0)
        
        # First pass: identify matching rows
        self.filtered_rows = []
        
        # Fast path for no filter
        if not search_term:
            self.filtered_rows = list(range(len(self.all_files)))
        else:
            # Use different search strategies based on the field
            if search_field == "All Fields":
                # Search in all fields including filename
                for i, (file_path, metadata) in enumerate(self.all_files):
                    filename = os.path.basename(file_path)
                    if (search_term in filename.lower() or 
                        any(search_term in str(value).lower() for value in metadata.values())):
                        self.filtered_rows.append(i)
            elif search_field == "Filename":
                # Search in filename only
                for i, (file_path, _) in enumerate(self.all_files):
                    filename = os.path.basename(file_path)
                    if search_term in filename.lower():
                        self.filtered_rows.append(i)
            else:
                # Search in the specified field
                for i, (_, metadata) in enumerate(self.all_files):
                    if search_term in str(metadata.get(search_field, "")).lower():
                        self.filtered_rows.append(i)
        
        # Second pass: batch populate table
        if self.filtered_rows:
            # Pre-allocate rows for better performance
            self.metadata_table.setRowCount(len(self.filtered_rows))
            
            # Create or update table items
            for table_row, file_idx in enumerate(self.filtered_rows):
                file_path, metadata = self.all_files[file_idx]
                filename = os.path.basename(file_path)
                
                # Column 0: Filename
                item = self.metadata_table.item(table_row, 0)
                if item:
                    item.setText(filename)
                else:
                    self.metadata_table.setItem(table_row, 0, QTableWidgetItem(filename))

                # Metadata columns
                metadata_keys = ["Show", "Scene", "Take", "Category", 
                                 "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]
                for col_offset, key in enumerate(metadata_keys):
                    col = col_offset + 1
                    value = metadata.get(key, "")
                    item = self.metadata_table.item(table_row, col)
                    if item:
                        item.setText(value)
                    else:
                        self.metadata_table.setItem(table_row, col, QTableWidgetItem(value))

                # Column 10: File Path
                item = self.metadata_table.item(table_row, 10)
                if item:
                    item.setText(file_path)
                else:
                    file_path_item = QTableWidgetItem(file_path)
                    file_path_item.setFlags(file_path_item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Make non-editable
                    self.metadata_table.setItem(table_row, 10, file_path_item)
        
        # Re-enable updates and signals
        self.metadata_table.setUpdatesEnabled(True)
        self.metadata_table.blockSignals(False)
        self.metadata_table.viewport().update() # Force repaint of the table viewport
        
        # Update status message
        if len(self.filtered_rows) == len(self.all_files):
            self.status_label.setText(f"Showing all {len(self.all_files)} files")
        else:
            self.status_label.setText(f"Showing {len(self.filtered_rows)} of {len(self.all_files)} files")
    
    def update_table_cell(self, file_index, field, value):
        """Update a specific cell in the table based on file index and field"""
        # Find the table row that corresponds to the file index
        for table_row, filtered_idx in enumerate(self.filtered_rows):
            if filtered_idx == file_index:
                # Determine the column based on the field
                metadata_keys = ["Show", "Scene", "Take", "Category", 
                             "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]
                
                if field in metadata_keys:
                    col = metadata_keys.index(field) + 1  # +1 to account for filename column
                    
                    # Update the cell
                    self.metadata_table.blockSignals(True)
                    self.metadata_table.item(table_row, col).setText(value)
                    self.metadata_table.blockSignals(False)
                break
    
    def update_filename_in_table(self, file_index, new_filename):
        """Update the filename and file path in the table"""
        file_path, _ = self.all_files[file_index]
        
        # Find the table row that corresponds to the file index
        for table_row, filtered_idx in enumerate(self.filtered_rows):
            if filtered_idx == file_index:
                # Update the filename (column 0)
                self.metadata_table.blockSignals(True)
                self.metadata_table.item(table_row, 0).setText(new_filename)
                
                # Update the file path (column 10)
                self.metadata_table.item(table_row, 10).setText(file_path)
                self.metadata_table.blockSignals(False)
                break
    
    def update_metadata(self, item):
        """Update metadata when a cell is edited."""
        row = item.row()
        col = item.column()
        
        # Get the index in self.all_files
        if 0 <= row < len(self.filtered_rows):
            # Get the actual index in all_files from the filtered rows list
            actual_row = self.filtered_rows[row]
            file_path, metadata = self.all_files[actual_row]
            
            # Get the new value from the table
            new_value = item.text()
            
            if col == 0:  # Filename column
                old_filename = os.path.basename(file_path)
                if new_value != old_filename:
                    self.rename_file(actual_row, new_value)
            elif 1 <= col <= 9:  # Metadata columns
                # Map column indices to metadata keys
                metadata_keys = ["Show", "Scene", "Take", "Category", 
                           "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]
            
                # Get the metadata key and old value
                key = metadata_keys[col - 1]  # -1 to account for filename column
                old_value = metadata.get(key, "")
                
                # Only update if the value has changed
                if new_value != old_value:
                    # Create and push the command to the stack
                    command = MetadataEditCommand(self, actual_row, key, old_value, new_value)
                    self.undo_redo_stack.push(command)
            
            # Mark that changes are pending
            self.changes_pending = True
            self.status_label.setText("Changes pending - press Save to apply")
    
    def rename_file(self, file_index, new_filename):
        """Rename the file at the given index with the new filename."""
        if file_index < 0 or file_index >= len(self.all_files):
            return False
            
        file_path, metadata = self.all_files[file_index]
        
        # Get directory and old filename
        directory = os.path.dirname(file_path)
        old_filename = os.path.basename(file_path)
        
        # Ensure the new filename has the same extension
        _, extension = os.path.splitext(old_filename)
        if not new_filename.endswith(extension):
            new_filename += extension
            
        # Create new file path
        new_file_path = os.path.join(directory, new_filename)
        
        # Don't do anything if the filename hasn't changed
        if new_file_path == file_path:
            return False
            
        # Check if the new file path already exists
        if os.path.exists(new_file_path) and new_file_path != file_path:
            QMessageBox.warning(
                self, 
                "File Already Exists", 
                f"Cannot rename to '{new_filename}': A file with this name already exists in the directory."
            )
            
            # Reset the table cell to the original filename
            for i, idx in enumerate(self.filtered_rows):
                if idx == file_index:
                    self.metadata_table.blockSignals(True)
                    self.metadata_table.item(i, 0).setText(old_filename)
                    self.metadata_table.blockSignals(False)
                    break
            return False
            
        # Create and push the rename command to the stack
        command = FileRenameCommand(self, file_index, file_path, new_file_path)
        if self.undo_redo_stack.push(command):
            self.status_label.setText(f"Renamed '{old_filename}' to '{new_filename}'")
            return True
        else:
            # Reset the table cell to the original filename if command failed
            for i, idx in enumerate(self.filtered_rows):
                if idx == file_index:
                    self.metadata_table.blockSignals(True)
                    self.metadata_table.item(i, 0).setText(old_filename)
                    self.metadata_table.blockSignals(False)
                    break
            return False
    
    def save_all_changes(self):
        # Get selected rows, if none are selected, show message
        selected_rows = self.get_selected_actual_rows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select the rows you want to save changes for.")
            return
            
        if not self.changes_pending:
            QMessageBox.information(self, "No Changes", "There are no pending changes to save.")
            return
        
        # Set up progress dialog
        progress = QProgressDialog("Saving changes...", "Cancel", 0, len(selected_rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)  # Only show if operation takes longer than 500ms
            
        success_count = 0
        error_count = 0
        
        # Process only selected rows
        for i, idx in enumerate(selected_rows):
            if progress.wasCanceled():
                break
                
            progress.setValue(i)
            progress.setLabelText(f"Saving {i+1}/{len(selected_rows)}: {os.path.basename(self.all_files[idx][0])}")
            QApplication.processEvents()
            
            file_path, metadata = self.all_files[idx]
            try:
                wav_metadata.write_wav_metadata(file_path, metadata)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"Error updating metadata for {file_path}: {e}")
        
        # Close progress dialog
        progress.setValue(len(selected_rows))
                
        # Update status
        if error_count == 0:
            self.status_label.setText(f"Successfully updated metadata for {success_count} files")
            QMessageBox.information(self, "Success", f"Successfully updated metadata for {success_count} files")
        else:
            self.status_label.setText(f"Updated {success_count} files with {error_count} errors")
            QMessageBox.warning(self, "Partial Success", 
                               f"Updated {success_count} files with {error_count} errors. Check console for details.")
            
        self.changes_pending = False
    
    def get_selected_actual_rows(self):
        """Get the actual indices in all_files for selected table rows"""
        selected_ranges = self.metadata_table.selectedRanges()
        if not selected_ranges:
            return []
            
        selected_table_rows = set()
        for selection_range in selected_ranges:
            for row in range(selection_range.topRow(), selection_range.bottomRow() + 1):
                selected_table_rows.add(row)
                
        # Map visible table rows to actual file indices
        selected_actual_rows = [self.filtered_rows[row] for row in selected_table_rows 
                               if row < len(self.filtered_rows)]
        
        return selected_actual_rows
    
    def show_extraction_dialog(self):
        """Show dialog to extract metadata from filenames"""
        if not self.all_files:
            QMessageBox.warning(self, "No Files Loaded", "Please load WAV files first.")
            return
            
        # Get selected rows, if none are selected, show message
        selected_rows = self.get_selected_actual_rows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", 
                                   "Please select the rows you want to extract metadata for.")
            return
        
        dialog = FilenameExtractorDialog(self)
        # Pre-configure with the pattern PR2_Allen_Sc5.14D_01
        dialog.preset_common_pattern()
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply extraction only to selected files
            count = self.apply_filename_extraction(
                dialog.separator, 
                dialog.mappings,
                selected_rows
            )
            self.status_label.setText(f"Extracted metadata from {count} filenames")
            # Mark changes as pending
            self.changes_pending = True
    
    def apply_filename_extraction(self, separator, mappings, selected_rows_indices=None):
        """Apply filename extraction to selected files based on dialog settings"""
        count = 0
        
        # If no rows specified, don't process any
        if selected_rows_indices is None or not selected_rows_indices:
            return 0
            
        # Disconnect signals temporarily
        self.metadata_table.blockSignals(True)
        
        # Set up batch processing with progress dialog
        progress = QProgressDialog("Extracting metadata...", "Cancel", 0, len(selected_rows_indices), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)  # Only show if operation takes longer than 500ms
            
        # First, collect the necessary data for all selected files into a temporary, stable list
        extraction_data = []
        for idx in selected_rows_indices:
            if idx >= len(self.all_files):
                continue
                
            file_path, metadata = self.all_files[idx]
            filename = os.path.basename(file_path)
            # Remove the extension
            filename = os.path.splitext(filename)[0]
            
            # Split the filename using the separator
            parts = filename.split(separator)
            
            # Check if we have enough parts
            max_pos = max(int(pos) for field, pos in mappings)
            if len(parts) < max_pos:
                print(f"  Not enough parts: have {len(parts)}, need {max_pos}")
                continue
                
            extraction_data.append((file_path, metadata, parts))
        
        # Now, iterate over the stable extraction_data list to perform the parsing and metadata updates
        for i, (file_path, metadata, parts) in enumerate(extraction_data):
            if progress.wasCanceled():
                break
                
            progress.setValue(i)
            progress.setLabelText(f"Processing {i+1}/{len(selected_rows_indices)}: {os.path.basename(file_path)}")
            QApplication.processEvents()
            
            # Extract metadata based on mappings
            updated = False
            for field, pos in mappings:
                try:
                    # Position is 1-based in UI, convert to 0-based for Python
                    idx_val = int(pos) - 1 # Renamed idx to idx_val to avoid conflict with loop variable
                    
                    if idx_val >= len(parts):
                        print(f"  Index {idx_val} out of range for parts {parts}")
                        continue
                        
                    value = parts[idx_val]
                    print(f"  Mapping {field} from part {idx_val+1}: '{value}'")
                    
                    if field == "Scene" and idx_val < len(parts):
                        # Extract scene information
                        scene_part = value
                        # If scene follows format like "Sc5.14D", extract just the "5.14D" part
                        if scene_part.lower().startswith("sc"):
                            scene_part = scene_part[2:]
                            print(f"  Extracted Scene: '{scene_part}' from '{value}'")
                        
                        # Extract letter suffix if present and add to Slate
                        letter_match = re.search(r'[A-Za-z]+$', scene_part)
                        if letter_match:
                            letter_suffix = letter_match.group(0)
                            print(f"  Extracted letter suffix '{letter_suffix}' from Scene '{scene_part}'")
                            # Set the Slate field, overwriting existing value if a new one is found
                            metadata["Slate"] = letter_suffix
                            print(f"  Set Slate to: '{metadata['Slate']}'")
                            
                            # Optionally, you could remove the letter from the scene value
                            # scene_part = re.sub(r'[A-Za-z]+$', '', scene_part)
                            
                        metadata[field] = scene_part
                        updated = True
                    
                    elif field == "Subcategory" and idx_val < len(parts):
                        # Try to extract episode number from the filename
                        
                        # First check the scene part for a period (like in "5.14D")
                        scene_val = metadata.get("Scene", "")
                        if "." in scene_val:
                            # Extract episode number (before the period)
                            match = re.match(r'(\d+)\.', scene_val)
                            if match:
                                episode = match.group(1)
                                print(f"  Extracted episode '{episode}' from Scene '{scene_val}'")
                                metadata[field] = episode
                                updated = True
                                continue
                        
                        # If that didn't work, just use the direct mapping
                        metadata[field] = value
                        print(f"  Set {field} to '{value}'")
                        updated = True
                    
                    else:
                        # For other fields, just map directly
                        metadata[field] = value
                        print(f"  Set {field} to '{value}'")
                        updated = True
                        
                except (ValueError, IndexError) as e:
                    print(f"  Error processing {field} at position {pos}: {e}")
            
            if updated:
                count += 1
                self.all_files[selected_rows_indices[i]] = (file_path, metadata) # Use original loop variable idx here
                print(f"  Updated metadata for {os.path.basename(file_path)}")
        
        # Ensure the progress dialog is closed/completed
        progress.setValue(len(selected_rows_indices))
                
        # After extraction complete, refresh the table
        self.update_table()
                
        return count

    def create_folder_icon(self):
        """Create a folder download icon from SVG"""
        # SVG icon for folder download
        svg_content = """
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M3 4C3 2.89543 3.89543 2 5 2H9L11 4H19C20.1046 4 21 4.89543 21 6V20C21 21.1046 20.1046 22 19 22H5C3.89543 22 3 21.1046 3 20V4Z" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M12 16L16 12M12 16L8 12M12 16V8" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """
        
        # Create a QPixmap with transparent background
        icon_size = 24
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the pixmap
        painter = QPainter(pixmap)
        
        # Load the SVG content
        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding='utf-8'))
        
        # Render the SVG onto the pixmap
        svg_renderer.render(painter)
        
        # Finish painting
        painter.end()
        
        return QIcon(pixmap)
    
    def toggle_mirror_panel(self):
        """Toggle the visibility of the mirror panel"""
        # Get current visibility state
        is_visible = self.mirror_panel.isVisible()
        
        # Get selected rows if any
        selected_rows = self.get_selected_actual_rows()
        if selected_rows:
            # Update the selected rows in the mirror panel
            self.mirror_panel.set_selected_rows(selected_rows)
        self.mirror_panel.update_selected_count()
        
        # Toggle the panel visibility
        if not is_visible:
            # Show panel
            self.mirror_panel.setVisible(True)
            self.main_splitter.setSizes([self.width() - 400, 400])
        else:
            # Hide panel
            self.main_splitter.setSizes([self.width(), 0])
            self.mirror_panel.setVisible(False)
            
    def toggle_dark_mode(self):
        """Toggle between light and dark themes"""
        if self.current_theme == 'light':
            self.current_theme = 'dark'
            self.dark_mode_button.setToolTip("Switch to Light Mode")
            self.dark_mode_button.setText("🌞") # Sun icon for switching to light mode
        else:
            self.current_theme = 'light'
            self.dark_mode_button.setToolTip("Switch to Dark Mode")
            self.dark_mode_button.setText("🌙") # Moon icon for switching to dark mode
        
        # Apply the new theme
        self.apply_stylesheet()
        
        # Update icons with the new theme colors
        if hasattr(self, 'undo_button'):
            self.undo_button.setIcon(self.create_undo_icon())
        if hasattr(self, 'redo_button'):
            self.redo_button.setIcon(self.create_redo_icon())
    
    # Property for animation (keeping for future use)
    def get_panel_position(self):
        return self.main_splitter.sizes()[1] if len(self.main_splitter.sizes()) > 1 else 0
        
    def set_panel_position(self, value):
        # This method will be called by the animation
        pass
        
    panel_position = pyqtProperty(int, get_panel_position, set_panel_position)

    def mirror_files_qcode_take_review(self, selected_rows, dest_dir, day_number, overwrite):
        """Stub method for mirroring files for QCode Take Review."""
        print(f"STUB: mirror_files_qcode_take_review called with dest_dir={dest_dir}, day_number={day_number}, overwrite={overwrite}, {len(selected_rows)} files selected.")
        # TODO: Implement actual QCode Take Review mirroring logic
        pass

    def mirror_files(self, selected_rows, destination_dir, organization, overwrite):
        """Stub method for general file mirroring."""
        print(f"STUB: mirror_files called with destination_dir={destination_dir}, organization={organization}, overwrite={overwrite}, {len(selected_rows)} files selected.")
        # TODO: Implement actual file mirroring logic
        pass

    def set_search_field(self, field):
        """Set the current search field and update the filter"""
        self.current_search_field = field
        self.filter_table()
    
    def show_field_menu(self):
        """Show a menu to select which field to search in"""
        menu = QMenu(self)
        for field in ["All Fields", "Filename", "Scene", "Take", "Description", "Notes"]:
            action = QAction(field, self)
            action.triggered.connect(lambda checked, f=field: self.set_search_field(f))
            if field == self.current_search_field:
                action.setCheckable(True)
                action.setChecked(True)
            menu.addAction(action)
            
        # Position the menu below the button
        pos = self.search_field_button.mapToGlobal(self.search_field_button.rect().bottomLeft())
        menu.popup(pos)

    def create_sidebar_icon(self):
        """Create a custom sidebar toggle icon from SVG"""
        # SVG icon for sidebar toggle
        svg_content = """
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="4" y="4" width="16" height="16" rx="3" stroke="black" stroke-width="2"/>
          <rect x="14" y="6" width="4" height="12" rx="1" fill="black"/>
          <line x1="7" y1="8" x2="12" y2="8" stroke="black" stroke-width="2" stroke-linecap="round"/>
          <line x1="7" y1="12" x2="12" y2="12" stroke="black" stroke-width="2" stroke-linecap="round"/>
          <line x1="7" y1="16" x2="12" y2="16" stroke="black" stroke-width="2" stroke-linecap="round"/>
        </svg>
        """
        
        # Create a QPixmap with transparent background
        icon_size = 32  # Increased from 24 to 32
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the pixmap
        painter = QPainter(pixmap)
        
        # Load the SVG content
        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding='utf-8'))
        
        # Render the SVG onto the pixmap
        svg_renderer.render(painter)
        
        # Finish painting
        painter.end()
        
        return QIcon(pixmap)

    def toggleMaximized(self):
        """Toggle between maximized and normal window state"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event):
        """Handle mouse press events for window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if the click is in the top 40 pixels (title bar area)
            if event.position().y() <= 40:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                self._is_dragging = True
                return
        
        # Let normal event processing continue
        self._is_dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for window dragging"""
        if hasattr(self, '_drag_pos') and self._is_dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events for window dragging"""
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def create_integrated_title_bar(self, main_layout):
        """Create an integrated title bar with all controls"""
        # Create title bar container
        title_bar = QWidget()
        title_bar.setObjectName("title_bar") 
        title_bar.setFixedHeight(48)  # Increased height to avoid button cutoff
        
        # The title bar styling is now moved to the stylesheet in apply_stylesheet()
        # This allows it to properly update when theme changes
        
        # Use horizontal layout for title bar with proper vertical alignment
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 4, 10, 4)  # Reduced vertical padding
        title_layout.setSpacing(8)  # Slightly reduced spacing
        title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Window control buttons in macOS style (left side)
        close_button = QPushButton("")
        close_button.setObjectName("close_button")
        close_button.setToolTip("Close")
        close_button.setFixedSize(12, 12)
        close_button.clicked.connect(self.close)
        
        minimize_button = QPushButton("")
        minimize_button.setObjectName("minimize_button")
        minimize_button.setToolTip("Minimize")
        minimize_button.setFixedSize(12, 12)
        minimize_button.clicked.connect(self.showMinimized)
        
        self.maximize_button = QPushButton("")
        self.maximize_button.setObjectName("maximize_button")
        self.maximize_button.setToolTip("Maximize")
        self.maximize_button.setFixedSize(12, 12)
        self.maximize_button.clicked.connect(self.toggleMaximized)
        
        # Window control buttons use styling from main stylesheet
        
        # Add buttons to layout in macOS order (close, minimize, maximize)
        title_layout.addWidget(close_button)
        title_layout.addSpacing(4)
        title_layout.addWidget(minimize_button)
        title_layout.addSpacing(4)
        title_layout.addWidget(self.maximize_button)
        title_layout.addSpacing(10)
        
        # App title
        app_title = QLabel("Audio Metadata Editor")
        app_title.setObjectName("app_title")
        title_layout.addWidget(app_title)
        
        # Add a small separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        separator1.setObjectName("title_separator")
        # Separator styling is handled in the main stylesheet
        title_layout.addWidget(separator1)
        
        # Integrated search widget with dropdown
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)
        
        # Integrated search field with dropdown
        search_frame = QFrame()
        search_frame.setObjectName("search_frame")
        # Search frame styling is handled in the main stylesheet
        
        search_frame_layout = QHBoxLayout(search_frame)
        search_frame_layout.setContentsMargins(8, 0, 5, 0)  # Increased left padding
        search_frame_layout.setSpacing(2)  # Added spacing between elements
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(200)  # Increased width
        self.search_input.setObjectName("search_input")
        # Search input styling is handled in the main stylesheet
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.filter_table)
        
        # Search input first
        search_frame_layout.addWidget(self.search_input)
        
        # Field indicator and dropdown button (inside the same frame)
        field_indicator = QLabel("All")
        field_indicator.setObjectName("field_indicator")
        field_indicator.setFixedWidth(30)  # Set fixed width for consistency
        # Field indicator styling is handled in the main stylesheet
        
        dropdown_button = QPushButton("▾")
        dropdown_button.setObjectName("dropdown_button")
        dropdown_button.setFixedWidth(20)  # Reduced width to fit better
        # Dropdown button styling is handled in the main stylesheet
        dropdown_button.clicked.connect(self.show_field_menu)
        
        # Add field indicator and dropdown to search frame
        search_frame_layout.addWidget(field_indicator)
        search_frame_layout.addWidget(dropdown_button)
        
        search_layout.addWidget(search_frame)
        
        # Store references for updating
        self.field_indicator = field_indicator
        self.search_field_button = dropdown_button
        self.current_search_field = "All Fields"
        
        # Add margin before and after search container
        title_layout.addSpacing(10)  # Add spacing before search
        title_layout.addWidget(search_container)
        title_layout.addSpacing(10)  # Add spacing after search
        
        # Add a flex spacer to push the rest to the right
        title_layout.addStretch(1)
        
        # Action buttons
        
        # Create a container for the action buttons to keep them aligned
        action_container = QWidget()
        action_container.setObjectName("action_container")
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(5, 0, 5, 0)
        action_layout.setSpacing(8)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        
        # Browse button
        self.browse_button = QPushButton()
        self.browse_button.setObjectName("browse_button")
        self.browse_button.setIcon(self.create_folder_icon())
        self.browse_button.setToolTip("Browse for audio files (Ctrl+O)")
        self.browse_button.setFixedSize(32, 32)
        self.browse_button.clicked.connect(self.browse_folder)
        action_layout.addWidget(self.browse_button)

        # Extract metadata button
        extract_metadata_button = QPushButton("Extract")
        extract_metadata_button.setObjectName("extract_button")
        extract_metadata_button.setProperty("class", "secondary")
        extract_metadata_button.setToolTip("Extract metadata from filenames")
        extract_metadata_button.setFixedWidth(70)
        extract_metadata_button.setFixedHeight(32)
        extract_metadata_button.clicked.connect(self.show_extraction_dialog)
        action_layout.addWidget(extract_metadata_button)

        # Save all changes button
        save_all_button = AnimatedPrimaryButton("Embed") # Use themed primary button
        save_all_button.setFixedWidth(70)
        save_all_button.setFixedHeight(32)
        save_all_button.setToolTip("Save all pending changes (Ctrl+S)")
        save_all_button.clicked.connect(self.save_all_changes)
        action_layout.addWidget(save_all_button)
        
        # Add the action container to the title layout
        title_layout.addWidget(action_container)
        title_layout.addSpacing(15) # Add spacing between button groups
        
        # Undo/Redo buttons container
        undo_redo_container = QWidget()
        undo_redo_container.setObjectName("undo_redo_container")
        undo_redo_layout = QHBoxLayout(undo_redo_container)
        undo_redo_layout.setContentsMargins(5, 0, 5, 0)
        undo_redo_layout.setSpacing(6)
        undo_redo_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Undo button
        self.undo_button = QPushButton()
        self.undo_button.setObjectName("undo_button")
        self.undo_button.setIcon(self.create_undo_icon())
        self.undo_button.setToolTip("Undo (Ctrl+Z)")
        self.undo_button.setFixedSize(32, 32)
        self.undo_button.clicked.connect(self.undo_last_change)
        self.undo_button.setEnabled(False)  # Initially disabled until changes are made
        undo_redo_layout.addWidget(self.undo_button)
        
        # Redo button
        self.redo_button = QPushButton()
        self.redo_button.setObjectName("redo_button")
        self.redo_button.setIcon(self.create_redo_icon())
        self.redo_button.setToolTip("Redo (Ctrl+Y)")
        self.redo_button.setFixedSize(32, 32)
        self.redo_button.clicked.connect(self.redo_last_change)
        self.redo_button.setEnabled(False)  # Initially disabled until an undo is performed
        undo_redo_layout.addWidget(self.redo_button)
        
        title_layout.addWidget(undo_redo_container)
        title_layout.addSpacing(12)
        
        # Theme/View buttons container
        view_container = QWidget()
        view_container.setObjectName("view_container")
        view_layout = QHBoxLayout(view_container)
        view_layout.setContentsMargins(5, 0, 5, 0)
        view_layout.setSpacing(8)
        view_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Dark mode toggle button
        self.dark_mode_button = QPushButton("🌙")  # Moon icon for dark mode
        self.dark_mode_button.setObjectName("dark_mode_button")
        self.dark_mode_button.setToolTip("Switch to Dark Mode")
        self.dark_mode_button.setFixedSize(32, 32)
        self.dark_mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dark_mode_button.clicked.connect(self.toggle_dark_mode)
        view_layout.addWidget(self.dark_mode_button)
        
        # Mirror panel toggle button (moved to be last)
        toggle_mirror_panel_button = QPushButton()
        toggle_mirror_panel_button.setObjectName("mirror_panel_button")
        toggle_mirror_panel_button.setIcon(self.create_sidebar_icon())
        toggle_mirror_panel_button.setToolTip("Toggle mirror panel (Ctrl+M)")
        toggle_mirror_panel_button.setFixedSize(32, 32)
        toggle_mirror_panel_button.clicked.connect(self.toggle_mirror_panel)
        view_layout.addWidget(toggle_mirror_panel_button)
        
        title_layout.addWidget(view_container)
        title_layout.addSpacing(5)  # Add spacing at the end
        
        # Add the title bar to the main layout
        main_layout.addWidget(title_bar)
    
    def set_selected_rows(self, selected_rows):
        """Set the selected rows from parent"""
        self.selected_rows = selected_rows
        self.update_selected_count()
        
    def update_selected_count(self):
        """Update the text showing how many files are selected"""
        count = len(self.selected_rows) if self.selected_rows else 0
        if count == 0:
            self.file_count_label.setText("No files selected. Select files in the main panel.")
            self.file_count_label.setStyleSheet("color: #FF3B30; font-weight: bold; font-style: italic;")
        else:
            self.file_count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
            self.file_count_label.setStyleSheet("color: #007AFF; font-weight: bold;")
            
    def get_selected_rows_from_parent(self):
        """Get currently selected rows from parent, updating our cached selection"""
        if hasattr(self.parent, 'get_selected_actual_rows') and hasattr(self.parent, 'all_files'):
            if not self.parent.all_files:
                QMessageBox.warning(self, "No Files Loaded", 
                                  "Please load WAV files using the Browse button before mirroring.")
                return []
                
            selected_rows = self.parent.get_selected_actual_rows()
            if selected_rows:
                # Update our cached selection
                self.selected_rows = selected_rows
                self.update_selected_count()
            return selected_rows if selected_rows else self.selected_rows
        return self.selected_rows
    
    def close_panel(self):
        """Close the panel using the parent's toggle method"""
        if hasattr(self.parent, 'toggle_mirror_panel'):
            self.parent.toggle_mirror_panel()
    
    def browse_destination(self):
        """Browse for destination directory"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder_path:
            self.dest_input.setText(folder_path)
            self.destination_dir = folder_path
    
    def mirror_for_qcode(self):
        """Mirror files in QCODE Take Review format"""
        # Check if files are selected
        selected_rows = []
        if hasattr(self.parent, 'get_selected_actual_rows'):
            selected_rows = self.parent.get_selected_actual_rows()
            
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select files in the main panel to mirror.")
            return
            
        dest_dir = self.dest_input.text()
        if not dest_dir:
            QMessageBox.warning(self, "No Destination", "Please select a destination folder.")
            return
            
        day_number = self.day_spinner.value()
        overwrite = self.overwrite_checkbox.isChecked()
        
        # Call the parent's mirror method if it exists
        if hasattr(self.parent, 'mirror_files_qcode_take_review'):
            self.parent.mirror_files_qcode_take_review(selected_rows, dest_dir, day_number, overwrite)
        else:
            QMessageBox.information(self, "Not Implemented", "QCODE mirroring is not yet implemented.")
    
    def mirror_with_custom_org(self):
        """Mirror files with custom organization"""
        # Check if files are selected
        selected_rows = self.get_selected_rows_from_parent()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select files in the main panel to mirror.")
            return
            
        dest_dir = self.dest_input.text()
        if not dest_dir:
            QMessageBox.warning(self, "No Destination", "Please select a destination folder.")
            return
            
        # Gather the selected fields in order
        organization = []
        for i in range(self.selected_list.count()):
            organization.append(self.selected_list.item(i).text())
            
        if not organization:
            QMessageBox.warning(self, "No Organization", "Please select at least one field for folder organization.")
            return
            
        overwrite = self.overwrite_checkbox.isChecked()
        
        # Call the parent's mirror method
        self.parent.mirror_files(selected_rows, dest_dir, organization, overwrite)
    
    def add_fields(self):
        """Add selected fields from available to selected"""
        # Disconnect the preview update temporarily to avoid multiple updates
        self.selected_list.blockSignals(True)
        
        for item in self.available_list.selectedItems():
            # Create a new item to add to selected list
            new_item = QListWidgetItem(item.text())
            self.selected_list.addItem(new_item)
            
            # Remove from available list
            self.available_list.takeItem(self.available_list.row(item))
        
        # Reconnect signals and update preview
        self.selected_list.blockSignals(False)
        self.update_preview()
    
    def remove_fields(self):
        """Remove selected fields from selected to available"""
        # Disconnect the preview update temporarily
        self.selected_list.blockSignals(True)
        
        for item in self.selected_list.selectedItems():
            # Create a new item to add back to available list
            new_item = QListWidgetItem(item.text())
            self.available_list.addItem(new_item)
            
            # Remove from selected list
            self.selected_list.takeItem(self.selected_list.row(item))
        
        # Reconnect signals and update preview
        self.selected_list.blockSignals(False)
        self.update_preview()
    
    def move_field_up(self):
        """Move selected field up in the list"""
        current_row = self.selected_list.currentRow()
        if current_row > 0:
            # Disconnect the preview update temporarily
            self.selected_list.blockSignals(True)
            
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row - 1, current_item)
            self.selected_list.setCurrentRow(current_row - 1)
            
            # Reconnect signals and update preview
            self.selected_list.blockSignals(False)
            self.update_preview()
    
    def move_field_down(self):
        """Move selected field down in the list"""
        current_row = self.selected_list.currentRow()
        if current_row < self.selected_list.count() - 1:
            # Disconnect the preview update temporarily
            self.selected_list.blockSignals(True)
            
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row + 1, current_item)
            self.selected_list.setCurrentRow(current_row + 1)
            
            # Reconnect signals and update preview
            self.selected_list.blockSignals(False)
            self.update_preview()
    
    def update_preview(self):
        """Update the preview of folder structure"""
        if self.selected_list.count() == 0:
            self.example_text.setText("Select fields to see example folder structure")
            return
            
        # Build example structure
        structure = "destination/"
        for i in range(self.selected_list.count()):
            field = self.selected_list.item(i).text()
            structure += f"<{field}>/"
            
        # Add example values for clearer visualization
        example = structure.replace("<Show>", "<Show: PR2>")
        example = example.replace("<Scene>", "<Scene: 2.14B>")
        example = example.replace("<Take>", "<Take: 03>")
        example = example.replace("<Category>", "<Category: Andre>")
        example = example.replace("<Subcategory>", "<Subcategory: 2>")
        example = example.replace("<Slate>", "<Slate: D>")
        
        self.example_text.setText(example)
    
    def fade_in_widget(self, widget, duration=300):
        """Fade in animation for widgets in the panel"""
        if not self.parent.animations_enabled:
            widget.show()
            return
            
        widget.setAutoFillBackground(True)
        
        # Setup palette for transparency animation
        p = widget.palette()
        p.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
        widget.setPalette(p)
        
        # Create opacity effect
        widget.setStyleSheet("background-color: transparent;")
        
        # Show widget first
        widget.show()
        
        # Create animation
        geo = widget.geometry()
        start_rect = QRect(geo.x() + 20, geo.y(), geo.width(), geo.height())
        end_rect = geo
        
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(duration)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        
        # Restore widget styling after animation
        def restore_style():
            widget.setStyleSheet("")
            
        anim.finished.connect(restore_style)
        
    def update_scene_column(self, index):
        """Update the scene column selection"""
        if hasattr(self, 'csv_headers') and 0 <= index < len(self.csv_headers):
            self.scene_column = self.csv_headers[index]
            self.update_entry_match_display()
    
    def update_take_column(self, index):
        """Update the take column selection"""
        if hasattr(self, 'csv_headers') and 0 <= index < len(self.csv_headers):
            self.take_column = self.csv_headers[index]
            self.update_entry_match_display()

    def undo_last_change(self):
        """Undo the last change made to the metadata"""
        if self.undo_redo_stack.can_undo():
            command = self.undo_redo_stack.command_to_undo()
            self.undo_redo_stack.undo()
            self.update_undo_redo_buttons()
            self.status_label.setText(f"Undo: {command.description}")
        else:
            QMessageBox.information(self, "No Changes", "No changes to undo.")
    
    def redo_last_change(self):
        """Redo the last undone change"""
        if self.undo_redo_stack.can_redo():
            command = self.undo_redo_stack.command_to_redo()
            self.undo_redo_stack.redo()
            self.update_undo_redo_buttons()
            self.status_label.setText(f"Redo: {command.description}")
        else:
            QMessageBox.information(self, "No Changes", "No changes to redo.")
            
    def update_undo_redo_buttons(self):
        """Update the enabled state of undo/redo buttons"""
        if hasattr(self, 'undo_button'):
            self.undo_button.setEnabled(self.undo_redo_stack.can_undo())
        if hasattr(self, 'redo_button'):
            self.redo_button.setEnabled(self.undo_redo_stack.can_redo())

    def create_undo_icon(self):
        """Create a modern undo icon using SVG"""
        # SVG for undo icon - curved arrow pointing left
        svg_content = """
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 9L4 12M4 12L7 15M4 12H16C18.2091 12 20 13.7909 20 16V16" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """
        
        # Current theme will determine the icon color
        stroke_color = "#333333" if self.current_theme == 'light' else "#FFFFFF"
        svg_content = svg_content.replace("currentColor", stroke_color)
        
        # Create a QPixmap with transparent background
        icon_size = 24
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the pixmap
        painter = QPainter(pixmap)
        
        # Load the SVG content
        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding='utf-8'))
        
        # Render the SVG onto the pixmap
        svg_renderer.render(painter)
        
        # Finish painting
        painter.end()
        
        return QIcon(pixmap)
    
    def create_redo_icon(self):
        """Create a modern redo icon using SVG"""
        # SVG for redo icon - curved arrow pointing right
        svg_content = """
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M17 9L20 12M20 12L17 15M20 12H8C5.79086 12 4 13.7909 4 16V16" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """
        
        # Current theme will determine the icon color
        stroke_color = "#333333" if self.current_theme == 'light' else "#FFFFFF"
        svg_content = svg_content.replace("currentColor", stroke_color)
        
        # Create a QPixmap with transparent background
        icon_size = 24
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the pixmap
        painter = QPainter(pixmap)
        
        # Load the SVG content
        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding='utf-8'))
        
        # Render the SVG onto the pixmap
        svg_renderer.render(painter)
        
        # Finish painting
        painter.end()
        
        return QIcon(pixmap)

class MirrorPanel(QWidget):
    """Panel for mirroring files to another location with organization options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("MirrorPanel")
        
        # Initialize variables
        self.selected_rows = []
        self.destination_dir = ""
        
        # Setup UI - minimal implementation
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title with close button
        title_layout = QHBoxLayout()
        panel_title = QLabel("Mirror Files")
        panel_title.setStyleSheet("font-weight: bold; font-size: 16px;")
        title_layout.addWidget(panel_title)
        title_layout.addStretch()
        
        close_button = QPushButton("×")
        close_button.setFixedSize(24, 24)
        close_button.setStyleSheet("font-weight: bold; font-size: 16px;")
        close_button.clicked.connect(self.close_panel)
        title_layout.addWidget(close_button)
        layout.addLayout(title_layout)
        
        # Selected files count
        self.file_count_label = QLabel("No files selected")
        layout.addWidget(self.file_count_label)
        
        # Destination folder section
        dest_group = QGroupBox("Destination Folder")
        dest_form_layout = QVBoxLayout(dest_group)
        
        # Destination input
        dest_input_layout = QHBoxLayout()
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Select destination folder...")
        self.dest_input.setReadOnly(True)
        dest_input_layout.addWidget(self.dest_input)
        
        dest_button = QPushButton("Browse...")
        dest_button.setMaximumWidth(100)
        dest_button.clicked.connect(self.browse_destination)
        dest_input_layout.addWidget(dest_button)
        
        dest_form_layout.addLayout(dest_input_layout)
        layout.addWidget(dest_group)
        
        # Day number input for QCODE
        day_group = QGroupBox("QCODE Options")
        day_layout = QHBoxLayout(day_group)
        
        day_label = QLabel("Day Number:")
        day_layout.addWidget(day_label)
        
        self.day_spinner = QSpinBox()
        self.day_spinner.setMinimum(1)
        self.day_spinner.setMaximum(99)
        self.day_spinner.setValue(1)
        day_layout.addWidget(self.day_spinner)
        day_layout.addStretch()
        
        layout.addWidget(day_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        options_layout.addWidget(self.overwrite_checkbox)
        
        layout.addWidget(options_group)
        
        # Custom folder organization section
        custom_org_group = QGroupBox("Custom Folder Organization")
        custom_org_layout = QVBoxLayout(custom_org_group)
        
        # Explanation
        explanation = QLabel("Select metadata fields to create folder structure:")
        explanation.setWordWrap(True)
        custom_org_layout.addWidget(explanation)
        
        # Lists and buttons
        lists_layout = QHBoxLayout()
        
        # Available fields
        available_container = QWidget()
        available_layout = QVBoxLayout(available_container)
        available_layout.setContentsMargins(0, 0, 0, 0)
        
        available_label = QLabel("Available Fields:")
        available_layout.addWidget(available_label)
        
        self.available_list = QListWidget()
        available_layout.addWidget(self.available_list)
        
        # Add default available fields
        for field in ["Show", "Scene", "Take", "Category", "Subcategory", "Slate"]:
            self.available_list.addItem(field)
            
        self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        
        lists_layout.addWidget(available_container)
        
        # Add/Remove buttons
        buttons_container = QWidget()
        buttons_layout_fields = QVBoxLayout(buttons_container)
        buttons_layout_fields.setContentsMargins(8, 0, 8, 0)
        buttons_layout_fields.addStretch()
        
        add_button = QPushButton("→")
        add_button.setFixedWidth(40)
        add_button.clicked.connect(lambda: self.handle_add_fields())
        buttons_layout_fields.addWidget(add_button)
        
        remove_button = QPushButton("←")
        remove_button.setFixedWidth(40)
        remove_button.clicked.connect(lambda: self.handle_remove_fields())
        buttons_layout_fields.addWidget(remove_button)
        
        buttons_layout_fields.addStretch()
        
        lists_layout.addWidget(buttons_container)
        
        # Selected fields
        selected_container = QWidget()
        selected_layout = QVBoxLayout(selected_container)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        
        selected_label = QLabel("Selected Fields:")
        selected_layout.addWidget(selected_label)
        
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        selected_layout.addWidget(self.selected_list)
        
        # Up/down buttons
        updown_layout = QHBoxLayout()
        
        up_button = QPushButton("↑")
        up_button.setFixedWidth(40)
        up_button.clicked.connect(lambda: self.handle_move_field_up())
        updown_layout.addWidget(up_button)
        
        down_button = QPushButton("↓")
        down_button.setFixedWidth(40)
        down_button.clicked.connect(lambda: self.handle_move_field_down())
        updown_layout.addWidget(down_button)
        
        selected_layout.addLayout(updown_layout)
        
        lists_layout.addWidget(selected_container)
        
        custom_org_layout.addLayout(lists_layout)
        
        # Preview
        preview_group = QGroupBox("Example Structure:")
        preview_layout = QVBoxLayout(preview_group)
        
        self.example_text = QLabel("Select fields to see example folder structure")
        self.example_text.setWordWrap(True)
        self.example_text.setStyleSheet("font-family: Menlo, Monaco, 'SF Mono', 'Courier New'; background-color: white; padding: 5px; border: 1px solid #ccc;")
        preview_layout.addWidget(self.example_text)
        
        custom_org_layout.addWidget(preview_group)
        
        # Mirror button
        mirror_custom_button = QPushButton("Mirror Files with Custom Organization")
        mirror_custom_button.clicked.connect(lambda: QMessageBox.information(self, "Not Implemented", "Custom folder organization is not yet implemented."))
        custom_org_layout.addWidget(mirror_custom_button)
        
        layout.addWidget(custom_org_group)
        
        # Mirror buttons for QCODE
        qcode_buttons_layout = QVBoxLayout()
        
        mirror_qcode_button = QPushButton("Mirror for QCODE Take Review")
        # Temporarily commenting out until we can properly implement the mirror_for_qcode method
        # mirror_qcode_button.clicked.connect(self.mirror_for_qcode)
        mirror_qcode_button.clicked.connect(lambda: QMessageBox.information(self, "Not Implemented", "QCODE mirroring is not yet implemented."))
        qcode_buttons_layout.addWidget(mirror_qcode_button)
        
        layout.addLayout(qcode_buttons_layout)
        
        # Add stretch to push everything to the top
        layout.addStretch()
    
    def close_panel(self):
        """Close the panel"""
        if hasattr(self.parent, 'toggle_mirror_panel'):
            self.parent.toggle_mirror_panel()
    
    def set_selected_rows(self, selected_rows):
        """Set the selected rows"""
        self.selected_rows = selected_rows
        self.update_selected_count()
    
    def update_selected_count(self):
        """Update the file count label"""
        count = len(self.selected_rows) if self.selected_rows else 0
        self.file_count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
        
    def browse_destination(self):
        """Browse for destination directory"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder_path:
            self.dest_input.setText(folder_path)
            self.destination_dir = folder_path

    def handle_add_fields(self):
        """Add selected fields from available to selected"""
        for item in self.available_list.selectedItems():
            # Create a new item to add to selected list
            new_item = QListWidgetItem(item.text())
            self.selected_list.addItem(new_item)
            
            # Remove from available list
            self.available_list.takeItem(self.available_list.row(item))
        self.update_folder_preview()
    
    def handle_remove_fields(self):
        """Remove selected fields from selected to available"""
        for item in self.selected_list.selectedItems():
            # Create a new item to add back to available list
            new_item = QListWidgetItem(item.text())
            self.available_list.addItem(new_item)
            
            # Remove from selected list
            self.selected_list.takeItem(self.selected_list.row(item))
        self.update_folder_preview()
    
    def handle_move_field_up(self):
        """Move selected field up in the list"""
        current_row = self.selected_list.currentRow()
        if current_row > 0:
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row - 1, current_item)
            self.selected_list.setCurrentRow(current_row - 1)
            self.update_folder_preview()
    
    def handle_move_field_down(self):
        """Move selected field down in the list"""
        current_row = self.selected_list.currentRow()
        if current_row < self.selected_list.count() - 1:
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row + 1, current_item)
            self.selected_list.setCurrentRow(current_row + 1)
            self.update_folder_preview()
    
    def update_folder_preview(self):
        """Update the preview of folder structure"""
        if self.selected_list.count() == 0:
            self.example_text.setText("Select fields to see example folder structure")
            return
            
        # Build example structure
        structure = "destination/"
        for i in range(self.selected_list.count()):
            field = self.selected_list.item(i).text()
            structure += f"<{field}>/"
            
        # Add example values for clearer visualization
        example = structure.replace("<Show>", "<Show: PR2>")
        example = example.replace("<Scene>", "<Scene: 2.14B>")
        example = example.replace("<Take>", "<Take: 03>")
        example = example.replace("<Category>", "<Category: Andre>")
        example = example.replace("<Subcategory>", "<Subcategory: 2>")
        example = example.replace("<Slate>", "<Slate: D>")
        
        self.example_text.setText(example)


class FilenameExtractorDialog(QDialog):
    """Dialog for extracting metadata from filenames"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extract Metadata from Filenames")
        self.resize(500, 400)
        
        # Initial values
        self.separator = "_"
        self.mappings = []
        
        # Setup UI
        layout = QVBoxLayout(self)
        
        # Separator input
        separator_layout = QHBoxLayout()
        separator_label = QLabel("Separator:")
        separator_layout.addWidget(separator_label)
        
        self.separator_input = QLineEdit(self.separator)
        separator_layout.addWidget(self.separator_input)
        
        layout.addLayout(separator_layout)
        
        # Mappings table
        layout.addWidget(QLabel("Field Mappings:"))
        
        self.mappings_table = QTableWidget(0, 2)
        self.mappings_table.setHorizontalHeaderLabels(["Field", "Position"])
        self.mappings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mappings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.mappings_table.setColumnWidth(1, 100)
        layout.addWidget(self.mappings_table)
        
        # Add mapping button
        add_button = QPushButton("Add Mapping")
        add_button.clicked.connect(self.add_mapping)
        layout.addWidget(add_button)
        
        # Preset button for common pattern
        preset_button = QPushButton("Use Common Pattern (Show_Character_SceneNumber_Take)")
        preset_button.clicked.connect(self.preset_common_pattern)
        layout.addWidget(preset_button)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        ok_button = QPushButton("Extract")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
    
    def add_mapping(self):
        """Add a new mapping row"""
        row = self.mappings_table.rowCount()
        self.mappings_table.insertRow(row)
        
        # Field combo box
        field_combo = QComboBox()
        field_combo.addItems(["Show", "Scene", "Take", "Category", "Subcategory", "Slate"])
        self.mappings_table.setCellWidget(row, 0, field_combo)
        
        # Position spin box
        position_spin = QSpinBox()
        position_spin.setMinimum(1)
        position_spin.setMaximum(10)
        position_spin.setValue(row + 1)
        self.mappings_table.setCellWidget(row, 1, position_spin)
    
    def preset_common_pattern(self):
        """Set up mappings for common filename pattern: Show_Character_SceneNumber_Take"""
        # Clear existing mappings
        while self.mappings_table.rowCount() > 0:
            self.mappings_table.removeRow(0)
        
        # Add preset mappings
        mappings = [
            ("Show", 1),
            ("Category", 2), # Category is character
            ("Scene", 3),
            ("Take", 4)
        ]
        
        for field, position in mappings:
            row = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row)
            
            field_combo = QComboBox()
            field_combo.addItems(["Show", "Scene", "Take", "Category", "Subcategory", "Slate"])
            field_combo.setCurrentText(field)
            self.mappings_table.setCellWidget(row, 0, field_combo)
            
            position_spin = QSpinBox()
            position_spin.setMinimum(1)
            position_spin.setMaximum(10)
            position_spin.setValue(position)
            self.mappings_table.setCellWidget(row, 1, position_spin)
        
        # Set separator to underscore
        self.separator_input.setText("_")
    
    def accept(self):
        """Get the values when accepting the dialog"""
        self.separator = self.separator_input.text()
        if not self.separator:
            self.separator = "_"  # Default to underscore
        
        # Get mappings from table
        self.mappings = []
        for row in range(self.mappings_table.rowCount()):
            field_combo = self.mappings_table.cellWidget(row, 0)
            position_spin = self.mappings_table.cellWidget(row, 1)
            
            if field_combo and position_spin:
                field = field_combo.currentText()
                position = position_spin.value()
                self.mappings.append((field, position))
        
        super().accept()

class CSVMatchWizard(QDialog):
    """Wizard for matching CSV data to WAV files in steps"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Match CSV Data to Audio Files")
        self.resize(800, 600)
        
        # Initialize variables
        self.csv_file_path = ""
        self.csv_data = []
        self.csv_headers = []
        self.character_matches = {}  # Maps audio character to CSV character
        self.field_mappings = {}     # Maps CSV field names to audio metadata fields
        self.character_column = ""   # CSV column that contains character names
        self.scene_column = ""       # CSV column for scene matching
        self.take_column = ""        # CSV column for take matching
        self.current_step = 0        # Track the current step
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the wizard UI with a stacked widget for steps"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # Set dialog background and styling
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(245, 236, 220, 0.92);
            }
            QLabel {
                color: #333333;
            }
            QPushButton {
                background-color: rgba(245, 236, 220, 0.75);
                color: #333333;
                border: 1px solid rgba(224, 216, 201, 0.7);
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(232, 223, 208, 0.85);
            }
            QPushButton.primary {
                background-color: rgba(196, 181, 159, 0.85);
                color: white;
                border: none;
            }
            QPushButton.primary:hover {
                background-color: rgba(181, 167, 144, 0.95);
            }
            QGroupBox {
                background-color: rgba(245, 236, 220, 0.6);
                border: 1px solid rgba(224, 216, 201, 0.7);
                border-radius: 4px;
                margin-top: 12px;
                font-weight: bold;
                color: #333333;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #333333;
            }
            QListWidget {
                background-color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(224, 216, 201, 0.7);
                color: #333333;
            }
            QComboBox, QLineEdit {
                padding: 5px;
                border: 1px solid rgba(224, 216, 201, 0.7);
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.8);
                color: #333333;
            }
            QCheckBox {
                color: #333333;
            }
        """)
        
        # Page navigation - Step labels at the top
        self.step_layout = QHBoxLayout()
        
        # Step 1: Select CSV File and Match Characters
        self.step1_label = QLabel("1. Match Characters")
        self.step1_label.setStyleSheet("font-weight: bold; color: #333333; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7); background-color: rgba(245, 236, 220, 0.85);")
        self.step_layout.addWidget(self.step1_label)
        
        # Step 2: Match Entries
        self.step2_label = QLabel("2. Match Entries")
        self.step2_label.setStyleSheet("font-weight: normal; color: #666666; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7);")
        self.step_layout.addWidget(self.step2_label)
        
        # Step 3: Map Fields
        self.step3_label = QLabel("3. Map Fields")
        self.step3_label.setStyleSheet("font-weight: normal; color: #666666; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7);")
        self.step_layout.addWidget(self.step3_label)
        
        main_layout.addLayout(self.step_layout)
        
        # Stacked widget to hold the different pages/steps
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)  # 1 = stretch factor
        
        # Create pages for each step
        self.page1 = self.create_character_match_page()
        self.page2 = self.create_entry_match_page()
        self.page3 = self.create_field_mapping_page()
        
        # Add pages to stack
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)
        
        # Navigation buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.back_button = QPushButton("Back")
        self.back_button.setFixedWidth(100)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)  # Disabled on first page
        button_layout.addWidget(self.back_button)
        
        self.next_button = QPushButton("Next")
        self.next_button.setFixedWidth(100)
        self.next_button.setProperty("class", "primary")
        self.next_button.clicked.connect(self.go_next)
        button_layout.addWidget(self.next_button)
        
        self.finish_button = QPushButton("Finish")
        self.finish_button.setFixedWidth(100)
        self.finish_button.setProperty("class", "primary")
        self.finish_button.clicked.connect(self.accept)
        self.finish_button.setVisible(False)  # Only visible on last page
        button_layout.addWidget(self.finish_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        # Initialize the first page
        self.update_step_display()

    def create_character_match_page(self):
        """Create the character matching page (Step 1)"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # CSV file selection
        csv_file_group = QGroupBox("CSV File")
        csv_file_layout = QHBoxLayout(csv_file_group)
        csv_file_layout.setContentsMargins(10, 16, 10, 10)
        
        self.csv_file_input = QLineEdit()
        self.csv_file_input.setPlaceholderText("Select CSV file...")
        self.csv_file_input.setReadOnly(True)
        csv_file_layout.addWidget(self.csv_file_input)
        
        browse_button = QPushButton("Browse...")
        browse_button.setFixedWidth(100)
        browse_button.clicked.connect(self.browse_csv_file)
        csv_file_layout.addWidget(browse_button)
        
        layout.addWidget(csv_file_group)
        
        # Character matching section
        character_match_group = QGroupBox("Character Matching")
        character_match_layout = QVBoxLayout(character_match_group)
        character_match_layout.setContentsMargins(10, 20, 10, 10)
        
        # Auto-match explanation
        auto_match_label = QLabel("Characters with similar names will be auto-matched. Audio file names in camelCase will match if the first part matches the CSV character name.")
        auto_match_label.setWordWrap(True)
        auto_match_label.setStyleSheet("font-style: italic; color: #666666; font-size: 12px;")
        character_match_layout.addWidget(auto_match_label)
        
        # Add search filter
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: bold;")
        search_layout.addWidget(search_label)
        
        self.character_search_input = QLineEdit()
        self.character_search_input.setPlaceholderText("Filter characters...")
        self.character_search_input.setClearButtonEnabled(True)
        self.character_search_input.textChanged.connect(self.filter_character_lists)
        search_layout.addWidget(self.character_search_input)
        
        character_match_layout.addLayout(search_layout)
        
        # Instructions for using double-click
        double_click_label = QLabel("Double-click on a character to match it, or double-click a match to remove it.")
        double_click_label.setStyleSheet("font-style: italic; color: #666666; font-size: 12px;")
        character_match_layout.addWidget(double_click_label)
        
        # Character matching interface
        matching_layout = QHBoxLayout()
        
        # Audio characters list
        audio_char_container = QWidget()
        audio_char_layout = QVBoxLayout(audio_char_container)
        audio_char_layout.setContentsMargins(0, 0, 0, 0)
        
        audio_char_label = QLabel("Unmatched Audio Characters:")
        audio_char_label.setStyleSheet("font-weight: bold;")
        audio_char_layout.addWidget(audio_char_label)
        
        self.audio_char_list = QListWidget()
        self.audio_char_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.audio_char_list.itemDoubleClicked.connect(self.on_audio_char_double_clicked)
        audio_char_layout.addWidget(self.audio_char_list)
        
        matching_layout.addWidget(audio_char_container)
        
        # Buttons for matching
        buttons_container = QWidget()
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(8, 0, 8, 0)
        buttons_layout.addStretch()
        
        self.match_button = QPushButton("Match →")
        self.match_button.clicked.connect(self.match_selected_characters)
        buttons_layout.addWidget(self.match_button)
        
        self.unmatch_button = QPushButton("← Unmatch")
        self.unmatch_button.clicked.connect(self.unmatch_selected_character)
        buttons_layout.addWidget(self.unmatch_button)
        
        buttons_layout.addStretch()
        
        matching_layout.addWidget(buttons_container)
        
        # CSV characters list
        csv_char_container = QWidget()
        csv_char_layout = QVBoxLayout(csv_char_container)
        csv_char_layout.setContentsMargins(0, 0, 0, 0)
        
        csv_char_label = QLabel("Unmatched CSV Characters:")
        csv_char_label.setStyleSheet("font-weight: bold;")
        csv_char_layout.addWidget(csv_char_label)
        
        self.csv_char_list = QListWidget()
        self.csv_char_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.csv_char_list.itemDoubleClicked.connect(self.on_csv_char_double_clicked)
        csv_char_layout.addWidget(self.csv_char_list)
        
        matching_layout.addWidget(csv_char_container)
        
        # Matched pairs list
        matches_container = QWidget()
        matches_layout = QVBoxLayout(matches_container)
        matches_layout.setContentsMargins(0, 0, 0, 0)
        
        matches_label = QLabel("Current Matches:")
        matches_label.setStyleSheet("font-weight: bold;")
        matches_layout.addWidget(matches_label)
        
        self.matches_list = QListWidget()
        self.matches_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.matches_list.itemDoubleClicked.connect(self.on_match_double_clicked)
        matches_layout.addWidget(self.matches_list)
        
        matching_layout.addWidget(matches_container)
        
        character_match_layout.addLayout(matching_layout)
        
        # Auto-match button
        auto_match_button = QPushButton("Auto-Match All")
        auto_match_button.clicked.connect(self.auto_match_characters)
        character_match_layout.addWidget(auto_match_button)
        
        layout.addWidget(character_match_group, 1)
        
        return page

    def filter_character_lists(self):
        """Filter all character lists based on search input"""
        search_text = self.character_search_input.text().lower()
        
        # Store current selections
        audio_current = self.audio_char_list.currentItem()
        audio_current_text = audio_current.text() if audio_current else ""
        
        csv_current = self.csv_char_list.currentItem()
        csv_current_text = csv_current.text() if csv_current else ""
        
        matches_current = self.matches_list.currentItem()
        matches_current_text = matches_current.text() if matches_current else ""
        
        # Make sure lists are up to date before filtering
        # This ensures we have _all_unmatched_audio_chars and _all_unmatched_csv_chars
        self.update_audio_character_list()
        self.update_csv_character_list()
        
        # 1. Filter Audio characters list
        self.audio_char_list.clear()
        if hasattr(self, '_all_unmatched_audio_chars'):
            for character in self._all_unmatched_audio_chars:
                if not search_text or search_text in character.lower():
                    self.audio_char_list.addItem(character)
                    
            # Restore selection if possible
            if audio_current_text:
                for i in range(self.audio_char_list.count()):
                    if self.audio_char_list.item(i).text() == audio_current_text:
                        self.audio_char_list.setCurrentRow(i)
                        break
        
        # 2. Filter CSV characters list
        self.csv_char_list.clear()
        if hasattr(self, '_all_unmatched_csv_chars'):
            for character in self._all_unmatched_csv_chars:
                if not search_text or search_text in character.lower():
                    self.csv_char_list.addItem(character)
                    
            # Restore selection if possible
            if csv_current_text:
                for i in range(self.csv_char_list.count()):
                    if self.csv_char_list.item(i).text() == csv_current_text:
                        self.csv_char_list.setCurrentRow(i)
                        break
        
        # 3. Filter Matches list
        self.matches_list.clear()
        sorted_matches = sorted(self.character_matches.items(), key=lambda x: x[0])
        for audio_char, csv_char in sorted_matches:
            match_text = f"{audio_char} → {csv_char}"
            if not search_text or search_text in audio_char.lower() or search_text in csv_char.lower():
                self.matches_list.addItem(match_text)
                
        # Restore selection if possible
        if matches_current_text:
            for i in range(self.matches_list.count()):
                if self.matches_list.item(i).text() == matches_current_text:
                    self.matches_list.setCurrentRow(i)
                    break
    
    def update_character_lists(self):
        """Update both character lists to reflect current matches"""
        # Store search text to reapply filter
        search_text = ""
        if hasattr(self, 'character_search_input'):
            search_text = self.character_search_input.text()
            
        # First update the raw lists
        self.update_audio_character_list()
        self.update_csv_character_list()
        
        # Then apply the search filter if there's any search text
        if search_text:
            self.filter_character_lists()
            
    def update_matches_list(self):
        """Update the list of matched character pairs"""
        # Store search text and current selection to reapply
        search_text = ""
        if hasattr(self, 'character_search_input'):
            search_text = self.character_search_input.text()
            
        current_item = self.matches_list.currentItem()
        current_text = current_item.text() if current_item else ""
        
        # Clear and update the list
        self.matches_list.clear()
        
        # Sort matches alphabetically by audio character name
        sorted_matches = sorted(self.character_matches.items(), key=lambda x: x[0])
        
        # Add all items if no search, or only matching items if searching
        for audio_char, csv_char in sorted_matches:
            match_text = f"{audio_char} → {csv_char}"
            if not search_text or search_text.lower() in audio_char.lower() or search_text.lower() in csv_char.lower():
                self.matches_list.addItem(match_text)
                
        # Restore previous selection if possible
        if current_text:
            for i in range(self.matches_list.count()):
                if self.matches_list.item(i).text() == current_text:
                    self.matches_list.setCurrentRow(i)
                    break
    
    def auto_match_characters(self):
        """Automatically match characters with the same name or closest match"""
        if not self.csv_data or not self.character_column:
            return
            
        try:
            # Get all available audio characters
            audio_characters = set()
            for file_path, metadata in self.parent.all_files:
                character = metadata.get("Category", "")
                if character:
                    audio_characters.add(character)
            
            # Get all available CSV characters
            char_col_idx = self.csv_headers.index(self.character_column)
            csv_characters = set()
            for row in self.csv_data:
                if char_col_idx < len(row) and row[char_col_idx]:
                    csv_characters.add(row[char_col_idx])
            
            # Track which CSV characters are already matched to ensure 1-to-1 matching
            matched_csv_chars = set(self.character_matches.values())
            available_csv_chars = csv_characters - matched_csv_chars
            
            # Store all candidate matches with scores for later processing
            all_potential_matches = []
            
            # First pass: gather all potential matches with scores
            for audio_char in audio_characters:
                if audio_char not in self.character_matches:
                    # Extract any numbers from the end of the audio character name
                    audio_number_match = re.search(r'(\d+)$', audio_char)
                    audio_number = audio_number_match.group(1) if audio_number_match else None
                    
                    # Try exact match first (case-insensitive)
                    exact_matches = [c for c in available_csv_chars if c.lower() == audio_char.lower()]
                    if exact_matches:
                        all_potential_matches.append((audio_char, exact_matches[0], 200))  # Perfect match gets highest score
                        continue
                    
                    # Special handling for numbered characters
                    if audio_number:
                        # Look for CSV characters with the same base name and matching number
                        audio_base = audio_char[:audio_number_match.start()]
                        for csv_char in available_csv_chars:
                            csv_lower = csv_char.lower()
                            
                            # Look for "#number" pattern in CSV character
                            csv_number_match = re.search(r'#(\d+)', csv_char)
                            if csv_number_match and csv_number_match.group(1) == audio_number:
                                # Check if the base name also matches
                                csv_base = csv_lower.split('#')[0].strip()
                                if audio_base.lower() in csv_base or csv_base in audio_base.lower():
                                    all_potential_matches.append((audio_char, csv_char, 150))  # High score for number match
                            
                            # Also check for plain numbers at the end of CSV character
                            csv_plain_number_match = re.search(r'(\d+)$', csv_lower)
                            if csv_plain_number_match and csv_plain_number_match.group(1) == audio_number:
                                # Check if the base name also matches
                                csv_base = csv_lower[:csv_plain_number_match.start()].strip()
                                if audio_base.lower() in csv_base or csv_base in audio_base.lower():
                                    all_potential_matches.append((audio_char, csv_char, 140))  # Good score for number match
                    
                    # Split audio character into words
                    audio_words = re.findall(r'[A-Z]?[a-z]+|\d+', audio_char)  # Split camelCase into words
                    audio_words_lower = [w.lower() for w in audio_words]
                    
                    # Handle word-based matching
                    for csv_char in available_csv_chars:
                        csv_lower = csv_char.lower()
                        
                        # Score based on word matching
                        score = 0
                        
                        # If character already got a numbered match, skip word matching
                        if any(match[0] == audio_char and match[2] >= 140 for match in all_potential_matches):
                            continue
                        
                        # Check for exact word matches, regardless of order
                        csv_words = csv_lower.split()
                        matching_words = set(audio_words_lower) & set(csv_words)
                        
                        # Calculate percentage of matching words
                        if matching_words:
                            # More weight to exact word matches
                            match_percentage = len(matching_words) / max(len(audio_words_lower), len(csv_words))
                            score += int(match_percentage * 60)  # Up to 60 points for word matches
                            
                            # Bonus if first word matches - often indicates character type
                            if audio_words_lower and csv_words and audio_words_lower[0] == csv_words[0]:
                                score += 20
                            
                            # Extra bonus for full word-for-word match, regardless of case/order
                            if len(matching_words) == len(audio_words_lower) == len(csv_words):
                                score += 50
                        
                        # Check for subword/substring matches if no exact word matches
                        if not matching_words:
                            # Check if audio character appears as substring in CSV
                            if ''.join(audio_words_lower) in csv_lower.replace(' ', ''):
                                score += 15
                            
                            # Check if CSV character appears as substring in audio
                            elif csv_lower.replace(' ', '') in ''.join(audio_words_lower):
                                score += 10
                                
                            # Individual word substring check
                            else:
                                for aw in audio_words_lower:
                                    if any(aw in cw or cw in aw for cw in csv_words):
                                        score += 5
                        
                        # Add to potential matches if score is positive
                        if score > 0:
                            all_potential_matches.append((audio_char, csv_char, score))
            
            # Sort all potential matches by score (highest first)
            all_potential_matches.sort(key=lambda x: x[2], reverse=True)
            
            # Debug: Print potential matches
            print("Potential matches (sorted by score):")
            for audio_char, csv_char, score in all_potential_matches:
                print(f"  {audio_char} → {csv_char} (score: {score})")
            
            # Second pass: apply matches ensuring 1-to-1 relationship
            matched_csv_chars = set()  # Track which CSV chars are already used
            matched_audio_chars = set()  # Track which audio chars are already matched
            
            for audio_char, csv_char, score in all_potential_matches:
                # Skip if audio char already matched (from previous matches)
                if audio_char in self.character_matches or audio_char in matched_audio_chars:
                    continue
                    
                # Skip if csv char already matched
                if csv_char in matched_csv_chars:
                    continue
                    
                # Apply the match
                self.character_matches[audio_char] = csv_char
                matched_csv_chars.add(csv_char)
                matched_audio_chars.add(audio_char)
            
            # Update the lists
            self.update_matches_list()
            self.update_character_lists()
            
            # Show a message about the results
            matched_count = len(self.character_matches)
            QMessageBox.information(
                self, 
                "Auto-Match Results", 
                f"Matched {matched_count} characters with a one-to-one relationship.\n\n"
                f"Each CSV character is now matched to at most one audio character."
            )
            
        except Exception as e:
            print(f"Error auto-matching characters: {e}")
            QMessageBox.warning(self, "Error", f"Error auto-matching characters: {e}")
            
    def load_csv_data(self):
        """Load data from the selected CSV file"""
        import csv
        
        try:
            with open(self.csv_file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                self.csv_headers = next(reader)  # Get headers
                self.csv_data = list(reader)      # Get all data rows
            
            # Try to detect character, scene and take columns based on name
            for i, header in enumerate(self.csv_headers):
                lower_header = header.lower()
                if 'character' in lower_header or 'actor' in lower_header or 'talent' in lower_header:
                    self.character_column = header
                elif 'scene' in lower_header:
                    self.scene_column = header
                elif 'take' in lower_header:
                    self.take_column = header
            
            # Reset existing matches when loading a new CSV
            self.character_matches = {}
            
            # Update character lists with unmatched items
            self.update_character_lists()
            
            # Try auto-matching characters
            self.auto_match_characters()
            
            # Success message
            QMessageBox.information(self, "CSV Loaded", f"Successfully loaded CSV with {len(self.csv_data)} rows.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error Loading CSV", f"Failed to load CSV file: {e}")
            
    def validate_current_step(self):
        """Validate the current step before allowing to proceed"""
        if self.current_step == 0:  # Character matching
            # Check if CSV file is loaded
            if not self.csv_data:
                QMessageBox.warning(self, "No CSV File", "Please select a CSV file first.")
                return False
                
            # Check if character column is selected
            if not self.character_column:
                QMessageBox.warning(self, "Missing Column", "Please select a character column in the CSV file.")
                return False
                
            # Check if any characters are matched
            if not self.character_matches:
                QMessageBox.warning(self, "No Matches", "Please match at least one character before continuing.")
                return False
                
            return True
        
        elif self.current_step == 1:  # Entry matching
            # Check if scene column is selected
            if not self.scene_column:
                QMessageBox.warning(self, "Missing Column", "Please select a scene column in the CSV file.")
                return False
                
            # Check if take column is selected
            if not self.take_column:
                QMessageBox.warning(self, "Missing Column", "Please select a take column in the CSV file.")
                return False
                
            # Check if we have potential matches
            try:
                char_col_idx = self.csv_headers.index(self.character_column)
                scene_col_idx = self.csv_headers.index(self.scene_column)
                take_col_idx = self.csv_headers.index(self.take_column)
                
                # Build a lookup of available CSV entries
                csv_entries = {}
                for row in self.csv_data:
                    if max(char_col_idx, scene_col_idx, take_col_idx) < len(row):
                        char = row[char_col_idx]
                        scene = row[scene_col_idx]
                        take = row[take_col_idx]
                        
                        # Build a key for lookup
                        key = (char, scene, take)
                        csv_entries[key] = True
                
                # Check which audio files would match
                matched_count = 0
                
                if hasattr(self.parent, 'all_files'):
                    for file_path, metadata in self.parent.all_files:
                        audio_char = metadata.get("Category", "")
                        if not audio_char or audio_char not in self.character_matches:
                            continue
                        
                        csv_char = self.character_matches[audio_char]
                        audio_scene = metadata.get("Scene", "")
                        audio_take = metadata.get("Take", "")
                        
                        if audio_scene and audio_take:
                            # Check exact match
                            key = (csv_char, audio_scene, audio_take)
                            if key in csv_entries:
                                matched_count += 1
                            elif self.partial_scene_check.isChecked():
                                # Try partial match if enabled
                                for csv_key in csv_entries.keys():
                                    csv_char_match, csv_scene, csv_take = csv_key
                                    
                                    if csv_char_match != csv_char:
                                        continue
                                    
                                    # Check if take matches (with or without case sensitivity)
                                    if self.case_sensitive_check.isChecked():
                                        # Case sensitive comparison
                                        if csv_take != audio_take:
                                            continue
                                    else:
                                        # Case insensitive comparison
                                        if csv_take.lower() != audio_take.lower():
                                            continue
                                    
                                    # Check if scene partially matches (with or without case sensitivity)
                                    if self.case_sensitive_check.isChecked():
                                        # Case sensitive comparison
                                        if csv_scene and audio_scene.startswith(csv_scene):
                                            matched_count += 1
                                            break
                                    else:
                                        # Case insensitive comparison
                                        if csv_scene and audio_scene.lower().startswith(csv_scene.lower()):
                                            matched_count += 1
                                            break
                
                if matched_count == 0:
                    result = QMessageBox.question(
                        self, 
                        "No Matches Found", 
                        "No matches were found with the current settings. Would you like to continue anyway?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if result == QMessageBox.StandardButton.No:
                        return False
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error validating matches: {str(e)}")
                return False
                
            return True
    
    def update_step_display(self):
        """Update the step display and button visibility"""
        # Reset all step labels
        self.step1_label.setStyleSheet("font-weight: normal; color: #666666; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7);")
        self.step2_label.setStyleSheet("font-weight: normal; color: #666666; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7);")
        self.step3_label.setStyleSheet("font-weight: normal; color: #666666; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7);")
        
        # Highlight current step
        if self.current_step == 0:
            self.step1_label.setStyleSheet("font-weight: bold; color: #333333; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7); background-color: rgba(245, 236, 220, 0.85);")
            self.back_button.setEnabled(False)
            self.next_button.setVisible(True)
            self.finish_button.setVisible(False)
        elif self.current_step == 1:
            self.step2_label.setStyleSheet("font-weight: bold; color: #333333; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7); background-color: rgba(245, 236, 220, 0.85);")
            self.back_button.setEnabled(True)
            self.next_button.setVisible(True)
            self.finish_button.setVisible(False)
        elif self.current_step == 2:
            self.step3_label.setStyleSheet("font-weight: bold; color: #333333; padding: 5px; border: 1px solid rgba(224, 216, 201, 0.7); background-color: rgba(245, 236, 220, 0.85);")
            self.back_button.setEnabled(True)
            self.next_button.setVisible(False)
            self.finish_button.setVisible(True)
    
    def go_back(self):
        """Navigate to the previous step"""
        if self.current_step > 0:
            self.current_step -= 1
            self.stack.setCurrentIndex(self.current_step)
            self.update_step_display()
    
    def go_next(self):
        """Navigate to the next step"""
        # Validate current step
        if not self.validate_current_step():
                return
        
        # Move to next step if validation passed
        if self.current_step < 2:
            self.current_step += 1
            self.stack.setCurrentIndex(self.current_step)
            self.update_step_display()
            
            # Update the appropriate page based on new step
            if self.current_step == 1:
                # Update entry match page
                self.update_entry_match_display()
            elif self.current_step == 2:
                # Update field mapping page
                self.update_mapping_preview()
                
                # Initialize the field mapping controls if not already done
                if not hasattr(self, 'field_mapping_controls') or not self.field_mapping_controls:
                    self.auto_map_fields()
    
    def update_entry_match_display(self):
        """Update the entry match page based on current selections"""
        if not hasattr(self, 'scene_column_combo') or not hasattr(self, 'take_column_combo'):
            return
            
        # Update character column display
        if hasattr(self, 'character_display'):
            self.character_display.setText(self.character_column if hasattr(self, 'character_column') else "")
            
        # Populate scene preview list
        if hasattr(self, 'scene_preview_list'):
            self.scene_preview_list.clear()
            if self.scene_column and self.csv_data:
                try:
                    scene_col_idx = self.csv_headers.index(self.scene_column)
                    scenes = set()
                    for row in self.csv_data:
                        if scene_col_idx < len(row) and row[scene_col_idx]:
                            scenes.add(row[scene_col_idx])
                    
                    for scene in sorted(scenes):
                        self.scene_preview_list.addItem(scene)
                except (ValueError, IndexError):
                    pass
        
        # Populate take preview list
        if hasattr(self, 'take_preview_list'):
            self.take_preview_list.clear()
            if self.take_column and self.csv_data:
                try:
                    take_col_idx = self.csv_headers.index(self.take_column)
                    takes = set()
                    for row in self.csv_data:
                        if take_col_idx < len(row) and row[take_col_idx]:
                            takes.add(row[take_col_idx])
                    
                    for take in sorted(takes):
                        self.take_preview_list.addItem(take)
                except (ValueError, IndexError):
                    pass
        
        # Update match summary
        if hasattr(self, 'match_summary'):
            summary_text = ""
            
            # Get potential matches count
            if self.character_matches and self.scene_column and self.take_column and self.csv_data:
                try:
                    # Get indices for columns
                    char_col_idx = self.csv_headers.index(self.character_column)
                    scene_col_idx = self.csv_headers.index(self.scene_column)
                    take_col_idx = self.csv_headers.index(self.take_column)
                    
                    # Build a lookup of available CSV entries
                    csv_entries = {}
                    for row in self.csv_data:
                        if max(char_col_idx, scene_col_idx, take_col_idx) < len(row):
                            char = row[char_col_idx]
                            scene = row[scene_col_idx]
                            take = row[take_col_idx]
                            
                            # Build a key for lookup
                            key = (char, scene, take)
                            csv_entries[key] = True
                    
                    # Check which audio files would match
                    matched_count = 0
                    total_count = 0
                    matched_chars = set()
                    
                    # Get unique scene and take combinations from audio files
                    audio_scenes = set()
                    audio_takes = set()
                    
                    if hasattr(self.parent, 'all_files'):
                        for file_path, metadata in self.parent.all_files:
                            audio_char = metadata.get("Category", "")
                            if not audio_char:
                                continue
                                
                            total_count += 1
                            
                            # Check if character is matched
                            if audio_char in self.character_matches:
                                csv_char = self.character_matches[audio_char]
                                matched_chars.add(audio_char)
                                
                                # Get scene and take from audio file
                                audio_scene = metadata.get("Scene", "")
                                audio_take = metadata.get("Take", "")
                                
                                if audio_scene and audio_take:
                                    audio_scenes.add(audio_scene)
                                    audio_takes.add(audio_take)
                                    
                                    # Check exact match
                                    key = (csv_char, audio_scene, audio_take)
                                    if key in csv_entries:
                                        matched_count += 1
                                    elif self.partial_scene_check.isChecked():
                                        # Try partial match if enabled
                                        for csv_key in csv_entries.keys():
                                            csv_char_match, csv_scene, csv_take = csv_key
                                            
                                            if csv_char_match != csv_char:
                                                continue
                                            
                                            # Check if take matches (with or without case sensitivity)
                                            if self.case_sensitive_check.isChecked():
                                                # Case sensitive comparison
                                                if csv_take != audio_take:
                                                    continue
                                            else:
                                                # Case insensitive comparison
                                                if csv_take.lower() != audio_take.lower():
                                                    continue
                                            
                                            # Check if scene partially matches (with or without case sensitivity)
                                            if self.case_sensitive_check.isChecked():
                                                # Case sensitive comparison
                                                if csv_scene and audio_scene.startswith(csv_scene):
                                                    matched_count += 1
                                                    break
                                            else:
                                                # Case insensitive comparison
                                                if csv_scene and audio_scene.lower().startswith(csv_scene.lower()):
                                                    matched_count += 1
                                                    break
                    
                    # Build summary
                    summary_text += f"Character matches: {len(self.character_matches)} characters\n"
                    summary_text += f"Audio files with matched characters: {len(matched_chars)} characters\n"
                    summary_text += f"Scene values in audio files: {len(audio_scenes)}\n"
                    summary_text += f"Take values in audio files: {len(audio_takes)}\n\n"
                    
                    if total_count > 0:
                        match_percent = (matched_count / total_count) * 100
                        summary_text += f"Potential matches: {matched_count} of {total_count} files ({match_percent:.1f}%)\n"
                        
                        if matched_count == 0:
                            summary_text += "\nNo matches found. Please check your scene and take column selections."
                        elif matched_count < total_count * 0.5:
                            summary_text += "\nFew matches found. You may want to check your scene and take column selections."
                except Exception as e:
                    summary_text = f"Error generating match summary: {str(e)}"
            else:
                summary_text = "Please select the character, scene, and take columns to see potential matches."
            
            self.match_summary.setText(summary_text)
    
    def add_field_mapping(self):
        """Add a new field mapping row."""
        current_row = self.field_mapping_list.rowCount()
        self.field_mapping_list.insertRow(current_row)
        
        # Create combobox for CSV fields
        csv_combo = QComboBox()
        if self.csv_headers:
            csv_combo.addItems(self.csv_headers)
        
        # Create combobox for metadata fields
        meta_combo = QComboBox()
        meta_fields = ["Show", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]
        meta_combo.addItems(meta_fields)
        
        # Add widgets to the table
        self.field_mapping_list.setCellWidget(current_row, 0, csv_combo)
        self.field_mapping_list.setCellWidget(current_row, 1, meta_combo)
        
        # Update the preview
        self.update_mapping_preview()

# --- Appended Main Execution Block (for debugging GUI launch) ---
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Audio Metadata Editor")
    
    # Optional: For High DPI displays
    # if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    #     QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    # if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    #     QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = AudioMetadataEditor()
    window.show()  # Ensure the window is explicitly shown
    sys.exit(app.exec()) # Start the event loop

if __name__ == "__main__":
    multiprocessing.freeze_support() # For PyInstaller/bundling
    main()
# --- End of Appended Main Execution Block ---