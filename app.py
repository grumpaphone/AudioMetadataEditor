#!/usr/bin/env python3
import sys
import os
import re
import shutil  # For file copying operations
import json
import wav_metadata
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, 
                             QTableWidgetItem, QVBoxLayout, QWidget, QFileDialog,
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView,
                             QLineEdit, QLabel, QComboBox, QGroupBox, QFormLayout,
                             QDialog, QSpinBox, QSplitter, QFrame, QToolBar, 
                             QStatusBar, QStyle, QSizePolicy, QStyledItemDelegate,
                             QGridLayout, QListWidget, QCheckBox, QProgressDialog,
                             QMenu, QScrollArea, QStackedWidget)
from PyQt6.QtCore import Qt, QMimeData, QSortFilterProxyModel, QSize, QMargins, QPropertyAnimation, QEasingCurve, QTimer, QRect, pyqtProperty
from PyQt6.QtGui import QPalette, QColor, QIcon, QFont, QPainter, QBrush, QPen, QPainterPath, QPixmap
from PyQt6.QtSvg import QSvgRenderer


class MacStyleDelegate(QStyledItemDelegate):
    """Custom delegate for macOS style table items"""
    def paint(self, painter, option, index):
        # Save painter state
        painter.save()
        
        # Draw background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#E0F2FF"))  # Light blue for selection
        elif index.row() % 2 == 0:  # Use index.row() instead of option.row
            painter.fillRect(option.rect, QColor("#FAFAFA"))  # Very light gray for alternating
        else:
            painter.fillRect(option.rect, QColor("#FFFFFF"))  # White
        
        # Draw text with proper padding
        text_rect = option.rect.adjusted(12, 6, -12, -6)  # Add padding
        
        # Set text color
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QColor("#000000"))  # Black text on selection
        else:
            painter.setPen(QColor("#000000"))  # Black text normally
            
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, index.data())
        
        # Restore painter state
        painter.restore()


class AnimatedPushButton(QPushButton):
    """Custom button with click animation"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        # Initialize attributes first
        self._normal_color = QColor(245, 236, 220, 153)  # 60% opacity
        self._hover_color = QColor(232, 223, 208, 204)   # 80% opacity
        self._click_color = QColor(224, 216, 201, 230)   # 90% opacity
        self._current_color = self._normal_color
        
        # Then create the animation
        self._animation = QPropertyAnimation(self, b"background_color")
        self._animation.setDuration(150)
        self.setStyleSheet(f"background-color: {self._normal_color.name()}")
        
    def get_background_color(self):
        return self._current_color
        
    def set_background_color(self, color):
        if self._current_color != color:
            self._current_color = color
            self.setStyleSheet(f"background-color: {color.name()}")
            
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
        super().__init__(text, parent)
        # Use primary colors
        self._normal_color = QColor(196, 181, 159, 230)  # 90% opacity
        self._hover_color = QColor(181, 167, 144, 242)   # 95% opacity
        self._click_color = QColor(166, 152, 127, 255)   # 100% opacity
        self._current_color = self._normal_color
        self.setStyleSheet(f"background-color: {self._normal_color.name()}; color: white; border: none;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class AudioMetadataEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Metadata Editor")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)
        
        # Configure for frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set the application style
        self.apply_stylesheet()
        
        # Setup UI
        self.central_widget = QWidget()
        self.central_widget.setObjectName("central_widget")
        self.central_widget.setStyleSheet("""
            #central_widget {
                background-color: rgba(245, 236, 220, 0.92);
                border-radius: 10px;
            }
        """)
        self.setCentralWidget(self.central_widget)
        
        # Main layout with reduced margins
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(10, 8, 10, 8) # Reduced from 20,15,20,15
        main_layout.setSpacing(8) # Reduced from 15
        
        # Add integrated title bar with window controls and app controls
        self.create_integrated_title_bar(main_layout)
        
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
        
        table_layout.addWidget(self.metadata_table)
        
        content_layout.addWidget(table_container, 1)  # 1 = stretch factor
        
        self.content_layout.addWidget(content_container, 1)  # 1 = stretch factor
        
        # Status bar at the bottom - subtle, Apple-style
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("class", "status-label")
        self.content_layout.addWidget(self.status_label)
        
        # Data storage
        self.all_files = []
        self.filtered_rows = []
        self.changes_pending = False
        
        # Enable animations in the application
        self.animations_enabled = True
    
    def apply_stylesheet(self):
        """Apply a modern macOS-inspired stylesheet with translucent elements"""
        # Set system font (SF Pro-like) - using system font family instead of specific name
        if sys.platform == "darwin":  # macOS
            app_font = QFont(".AppleSystemUIFont", 12)  # Smaller font size
        else:  # Windows/Linux
            app_font = QFont("Segoe UI", 12)  # Smaller font size
        QApplication.setFont(app_font)
        
        # Create and apply stylesheet
        stylesheet = """
        /* Main window - higher alpha for frostier effect */
        QMainWindow {
            background-color: rgba(245, 236, 220, 0.92);
            border: none;
            border-radius: 10px;
        }
        
        /* Content container */
        .content-container {
            background-color: rgba(245, 236, 220, 0.85);
            border-radius: 10px;
        }
        
        /* Icon button style */
        .icon-button {
            background-color: rgba(245, 236, 220, 0.75);
            border: none;
            border-radius: 8px;
            padding: 8px;
        }
        
        .icon-button:hover {
            background-color: rgba(232, 223, 208, 0.85);
        }
        
        .icon-button:pressed {
            background-color: rgba(224, 216, 201, 0.92);
        }
        
        /* Action button style */
        .action-button {
            background-color: rgba(245, 236, 220, 0.75);
            color: #000000;
            border: none;
            border-radius: 8px;
            font-weight: 500;
            font-size: 13px;
        }
        
        .action-button:hover {
            background-color: rgba(232, 223, 208, 0.85);
        }
        
        .action-button:pressed {
            background-color: rgba(224, 216, 201, 0.92);
        }
        
        /* Primary button style */
        .action-button.primary {
            background-color: rgba(196, 181, 159, 0.92);
            color: white;
            border: none;
        }
        
        .action-button.primary:hover {
            background-color: rgba(181, 167, 144, 0.95);
        }
        
        .action-button.primary:pressed {
            background-color: rgba(166, 152, 127, 1.0);
        }
        
        /* QLineEdit styling */
        QLineEdit {
            border: 1px solid rgba(224, 216, 201, 0.8);
            border-radius: 6px;
            padding: 4px 6px;
            background-color: rgba(255, 255, 255, 0.85);
            selection-background-color: rgba(196, 181, 159, 0.8);
            selection-color: white;
        }
        
        QLineEdit:focus {
            border: 1px solid rgba(196, 181, 159, 0.92);
            background-color: rgba(255, 255, 255, 0.95);
        }
        
        /* Labels */
        QLabel {
            color: #000000;
            font-size: 13px;
        }
        
        /* Title label larger */
        #title_label {
            font-size: 18px;
            font-weight: 500;
            color: #000000;
        }
        
        /* Table styling */
        QTableWidget {
            border: none;
            background-color: rgba(255, 255, 255, 0.9);
            selection-background-color: rgba(232, 223, 208, 0.85);
            alternate-background-color: rgba(249, 245, 239, 0.75);
            gridline-color: rgba(232, 223, 208, 0.8);
        }
        
        QHeaderView::section {
            background-color: rgba(255, 255, 255, 0.85);
            padding: 6px;
            border: none;
            border-bottom: 1px solid rgba(224, 216, 201, 0.8);
            font-weight: 500;
            color: #333333;
        }
        
        /* Status bar */
        .status-label {
            color: #666666;
            font-size: 12px;
            padding: 4px;
        }
        
        /* Dialog styling */
        QDialog {
            background-color: rgba(245, 236, 220, 0.92);
            border-radius: 8px;
        }
        
        /* Dropdown/ComboBox styling */
        QComboBox {
            border: 1px solid rgba(208, 200, 185, 0.8);
            border-radius: 6px;
            padding: 5px;
            background-color: rgba(255, 255, 255, 0.85);
            color: #333333;
            selection-background-color: rgba(196, 181, 159, 0.8);
            selection-color: white;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid rgba(208, 200, 185, 0.8);
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }
        
        QComboBox::down-arrow {
            width: 12px;
            height: 12px;
            image: url(:/icons/dropdown_arrow.png);
        }
        
        QComboBox QAbstractItemView {
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(208, 200, 185, 0.8);
            color: #333333;
            selection-background-color: rgba(196, 181, 159, 0.8);
            selection-color: white;
        }
        
        /* Line Edit and ComboBox common styles */
        QLineEdit, QComboBox, QSpinBox {
            padding: 5px;
            border: 1px solid rgba(208, 200, 185, 0.8);
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.85);
            color: #333333;
        }
        
        /* Splitter styling */
        QSplitter::handle {
            background-color: rgba(224, 216, 201, 0.7);
        }
        
        /* Menu styling */
        QMenu {
            background-color: rgba(245, 236, 220, 0.95);
            border: 1px solid rgba(224, 216, 201, 0.8);
            border-radius: 6px;
            padding: 4px;
        }
        
        QMenu::item {
            padding: 4px 20px 4px 6px;
            border-radius: 4px;
            color: #333333;
        }
        
        QMenu::item:selected {
            background-color: rgba(232, 223, 208, 0.85);
        }
        
        /* QScrollBar styling */
        QScrollBar:vertical {
            border: none;
            background: rgba(245, 236, 220, 0.4);
            width: 10px;
            margin: 0px;
            border-radius: 5px;
        }
        
        QScrollBar::handle:vertical {
            background: rgba(196, 181, 159, 0.8);
            min-height: 20px;
            border-radius: 5px;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
            height: 0px;
        }
        
        QScrollBar:horizontal {
            border: none;
            background: rgba(245, 236, 220, 0.4);
            height: 10px;
            margin: 0px;
            border-radius: 5px;
        }
        
        QScrollBar::handle:horizontal {
            background: rgba(196, 181, 159, 0.8);
            min-width: 20px;
            border-radius: 5px;
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
            width: 0px;
        }
        """
        self.setStyleSheet(stylesheet)

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
        """Load WAV files from a folder."""
        import glob
        
        # Find all WAV files in the folder and subfolders
        wav_files = glob.glob(os.path.join(folder_path, "**", "*.wav"), recursive=True)
        
        if not wav_files:
            QMessageBox.warning(self, "No WAV Files", f"No WAV files found in {folder_path}")
            return
        
        # Clear existing data
        self.all_files = []
        self.metadata_table.setRowCount(0)
        
        # Show progress in status bar
        self.status_label.setText(f"Loading {len(wav_files)} WAV files...")
        QApplication.processEvents()
        
        # Load metadata for each file
        for file_path in wav_files:
            try:
                metadata = wav_metadata.read_wav_metadata(file_path)
                # Add filename to metadata
                metadata["Filename"] = os.path.basename(file_path)
                self.all_files.append((file_path, metadata))
            except Exception as e:
                print(f"Error reading metadata from {file_path}: {e}")
        
        # Update the UI
        self.update_table()
        self.status_label.setText(f"Loaded {len(self.all_files)} WAV files")
    
    def update_table(self):
        """Update the table with current metadata."""
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
        """Filter the table based on search term."""
        search_term = self.search_input.text().lower()
        search_field = self.current_search_field
        
        # Disconnect signals temporarily
        self.metadata_table.blockSignals(True)
        
        # Clear the table
        self.metadata_table.setRowCount(0)
        
        # Reset filtered rows if no search term
        if not search_term:
            self.filtered_rows = list(range(len(self.all_files)))
        else:
            self.filtered_rows = []
            for i, (file_path, metadata) in enumerate(self.all_files):
                # Check if the search term is in the specified field or any field
                if search_field == "All Fields":
                    # Search in all fields including filename
                    filename = os.path.basename(file_path)
                    found = search_term in filename.lower() or any(search_term in str(value).lower() for value in metadata.values())
                elif search_field == "Filename":
                    # Search in filename
                    filename = os.path.basename(file_path)
                    found = search_term in filename.lower()
                else:
                    # Search in the specified field
                    found = search_term in str(metadata.get(search_field, "")).lower()
                
                if found:
                    self.filtered_rows.append(i)
        
        # Populate the table with filtered rows
        for row, idx in enumerate(self.filtered_rows):
            file_path, metadata = self.all_files[idx]
            
            # Add a new row to the table
            self.metadata_table.insertRow(row)
            
            # Get the filename from the file_path
            filename = os.path.basename(file_path)
            
            # Set the filename in the first column
            self.metadata_table.setItem(row, 0, QTableWidgetItem(filename))
            
            # Set metadata fields in the respective columns
            for col, key in enumerate(["Show", "Scene", "Take", "Category", 
                                    "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]):
                item = QTableWidgetItem(metadata.get(key, ""))  # Use get() with default empty string
                self.metadata_table.setItem(row, col + 1, item)  # +1 to account for filename column
            
            # Set the file path in the last column
            file_path_item = QTableWidgetItem(file_path)
            file_path_item.setFlags(file_path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make non-editable
            self.metadata_table.setItem(row, 10, file_path_item)
            
            # Make the filename column non-editable
            filename_item = self.metadata_table.item(row, 0)
            if filename_item:
                filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        
        # Reconnect signals
        self.metadata_table.blockSignals(False)
        
        # Update status message
        if len(self.filtered_rows) == len(self.all_files):
            self.status_label.setText(f"Showing all {len(self.all_files)} files")
        else:
            self.status_label.setText(f"Showing {len(self.filtered_rows)} of {len(self.all_files)} files")
    
    def update_metadata(self, item):
        """Update metadata when a cell is edited."""
        row = item.row()
        col = item.column()
        
        # Get the index in self.all_files
        if 0 <= row < len(self.filtered_rows) and 1 <= col <= 9:  # Skip filename (0) and filepath (10) columns
            # Get the actual index in all_files from the filtered rows list
            actual_row = self.filtered_rows[row]
            file_path, metadata = self.all_files[actual_row]
            
            # Get the new value from the table
            new_value = item.text()
            
            # Map column indices to metadata keys
            metadata_keys = ["Show", "Scene", "Take", "Category", 
                           "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]
            
            # Update our local metadata copy
            key = metadata_keys[col - 1]  # -1 to account for filename column
            metadata[key] = new_value
            self.all_files[actual_row] = (file_path, metadata)
            
            # Mark that changes are pending
            self.changes_pending = True
            self.status_label.setText("Changes pending - press Save to apply")
    
    def save_all_changes(self):
        # Get selected rows, if none are selected, show message
        selected_rows = self.get_selected_actual_rows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select the rows you want to save changes for.")
            return
            
        if not self.changes_pending:
            QMessageBox.information(self, "No Changes", "There are no pending changes to save.")
            return
            
        success_count = 0
        error_count = 0
        
        # Process only selected rows
        for idx in selected_rows:
            file_path, metadata = self.all_files[idx]
            try:
                wav_metadata.write_wav_metadata(file_path, metadata)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"Error updating metadata for {file_path}: {e}")
                
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
    
    def apply_filename_extraction(self, separator, mappings, selected_rows=None):
        """Apply filename extraction to selected files based on dialog settings"""
        count = 0
        
        # If no rows specified, don't process any
        if selected_rows is None or not selected_rows:
            return 0
            
        for i in selected_rows:
            if i >= len(self.all_files):
                continue
                
            file_path, metadata = self.all_files[i]
            filename = os.path.basename(file_path)
            # Remove the extension
            filename = os.path.splitext(filename)[0]
            
            # Print debug info
            print(f"Processing filename: {filename} with separator '{separator}'")
            
            # Split the filename using the separator
            parts = filename.split(separator)
            print(f"  Split into parts: {parts}")
            
            # Check if we have enough parts
            max_pos = max(int(pos) for field, pos in mappings)
            if len(parts) < max_pos:
                print(f"  Not enough parts: have {len(parts)}, need {max_pos}")
                continue
                
            # Extract metadata based on mappings
            updated = False
            for field, pos in mappings:
                try:
                    # Position is 1-based in UI, convert to 0-based for Python
                    idx = int(pos) - 1
                    
                    if idx >= len(parts):
                        print(f"  Index {idx} out of range for parts {parts}")
                        continue
                        
                    value = parts[idx]
                    print(f"  Mapping {field} from part {idx+1}: '{value}'")
                    
                    if field == "Scene" and idx < len(parts):
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
                            # Add to Slate field (preserve existing value if any)
                            existing_slate = metadata.get("Slate", "")
                            if existing_slate:
                                metadata["Slate"] = existing_slate + letter_suffix
                            else:
                                metadata["Slate"] = letter_suffix
                            print(f"  Added letter suffix to Slate: '{metadata['Slate']}'")
                            
                            # Optionally, you could remove the letter from the scene value
                            # scene_part = re.sub(r'[A-Za-z]+$', '', scene_part)
                            
                        metadata[field] = scene_part
                        updated = True
                    
                    elif field == "Subcategory" and idx < len(parts):
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
                self.all_files[i] = (file_path, metadata)
                print(f"  Updated metadata for {filename}")
                
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
    
    # Property for animation (keeping for future use)
    def get_panel_position(self):
        return self.main_splitter.sizes()[1] if len(self.main_splitter.sizes()) > 1 else 0
        
    def set_panel_position(self, value):
        # This method will be called by the animation
        pass
        
    panel_position = pyqtProperty(int, get_panel_position, set_panel_position)

    def set_search_field(self, field):
        """Set the current search field and update the filter"""
        self.current_search_field = field
        self.filter_table()
    
    def show_field_menu(self):
        """Show the dropdown menu for search field selection"""
        # Position the menu below the button
        pos = self.field_selector_button.mapToGlobal(self.field_selector_button.rect().bottomLeft())
        self.field_menu.popup(pos)

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
        """Create an integrated title bar with window controls and app controls in one row"""
        # Create title bar container
        title_bar = QWidget()
        title_bar.setObjectName("title_bar")
        title_bar.setFixedHeight(40) # Slightly taller to fit controls
        title_bar.setStyleSheet("""
            #title_bar {
                background-color: transparent;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
        """)
        
        # Title bar layout
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 0, 8, 0)
        title_layout.setSpacing(10)
        
        # Window control buttons container (at the left)
        window_controls = QWidget()
        window_controls_layout = QHBoxLayout(window_controls)
        window_controls_layout.setContentsMargins(0, 0, 0, 0)
        window_controls_layout.setSpacing(2) # Reduced from 6 to place buttons closer together
        
        # Define window control buttons
        btn_size = 12
        
        # Close button
        btn_close = QPushButton()
        btn_close.setFixedSize(btn_size, btn_size)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #FF5F57;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #FF5F57;
                border: 1px solid #E33E3A;
            }
        """)
        btn_close.clicked.connect(self.close)
        window_controls_layout.addWidget(btn_close)
        
        # Minimize button
        btn_minimize = QPushButton()
        btn_minimize.setFixedSize(btn_size, btn_size)
        btn_minimize.setStyleSheet("""
            QPushButton {
                background-color: #FEBC2E;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #FEBC2E;
                border: 1px solid #E1A116;
            }
        """)
        btn_minimize.clicked.connect(self.showMinimized)
        window_controls_layout.addWidget(btn_minimize)
        
        # Maximize button
        btn_maximize = QPushButton()
        btn_maximize.setFixedSize(btn_size, btn_size)
        btn_maximize.setStyleSheet("""
            QPushButton {
                background-color: #28C941;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #28C941;
                border: 1px solid #1AAB29;
            }
        """)
        btn_maximize.clicked.connect(self.toggleMaximized)
        window_controls_layout.addWidget(btn_maximize)
        
        # Add window controls to title layout
        title_layout.addWidget(window_controls)
        
        # App title - smaller now
        title_label = QLabel("Audio Metadata")
        title_label.setObjectName("title_label")
        title_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #000000;")
        title_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        title_layout.addWidget(title_label)
        
        # Add spacing between title and controls
        title_layout.addSpacing(20)
        
        # Create a control container for search and action buttons
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        
        # Search controls
        search_frame = QFrame()
        search_frame.setFrameShape(QFrame.Shape.StyledPanel)
        search_frame.setFixedHeight(30) # Smaller height
        search_frame.setMinimumWidth(180)
        search_frame.setMaximumWidth(220)
        search_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(245, 236, 220, 0.6);
                border-radius: 6px;
                border: 1px solid rgba(224, 216, 201, 0.7);
            }
        """)
        search_frame_layout = QHBoxLayout(search_frame)
        search_frame_layout.setContentsMargins(8, 0, 8, 0)
        search_frame_layout.setSpacing(0)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                padding: 0;
                font-size: 13px;
                color: #333333;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        self.search_input.textChanged.connect(self.filter_table)
        
        # Add search field to frame
        search_frame_layout.addWidget(self.search_input)
        
        # Down caret button for field selection
        self.field_selector_button = QPushButton()
        self.field_selector_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding: 0;
                margin: 0;
                color: #333333;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
        """)
        
        # Add the SVG caret icon
        caret_svg = """
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M6 9l6 6 6-6" stroke="#333333" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """
        
        # Load the SVG icon for the caret
        caret_pixmap = QPixmap(16, 16)
        caret_pixmap.fill(Qt.GlobalColor.transparent)
        caret_painter = QPainter(caret_pixmap)
        caret_renderer = QSvgRenderer(bytearray(caret_svg, encoding='utf-8'))
        caret_renderer.render(caret_painter)
        caret_painter.end()
        
        self.field_selector_button.setIcon(QIcon(caret_pixmap))
        self.field_selector_button.setFixedSize(24, 24)
        
        # Create dropdown menu for field selection
        self.field_menu = QMenu(self)
        for field in ["All Fields", "Filename", "Show", "Scene", "Take", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]:
            action = self.field_menu.addAction(field)
            action.triggered.connect(lambda checked, f=field: self.set_search_field(f))
        
        # Set default field
        self.current_search_field = "All Fields"
        self.field_selector_button.clicked.connect(self.show_field_menu)
        
        # Add field selector to search frame
        search_frame_layout.addWidget(self.field_selector_button)
        
        # Add search to controls
        controls_layout.addWidget(search_frame)
        
        # Add stretch to push buttons to right
        controls_layout.addStretch(1)
        
        # Buttons container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8) # Reduced spacing
        
        # Browse button with icon (smaller)
        self.browse_button = QPushButton()
        self.browse_button.setProperty("class", "icon-button")
        self.browse_button.setIcon(self.create_folder_icon())
        self.browse_button.setIconSize(QSize(18, 18)) # Smaller icon
        self.browse_button.setToolTip("Browse for audio files")
        self.browse_button.clicked.connect(self.browse_folder)
        self.browse_button.setFixedSize(30, 30) # Smaller button
        button_layout.addWidget(self.browse_button)
        
        # Extract Metadata button - changed to "Extract"
        self.extract_button = QPushButton("Extract")
        self.extract_button.setProperty("class", "action-button")
        self.extract_button.clicked.connect(self.show_extraction_dialog)
        self.extract_button.setFixedHeight(30) # Smaller height
        self.extract_button.setFixedWidth(70) # Smaller width
        button_layout.addWidget(self.extract_button)
        
        # CSV Match button
        self.csv_match_button = QPushButton("CSV Match")
        self.csv_match_button.setProperty("class", "action-button")
        self.csv_match_button.clicked.connect(self.show_csv_match_dialog)
        self.csv_match_button.setFixedHeight(30) # Smaller height
        self.csv_match_button.setFixedWidth(90) # Wider than Extract button
        button_layout.addWidget(self.csv_match_button)
        
        # Save button - changed to "Embed"
        self.save_button = QPushButton("Embed")
        self.save_button.setProperty("class", "action-button primary")
        self.save_button.clicked.connect(self.save_all_changes)
        self.save_button.setFixedHeight(30) # Smaller height
        self.save_button.setFixedWidth(70) # Smaller width
        button_layout.addWidget(self.save_button)
        
        # Add buttons to controls
        controls_layout.addWidget(button_container)
        
        # Sidebar toggle button (smaller)
        self.sidebar_toggle = QPushButton()
        self.sidebar_toggle.setProperty("class", "icon-button")
        self.sidebar_toggle.setToolTip("Toggle Mirror Panel")
        self.sidebar_toggle.clicked.connect(self.toggle_mirror_panel)
        self.sidebar_toggle.setIcon(self.create_sidebar_icon())
        self.sidebar_toggle.setIconSize(QSize(18, 18)) # Smaller icon
        self.sidebar_toggle.setFixedSize(30, 30) # Smaller button
        controls_layout.addWidget(self.sidebar_toggle)
        
        # Add controls to title layout
        title_layout.addWidget(controls_container, 1) # Give stretch factor to center
        
        # Add the integrated title bar to the main layout
        main_layout.insertWidget(0, title_bar)
    
    def show_csv_match_dialog(self):
        """Show dialog to match metadata from CSV file"""
        if not self.all_files:
            QMessageBox.warning(self, "No Files Loaded", "Please load WAV files first.")
            return
            
        wizard = CSVMatchWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            # Get matched characters
            character_matches = wizard.character_matches
            
            # Get field mappings
            field_mappings = wizard.get_field_mappings()
            
            # Get matching columns
            character_column = wizard.character_column
            scene_column = wizard.scene_column
            take_column = wizard.take_column
            
            # Match and update metadata
            updated_count = self.apply_csv_matches(
                wizard.csv_data,
                wizard.csv_headers,
                character_matches,
                character_column,
                scene_column,
                take_column,
                field_mappings
            )
            
            # Update table with matched metadata
            self.update_table()
            self.status_label.setText(f"Updated {updated_count} files with CSV metadata")
            
            # Mark changes as pending
            self.changes_pending = True

    def apply_csv_matches(self, csv_data, csv_headers, character_matches, character_column, scene_column, take_column, field_mappings):
        """Apply CSV matches to audio files
        
        Args:
            csv_data: List of csv rows
            csv_headers: List of csv column headers
            character_matches: Dict mapping audio characters to csv characters
            character_column: CSV column name for character matching
            scene_column: CSV column name for scene matching
            take_column: CSV column name for take matching
            field_mappings: Dict mapping CSV field names to audio metadata fields
        """
        # Get column indices
        char_col_idx = csv_headers.index(character_column)
        scene_col_idx = csv_headers.index(scene_column)
        take_col_idx = csv_headers.index(take_column)
        
        # Create a lookup dictionary for CSV rows by character, scene, and take
        csv_lookup = {}
        for row in csv_data:
            if len(row) <= max(char_col_idx, scene_col_idx, take_col_idx):
                continue
                
            char = row[char_col_idx]
            scene = row[scene_col_idx]
            take = row[take_col_idx]
            
            # Create a lookup key
            key = (char, scene, take)
            csv_lookup[key] = row
        
        # Count of updated files
        updated_count = 0
        
        # Match and update audio file metadata
        for i, (file_path, metadata) in enumerate(self.all_files):
            # Get audio file character, scene, and take
            audio_char = metadata.get("Category", "")
            audio_scene = metadata.get("Scene", "")
            audio_take = metadata.get("Take", "")
            
            # Skip if missing any required field
            if not audio_char or not audio_scene or not audio_take:
                continue
                
            # Skip if character not matched
            if audio_char not in character_matches:
                continue
                
            # Get matched CSV character
            csv_char = character_matches[audio_char]
            
            # Try to find matching CSV row
            key = (csv_char, audio_scene, audio_take)
            if key in csv_lookup:
                # Get the matching CSV row
                csv_row = csv_lookup[key]
                
                # Update metadata with mapped fields
                updated = False
                for csv_field, target_field in field_mappings.items():
                    if csv_field in csv_headers:
                        field_idx = csv_headers.index(csv_field)
                        if field_idx < len(csv_row) and csv_row[field_idx]:
                            # Map CSV field to the specified audio metadata field
                            metadata[target_field] = csv_row[field_idx]
                            updated = True
                
                if updated:
                    # Update the all_files list with the new metadata
                    self.all_files[i] = (file_path, metadata)
                    updated_count += 1
        
        return updated_count


class FilenameExtractorDialog(QDialog):
    """Dialog for configuring filename metadata extraction"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extract Metadata from Filename")
        # Remove fixed size to allow resize and make dialog smaller
        self.resize(480, 380)
        
        # Store the mappings of fields to positions
        self.mappings = []
        self.separator = "_"  # Default separator
        
        # Create a more compact, efficient layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header with explanation - simplified
        header_layout = QHBoxLayout()
        header = QLabel("Extract Metadata")
        header.setStyleSheet("font-size: 16px; font-weight: 500;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Example pattern - more compact
        self.example_label = QLabel("Example: PR2_Allen_Sc5.14D_01 → Show/Category/Scene/Take")
        self.example_label.setStyleSheet("font-style: italic; color: #666; font-size: 12px;")
        layout.addWidget(self.example_label)
        
        # Separator selection - more compact
        separator_layout = QHBoxLayout()
        separator_layout.setSpacing(8)
        
        separator_label = QLabel("Separator:")
        separator_label.setFixedWidth(70)
        separator_layout.addWidget(separator_label)
        
        # Separator input
        self.separator_input = QLineEdit("_")
        self.separator_input.setFixedWidth(40)
        separator_layout.addWidget(self.separator_input)
        
        # Preset button
        preset_button = QPushButton("Use Common Pattern")
        preset_button.setProperty("class", "mac-button")
        preset_button.clicked.connect(self.preset_common_pattern)
        separator_layout.addWidget(preset_button)
        
        separator_layout.addStretch()
        layout.addLayout(separator_layout)
        
        # Mapping rules section heading
        mapping_label = QLabel("Mapping Rules:")
        mapping_label.setStyleSheet("font-weight: 500; margin-top: 8px;")
        layout.addWidget(mapping_label)
        
        # Mapping grid - more efficient layout
        mapping_container = QWidget()
        mapping_grid = QGridLayout(mapping_container)
        mapping_grid.setContentsMargins(0, 0, 0, 0)
        mapping_grid.setSpacing(8)
        mapping_grid.setHorizontalSpacing(10)
        
        # Column headers
        mapping_grid.addWidget(QLabel("Item"), 0, 0)
        mapping_grid.addWidget(QLabel("Position"), 0, 1)
        mapping_grid.addWidget(QLabel("Field"), 0, 2)
        
        # Add mapping rows (up to 5 initially)
        self.mapping_layouts = []
        for i in range(5):
            # Position spinbox
            position = QSpinBox()
            position.setMinimum(1)
            position.setMaximum(10)
            position.setValue(i+1)
            position.setFixedWidth(50)
            
            # Target field dropdown
            target_field = QComboBox()
            target_field.addItems(["Show", "Category", "Subcategory", "Scene", "Take"])
            target_field.setFixedWidth(130)
            
            # Default mapping (will be overridden by preset_common_pattern)
            if i == 0:
                target_field.setCurrentText("Show")
            elif i == 1:
                target_field.setCurrentText("Category")
            elif i == 2:
                target_field.setCurrentText("Scene")
            elif i == 3:
                target_field.setCurrentText("Take")
            elif i == 4:
                target_field.setCurrentText("Subcategory")
            
            # Add to grid layout
            mapping_grid.addWidget(QLabel(f"#{i+1}"), i+1, 0)
            mapping_grid.addWidget(position, i+1, 1)
            mapping_grid.addWidget(target_field, i+1, 2)
            
            self.mapping_layouts.append((position, target_field))
        
        layout.addWidget(mapping_container)
        layout.addStretch()
        
        # Buttons in a nicer layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setFixedWidth(80)
        cancel_button.setProperty("class", "mac-button")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        apply_button = QPushButton("Apply")
        apply_button.setFixedWidth(80)
        apply_button.setProperty("class", "mac-button primary")
        apply_button.setStyleSheet(".mac-button.primary { background-color: #007AFF; color: white; }")
        apply_button.clicked.connect(self.accept)
        button_layout.addWidget(apply_button)
        
        layout.addLayout(button_layout)
    
    def preset_common_pattern(self):
        """Set a preset for the common pattern PR2_Allen_Sc5.14D_01"""
        # Update the example label for clarity
        self.example_label.setText("Example: PR2_Allen_Sc5.14D_01 → Show, Character, Scene (with Sc prefix), Take")
        
        # Set separator
        self.separator_input.setText("_")
        
        # Configure mappings for the standard pattern
        # 1. Show (PR2)
        # 2. Category/Character (Allen)
        # 3. Scene with "Sc" prefix (Sc5.14D) - code will strip the "Sc"
        # 4. Take (01)
        # (Subcategory will be extracted from scene number)
        
        # Set up the mapping controls
        for i, (position, field) in enumerate(self.mapping_layouts):
            if i == 0:
                position.setValue(1)
                field.setCurrentText("Show")
            elif i == 1:
                position.setValue(2)
                field.setCurrentText("Category")
            elif i == 2:
                position.setValue(3)
                field.setCurrentText("Scene")
            elif i == 3:
                position.setValue(4)
                field.setCurrentText("Take")
            elif i == 4:
                # This will be auto-extracted from Scene
                position.setValue(1)  # Doesn't matter - will be extracted from Scene
                field.setCurrentText("Subcategory")

    def accept(self):
        """When user clicks Apply, gather all the settings"""
        self.separator = self.separator_input.text()
        if not self.separator:
            self.separator = "_"  # Default if empty
        
        # Gather the mappings
        self.mappings = []
        for position, target_field in self.mapping_layouts:
            field = target_field.currentText()
            pos = position.value()
            self.mappings.append((field, pos))
        
        super().accept()


class MirrorFilesDialog(QDialog):
    """Dialog for configuring file mirroring options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mirror Files to New Location")
        self.resize(550, 400)
        
        # Initialize variables
        self.destination_dir = ""
        self.organization = []
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Set dialog background to light color
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F5F7;
            }
            QLabel {
                color: #333333;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #E0E0E0;
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
                background-color: white;
                border: 1px solid #E0E0E0;
                color: #333333;
            }
            QPushButton {
                background-color: #E9E9E9;
                color: #333333;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton.primary {
                background-color: #007AFF;
                color: white;
                border: none;
            }
            QPushButton.primary:hover {
                background-color: #0066CC;
            }
            QLineEdit, QSpinBox {
                padding: 5px;
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                background-color: white;
                color: #333333;
            }
            QCheckBox {
                color: #333333;
            }
        """)
        
        # Header with explanation
        header = QLabel("Mirror Files")
        header.setStyleSheet("font-size: 18px; font-weight: 600; color: #333333; margin-bottom: 5px;")
        layout.addWidget(header)
        
        info_label = QLabel("Copy selected files to a new location with organized folder structure.")
        info_label.setStyleSheet("font-style: italic; color: #666666; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Destination directory selection
        dest_group = QGroupBox("Destination Folder")
        dest_layout = QHBoxLayout(dest_group)
        dest_layout.setContentsMargins(12, 12, 12, 12)
        
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Select destination folder...")
        dest_layout.addWidget(self.dest_input)
        
        dest_button = QPushButton("Browse...")
        dest_button.setFixedWidth(100)
        dest_button.clicked.connect(self.browse_destination)
        dest_layout.addWidget(dest_button)
        
        layout.addWidget(dest_group)
        
        # Folder organization section - main content area
        org_group = QGroupBox("Folder Organization")
        org_main_layout = QVBoxLayout(org_group)
        org_main_layout.setContentsMargins(12, 16, 12, 12)
        
        # Explanation for this section
        org_info = QLabel("Select fields to create an organized folder structure. Order determines hierarchy.")
        org_info.setStyleSheet("font-style: italic; color: #666666; font-size: 12px; margin-bottom: 8px;")
        org_main_layout.addWidget(org_info)
        
        # Split into two columns - available fields and selected fields
        org_layout = QHBoxLayout()
        
        # Available fields list
        available_group = QGroupBox("Available Fields")
        available_layout = QVBoxLayout(available_group)
        available_layout.setContentsMargins(10, 20, 10, 10)
        
        self.available_list = QListWidget()
        self.available_list.addItems(["Show", "Scene", "Take", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"])
        self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        available_layout.addWidget(self.available_list)
        
        org_layout.addWidget(available_group)
        
        # Buttons for moving fields between lists
        button_layout = QVBoxLayout()
        button_layout.addStretch()
        
        add_button = QPushButton("→")
        add_button.setFixedSize(40, 30)
        add_button.clicked.connect(self.add_fields)
        button_layout.addWidget(add_button)
        
        remove_button = QPushButton("←")
        remove_button.setFixedSize(40, 30)
        remove_button.clicked.connect(self.remove_fields)
        button_layout.addWidget(remove_button)
        
        button_layout.addSpacing(20)
        
        up_button = QPushButton("↑")
        up_button.setFixedSize(40, 30)
        up_button.clicked.connect(self.move_field_up)
        button_layout.addWidget(up_button)
        
        down_button = QPushButton("↓")
        down_button.setFixedSize(40, 30)
        down_button.clicked.connect(self.move_field_down)
        button_layout.addWidget(down_button)
        
        button_layout.addStretch()
        org_layout.addLayout(button_layout)
        
        # Selected fields list
        selected_group = QGroupBox("Selected Order (Top to Bottom)")
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setContentsMargins(10, 20, 10, 10)
        
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        selected_layout.addWidget(self.selected_list)
        
        org_layout.addWidget(selected_group)
        
        org_main_layout.addLayout(org_layout)
        
        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(10, 20, 10, 10)
        
        self.example_text = QLabel("Select fields to see example folder structure")
        self.example_text.setStyleSheet("font-family: monospace; color: #333333; background-color: #EAEAEA; padding: 8px; border-radius: 4px;")
        self.example_text.setWordWrap(True)
        preview_layout.addWidget(self.example_text)
        
        org_main_layout.addWidget(preview_group)
        
        # Options
        options_layout = QHBoxLayout()
        
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        self.overwrite_checkbox.setStyleSheet("color: #333333;")
        options_layout.addWidget(self.overwrite_checkbox)
        
        org_main_layout.addLayout(options_layout)
        
        layout.addWidget(org_group)
        
        # Connect signals for preview updates
        self.selected_list.model().rowsInserted.connect(self.update_preview)
        self.selected_list.model().rowsRemoved.connect(self.update_preview)
        self.selected_list.model().layoutChanged.connect(self.update_preview)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setFixedWidth(90)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        mirror_button = QPushButton("Mirror")
        mirror_button.setFixedWidth(90)
        mirror_button.setProperty("class", "primary")
        mirror_button.clicked.connect(self.accept)
        button_layout.addWidget(mirror_button)
        
        layout.addLayout(button_layout)
    
    def browse_destination(self):
        """Browse for destination directory"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder_path:
            self.dest_input.setText(folder_path)
            self.destination_dir = folder_path
    
    def add_fields(self):
        """Add selected fields from available to selected"""
        for item in self.available_list.selectedItems():
            # Create a new item to add to selected list
            new_item = item.text()
            self.selected_list.addItem(new_item)
            
            # Remove from available list
            self.available_list.takeItem(self.available_list.row(item))
    
    def remove_fields(self):
        """Remove selected fields from selected to available"""
        for item in self.selected_list.selectedItems():
            # Create a new item to add back to available list
            new_item = item.text()
            self.available_list.addItem(new_item)
            
            # Remove from selected list
            self.selected_list.takeItem(self.selected_list.row(item))
    
    def move_field_up(self):
        """Move selected field up in the list"""
        current_row = self.selected_list.currentRow()
        if current_row > 0:
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row - 1, current_item)
            self.selected_list.setCurrentRow(current_row - 1)
    
    def move_field_down(self):
        """Move selected field down in the list"""
        current_row = self.selected_list.currentRow()
        if current_row < self.selected_list.count() - 1:
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row + 1, current_item)
            self.selected_list.setCurrentRow(current_row + 1)
    
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
        
        self.example_text.setText(example)
    
    def accept(self):
        """When user clicks Mirror, gather all the settings"""
        self.destination_dir = self.dest_input.text()
        if not self.destination_dir:
            QMessageBox.warning(self, "No Destination", "Please select a destination folder.")
            return
            
        # Gather the selected fields in order
        self.organization = []
        for i in range(self.selected_list.count()):
            self.organization.append(self.selected_list.item(i).text())
            
        if not self.organization:
            QMessageBox.warning(self, "No Organization", "Please select at least one field for folder organization.")
            return
            
        overwrite = self.overwrite_checkbox.isChecked()
        
        # Call the parent's mirror method
        self.parent.mirror_files(self.selected_rows, self.destination_dir, self.organization, overwrite)


class MirrorPanel(QWidget):
    """Side panel for configuring and executing file mirroring options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.selected_rows = []
        self.destination_dir = ""
        self.organization = []
        
        # Set the object name for styling
        self.setObjectName("MirrorPanel")
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create content widget to hold all panel elements
        content_widget = QWidget()
        content_widget.setObjectName("MirrorPanelContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        # Set panel styling
        self.setStyleSheet("""
            QWidget#MirrorPanel {
                background-color: rgba(245, 236, 220, 0.75);
                border-left: 1px solid rgba(224, 216, 201, 0.7);
            }
            QWidget#MirrorPanelContent {
                background-color: rgba(245, 236, 220, 0.5);
            }
            QLabel {
                color: #333333;
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
                min-height: 80px;
            }
            QListWidget::item {
                color: #333333;
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: rgba(232, 223, 208, 0.7);
                color: #333333;
            }
            QPushButton {
                background-color: rgba(245, 236, 220, 0.6);
                color: #333333;
                border: 1px solid rgba(224, 216, 201, 0.7);
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(232, 223, 208, 0.8);
            }
            QPushButton.primary {
                background-color: rgba(196, 181, 159, 0.85);
                color: white;
                border: none;
            }
            QPushButton.primary:hover {
                background-color: rgba(181, 167, 144, 0.95);
            }
            QLineEdit, QSpinBox {
                padding: 5px;
                border: 1px solid rgba(224, 216, 201, 0.7);
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.8);
                color: #333333;
            }
            QCheckBox {
                color: #333333;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QSplitter::handle {
                background-color: rgba(224, 216, 201, 0.5);
                height: 1px;
            }
            QFrame[frameShape="4"] {  /* HLine */
                background-color: rgba(224, 216, 201, 0.5);
                max-height: 1px;
            }
            
            /* QScrollBar styling */
            QScrollBar:vertical {
                border: none;
                background: rgba(245, 236, 220, 0.3);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            
            QScrollBar::handle:vertical {
                background: rgba(196, 181, 159, 0.7);
                min-height: 20px;
                border-radius: 4px;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            
            QScrollBar:horizontal {
                border: none;
                background: rgba(245, 236, 220, 0.3);
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            
            QScrollBar::handle:horizontal {
                background: rgba(196, 181, 159, 0.7);
                min-width: 20px;
                border-radius: 4px;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
                width: 0px;
            }
        """)
        
        # Header section
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        header = QLabel("Mirror Files")
        header.setStyleSheet("font-size: 18px; font-weight: 600; color: #333333; margin-bottom: 5px;")
        header_layout.addWidget(header)
        
        info_label = QLabel("Copy selected files to a new location with organized folder structure.")
        info_label.setStyleSheet("font-style: italic; color: #666666; font-size: 13px; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        header_layout.addWidget(info_label)
        
        # File count label
        self.file_count_label = QLabel("No files selected. Select files in the main panel.")
        self.file_count_label.setStyleSheet("color: #FF3B30; font-weight: bold; font-style: italic;")
        header_layout.addWidget(self.file_count_label)
        
        content_layout.addWidget(header_container)
        
        # Destination directory selection - simplified
        dest_container = QWidget()
        dest_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        dest_layout = QVBoxLayout(dest_container)
        dest_layout.setContentsMargins(0, 0, 0, 0)
        dest_layout.setSpacing(8)
        
        dest_label = QLabel("Destination Folder:")
        dest_label.setStyleSheet("font-weight: bold; color: #333333;")
        dest_layout.addWidget(dest_label)
        
        dest_input_layout = QHBoxLayout()
        dest_input_layout.setContentsMargins(0, 0, 0, 0)
        dest_input_layout.setSpacing(8)
        
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Select destination folder...")
        dest_input_layout.addWidget(self.dest_input)
        
        dest_button = QPushButton("Browse...")
        dest_button.setMaximumWidth(80)
        dest_button.clicked.connect(self.browse_destination)
        dest_input_layout.addWidget(dest_button)
        
        dest_layout.addLayout(dest_input_layout)
        content_layout.addWidget(dest_container)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator)
        
        # QCODE Take Review section - simplified
        qcode_container = QWidget()
        qcode_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        qcode_layout = QVBoxLayout(qcode_container)
        qcode_layout.setContentsMargins(0, 0, 0, 0)
        qcode_layout.setSpacing(8)
        
        qcode_label = QLabel("QCODE Take Review")
        qcode_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333333;")
        qcode_layout.addWidget(qcode_label)
        
        qcode_info = QLabel("Mirror files in QCODE Take Review format with two copies:\n1. By Episode/Character/Episode/Scene\n2. Day X/Character")
        qcode_info.setStyleSheet("font-style: italic; color: #666666; font-size: 12px;")
        qcode_info.setWordWrap(True)
        qcode_layout.addWidget(qcode_info)
        
        # Day number input
        day_layout = QHBoxLayout()
        day_layout.setContentsMargins(0, 0, 0, 0)
        
        day_label = QLabel("Day Number:")
        day_label.setStyleSheet("color: #333333;")
        day_label.setFixedWidth(100)
        day_layout.addWidget(day_label)
        
        self.day_spinner = QSpinBox()
        self.day_spinner.setMinimum(1)
        self.day_spinner.setMaximum(99)
        self.day_spinner.setValue(1)
        day_layout.addWidget(self.day_spinner)
        day_layout.addStretch()
        
        qcode_layout.addLayout(day_layout)
        
        # QCODE mirror button
        qcode_mirror_button = QPushButton("Mirror for QCODE Take Review")
        qcode_mirror_button.setProperty("class", "primary")
        qcode_mirror_button.clicked.connect(self.mirror_for_qcode)
        qcode_layout.addWidget(qcode_mirror_button)
        
        content_layout.addWidget(qcode_container)
        
        # Add separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(separator2)
        
        # Custom folder organization section - with splitter
        custom_org_container = QWidget()
        custom_org_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        custom_org_layout = QVBoxLayout(custom_org_container)
        custom_org_layout.setContentsMargins(0, 0, 0, 0)
        custom_org_layout.setSpacing(8)
        
        custom_org_label = QLabel("Custom Folder Organization")
        custom_org_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333333;")
        custom_org_layout.addWidget(custom_org_label)
        
        org_info = QLabel("Select fields to create an organized folder structure. Order determines hierarchy.")
        org_info.setStyleSheet("font-style: italic; color: #666666; font-size: 12px;")
        org_info.setWordWrap(True)
        custom_org_layout.addWidget(org_info)
        
        # Create splitter for field lists
        field_splitter = QSplitter(Qt.Orientation.Horizontal)
        field_splitter.setChildrenCollapsible(False)
        
        # Available fields container
        available_container = QWidget()
        available_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        available_layout = QVBoxLayout(available_container)
        available_layout.setContentsMargins(0, 0, 0, 0)
        available_layout.setSpacing(4)
        
        available_label = QLabel("Available Fields")
        available_label.setStyleSheet("font-weight: bold; color: #333333;")
        available_layout.addWidget(available_label)
        
        self.available_list = QListWidget()
        self.available_list.addItems(["Show", "Scene", "Take", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"])
        self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.available_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        available_layout.addWidget(self.available_list)
        
        field_splitter.addWidget(available_container)
        
        # Buttons container - vertical in center
        buttons_container = QWidget()
        buttons_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        buttons_container.setFixedWidth(40)
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(4, 0, 4, 0)
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()
        
        add_button = QPushButton("→")
        add_button.setFixedSize(32, 32)
        add_button.clicked.connect(self.add_fields)
        buttons_layout.addWidget(add_button)
        
        remove_button = QPushButton("←")
        remove_button.setFixedSize(32, 32)
        remove_button.clicked.connect(self.remove_fields)
        buttons_layout.addWidget(remove_button)
        
        buttons_layout.addSpacing(20)
        
        up_button = QPushButton("↑")
        up_button.setFixedSize(32, 32)
        up_button.clicked.connect(self.move_field_up)
        buttons_layout.addWidget(up_button)
        
        down_button = QPushButton("↓")
        down_button.setFixedSize(32, 32)
        down_button.clicked.connect(self.move_field_down)
        buttons_layout.addWidget(down_button)
        
        buttons_layout.addStretch()
        
        field_splitter.addWidget(buttons_container)
        
        # Selected fields container
        selected_container = QWidget()
        selected_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        selected_layout = QVBoxLayout(selected_container)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        selected_layout.setSpacing(4)
        
        selected_label = QLabel("Selected Order")
        selected_label.setStyleSheet("font-weight: bold; color: #333333;")
        selected_layout.addWidget(selected_label)
        
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.selected_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        selected_layout.addWidget(self.selected_list)
        
        field_splitter.addWidget(selected_container)
        
        # Set splitter sizes equally
        field_splitter.setSizes([100, 40, 100])
        
        custom_org_layout.addWidget(field_splitter, 1)  # Give this section more stretch
        
        # Preview section - simplified
        preview_container = QWidget()
        preview_container.setStyleSheet("background-color: rgba(245, 236, 220, 0.5);")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 8, 0, 0)
        preview_layout.setSpacing(4)
        
        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("font-weight: bold; color: #333333;")
        preview_layout.addWidget(preview_label)
        
        self.example_text = QLabel("Select fields to see example folder structure")
        self.example_text.setStyleSheet("font-family: monospace; color: #333333; background-color: rgba(229, 220, 200, 0.7); padding: 8px; border-radius: 4px;")
        self.example_text.setWordWrap(True)
        self.example_text.setMinimumHeight(60)
        preview_layout.addWidget(self.example_text)
        
        custom_org_layout.addWidget(preview_container)
        
        # Options and mirror button - at bottom
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 4, 0, 0)
        
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        self.overwrite_checkbox.setStyleSheet("color: #333333;")
        options_layout.addWidget(self.overwrite_checkbox)
        options_layout.addStretch()
        
        custom_org_layout.addLayout(options_layout)
        
        custom_mirror_button = QPushButton("Mirror with Custom Organization")
        custom_mirror_button.clicked.connect(self.mirror_with_custom_org)
        custom_org_layout.addWidget(custom_mirror_button)
        
        content_layout.addWidget(custom_org_container, 1)  # Give more stretch to this section
        
        # Add content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Connect signals for preview updates
        self.selected_list.model().rowsInserted.connect(self.update_preview)
        self.selected_list.model().rowsRemoved.connect(self.update_preview)
        self.selected_list.model().layoutChanged.connect(self.update_preview)
    
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
        selected_rows = self.get_selected_rows_from_parent()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select files in the main panel to mirror.")
            return
            
        dest_dir = self.dest_input.text()
        if not dest_dir:
            QMessageBox.warning(self, "No Destination", "Please select a destination folder.")
            return
            
        day_number = self.day_spinner.value()
        overwrite = self.overwrite_checkbox.isChecked()
        
        # Call the parent's mirror method
        self.parent.mirror_files_qcode_take_review(selected_rows, dest_dir, day_number, overwrite)
    
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
        for item in self.available_list.selectedItems():
            # Create a new item to add to selected list
            new_item = item.text()
            self.selected_list.addItem(new_item)
            
            # Remove from available list
            self.available_list.takeItem(self.available_list.row(item))
    
    def remove_fields(self):
        """Remove selected fields from selected to available"""
        for item in self.selected_list.selectedItems():
            # Create a new item to add back to available list
            new_item = item.text()
            self.available_list.addItem(new_item)
            
            # Remove from selected list
            self.selected_list.takeItem(self.selected_list.row(item))
    
    def move_field_up(self):
        """Move selected field up in the list"""
        current_row = self.selected_list.currentRow()
        if current_row > 0:
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row - 1, current_item)
            self.selected_list.setCurrentRow(current_row - 1)
    
    def move_field_down(self):
        """Move selected field down in the list"""
        current_row = self.selected_list.currentRow()
        if current_row < self.selected_list.count() - 1:
            current_item = self.selected_list.takeItem(current_row)
            self.selected_list.insertItem(current_row + 1, current_item)
            self.selected_list.setCurrentRow(current_row + 1)
    
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
            
            # Match characters progressively
            for audio_char in audio_characters:
                if audio_char not in self.character_matches:
                    # Try exact match first (case-insensitive)
                    exact_match = next((c for c in csv_characters if c.lower() == audio_char.lower()), None)
                    if exact_match:
                        self.character_matches[audio_char] = exact_match
                        continue
                    
                    # Split audio character into words
                    audio_words = audio_char.lower().split()
                    
                    # If no exact match, try progressive word matching
                    if audio_words:
                        # Initialize candidates with all CSV characters
                        candidates = list(csv_characters)
                        
                        # Track best match and score
                        best_match = None
                        best_score = -1
                        
                        # Score each CSV character
                        for csv_char in candidates:
                            csv_words = csv_char.lower().split()
                            
                            # Calculate match score
                            score = 0
                            
                            # First check first word matches
                            if csv_words and audio_words and csv_words[0] == audio_words[0]:
                                score += 10  # High score for first word match
                                
                                # Check second word if available
                                if len(csv_words) > 1 and len(audio_words) > 1 and csv_words[1] == audio_words[1]:
                                    score += 5  # Additional score for second word match
                                    
                                    # Check third word if available
                                    if len(csv_words) > 2 and len(audio_words) > 2 and csv_words[2] == audio_words[2]:
                                        score += 3  # Additional score for third word match
                            
                            # Also check if first word of one is contained in the other
                            elif csv_words and audio_words:
                                if csv_words[0] in audio_words[0] or audio_words[0] in csv_words[0]:
                                    score += 3  # Partial match on first word
                            
                            # Check for first part of camelCase name
                            if not score and len(audio_char) > 1:
                                # Find first capital letter after the first character
                                camel_split_pos = 1
                                for i in range(1, len(audio_char)):
                                    if audio_char[i].isupper():
                                        camel_split_pos = i
                                        break
                                
                                # Get first part of the camelCase name
                                first_part = audio_char[:camel_split_pos].lower()
                                
                                # Check if first part matches or is contained in csv_char
                                if any(first_part in word.lower() for word in csv_words) or any(word.lower() in first_part for word in csv_words):
                                    score += 2  # Some match with camelCase first part
                            
                            # Update best match if this score is higher
                            if score > best_score:
                                best_score = score
                                best_match = csv_char
                        
                        # If we found a match with a score, use it
                        if best_match and best_score > 0:
                            self.character_matches[audio_char] = best_match
            
            # Update the lists
            self.update_matches_list()
            self.update_character_lists()
        except Exception as e:
            print(f"Error auto-matching characters: {e}")
            
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
                
            # Check if character column is detected
            if not self.character_column:
                QMessageBox.warning(self, "Missing Column", "Could not detect a character column in the CSV file.")
                return False
                
            # Check if scene column is detected
            if not self.scene_column:
                QMessageBox.warning(self, "Missing Column", "Could not detect a scene column in the CSV file.")
                return False
                
            # Check if take column is detected
            if not self.take_column:
                QMessageBox.warning(self, "Missing Column", "Could not detect a take column in the CSV file.")
                return False
                
            # Check if any characters are matched
            if not self.character_matches:
                QMessageBox.warning(self, "No Matches", "Please match at least one character before continuing.")
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
    
    def browse_csv_file(self):
        """Browse for a CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        self.csv_file_path = file_path
        self.csv_file_input.setText(file_path)
        
        # Load CSV data
        self.load_csv_data()
    
    def on_audio_char_double_clicked(self, item):
        """Handle double-click on audio character item"""
        audio_char = item.text()
        
        # Find first unmatched CSV character to match with
        for i in range(self.csv_char_list.count()):
            csv_item = self.csv_char_list.item(i)
            if csv_item:
                csv_char = csv_item.text()
                self.character_matches[audio_char] = csv_char
                self.update_matches_list()
                self.update_character_lists()
                break
    
    def on_csv_char_double_clicked(self, item):
        """Handle double-click on CSV character item"""
        csv_char = item.text()
        
        # Find first unmatched audio character to match with
        for i in range(self.audio_char_list.count()):
            audio_item = self.audio_char_list.item(i)
            if audio_item:
                audio_char = audio_item.text()
                self.character_matches[audio_char] = csv_char
                self.update_matches_list()
                self.update_character_lists()
                break
    
    def on_match_double_clicked(self, item):
        """Handle double-click on a match item to unmatch it"""
        match_text = item.text()
        audio_char = match_text.split(" → ")[0]
        
        # Remove the match
        if audio_char in self.character_matches:
            del self.character_matches[audio_char]
        
        # Update lists
        self.update_matches_list()
        self.update_character_lists()

    def update_csv_character_list(self):
        """Update the list of characters from the CSV file, showing only unmatched ones"""
        if not self.csv_data or not self.character_column:
            return
            
        try:
            # Get the index of the character column
            char_col_idx = self.csv_headers.index(self.character_column)
            
            # Get unique character names from CSV
            csv_characters = set()
            for row in self.csv_data:
                if char_col_idx < len(row) and row[char_col_idx]:
                    csv_characters.add(row[char_col_idx])
            
            # Get characters that are already matched
            matched_csv_chars = set(self.character_matches.values())
            
            # Get unmatched characters
            unmatched_csv_chars = csv_characters - matched_csv_chars
            
            # Update the CSV character list
            self.csv_char_list.clear()
            for character in sorted(unmatched_csv_chars):
                self.csv_char_list.addItem(character)
        except Exception as e:
            print(f"Error updating CSV character list: {e}")
    
    def update_audio_character_list(self):
        """Update the list of characters from audio files, showing only unmatched ones"""
        if not hasattr(self.parent, 'all_files') or not self.parent.all_files:
            return
            
        try:
            # Get unique character names (Category field) from audio files
            audio_characters = set()
            for file_path, metadata in self.parent.all_files:
                character = metadata.get("Category", "")
                if character:
                    audio_characters.add(character)
            
            # Get characters that are already matched
            matched_audio_chars = set(self.character_matches.keys())
            
            # Get unmatched characters
            unmatched_audio_chars = audio_characters - matched_audio_chars
            
            # Update the audio character list
            self.audio_char_list.clear()
            for character in sorted(unmatched_audio_chars):
                self.audio_char_list.addItem(character)
        except Exception as e:
            print(f"Error updating audio character list: {e}")
            
    def update_character_lists(self):
        """Update both character lists to reflect current matches"""
        self.update_audio_character_list()
        self.update_csv_character_list()

    def match_selected_characters(self):
        """Match the selected characters from both lists"""
        audio_item = self.audio_char_list.currentItem()
        csv_item = self.csv_char_list.currentItem()
        
        if audio_item and csv_item:
            audio_char = audio_item.text()
            csv_char = csv_item.text()
            
            # Create the match
            self.character_matches[audio_char] = csv_char
            
            # Update the lists
            self.update_matches_list()
            self.update_character_lists()
    
    def unmatch_selected_character(self):
        """Remove the selected match"""
        match_item = self.matches_list.currentItem()
        if match_item:
            match_text = match_item.text()
            audio_char = match_text.split(" → ")[0]
            
            # Remove the match
            if audio_char in self.character_matches:
                del self.character_matches[audio_char]
            
            # Update the lists
            self.update_matches_list()
            self.update_character_lists()
    
    def update_matches_list(self):
        """Update the list of matched character pairs"""
        self.matches_list.clear()
        # Sort matches alphabetically by audio character name
        sorted_matches = sorted(self.character_matches.items(), key=lambda x: x[0])
        for audio_char, csv_char in sorted_matches:
            self.matches_list.addItem(f"{audio_char} → {csv_char}")
    
    def create_entry_match_page(self):
        """Create the entry matching page (Step 2)"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Entry matching explanation
        info_label = QLabel("Review and confirm the matches between audio files and CSV entries.")
        info_label.setStyleSheet("font-style: italic; color: #666666; font-size: 13px; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Matches found summary
        self.match_summary_label = QLabel("Matching 0 audio files with CSV entries based on character, scene, and take.")
        self.match_summary_label.setStyleSheet("font-weight: bold; margin: 10px 0;")
        layout.addWidget(self.match_summary_label)
        
        # Preview of matches table
        matches_table_group = QGroupBox("Matched Entries")
        matches_table_layout = QVBoxLayout(matches_table_group)
        
        # Simplified table with just filename and matching CSV data
        self.matches_table = QTableWidget(0, 4)  # 4 columns: Filename, CSV Character, CSV Scene, CSV Take
        self.matches_table.setHorizontalHeaderLabels([
            "Audio Filename", "CSV Character", "CSV Scene", "CSV Take"
        ])
        self.matches_table.setAlternatingRowColors(True)
        self.matches_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.matches_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Read-only
        self.matches_table.setStyleSheet("QTableWidget { color: black; } QTableWidgetItem { color: black; }")
        
        # Set up the table columns
        header = self.matches_table.horizontalHeader()
        for col in range(self.matches_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        
        # Set minimum size for columns
        header.setMinimumSectionSize(100)
        
        matches_table_layout.addWidget(self.matches_table)
        layout.addWidget(matches_table_group, 1)  # 1 = stretch factor
        
        # Options section
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        # Option to ignore unmatched files
        self.ignore_unmatched_cb = QCheckBox("Ignore unmatched files")
        self.ignore_unmatched_cb.setChecked(True)
        options_layout.addWidget(self.ignore_unmatched_cb)
        
        layout.addWidget(options_group)
        
        return page

    def prepare_entry_matches(self):
        """Prepare the entry matches table"""
        # Clear existing data
        self.matches_table.setRowCount(0)
        
        # Check if character_matches is populated
        if not hasattr(self, 'character_matches') or not self.character_matches:
            self.match_summary_label.setText("No character matches defined. Please go back to step 1.")
            return
        
        # Get all audio files with their metadata
        audio_files = self.parent().all_files
        
        # Collect audio files by character
        character_audio_files = {}
        for file_path, metadata in audio_files:
            character = metadata.get("Category", "")
            if character in self.character_matches:
                if character not in character_audio_files:
                    character_audio_files[character] = []
                character_audio_files[character].append((file_path, metadata))
        
        # Prepare to count matches
        total_matches = 0
        
        # Process CSV data for each matched character
        for audio_character, csv_character in self.character_matches.items():
            # Find rows in CSV for this character
            csv_rows = [row for row in self.csv_data if row[self.character_column] == csv_character]
            
            # Get audio files for this character
            if audio_character not in character_audio_files:
                continue
                
            audio_files_for_character = character_audio_files[audio_character]
            
            # Match each audio file with CSV entries
            for file_path, metadata in audio_files_for_character:
                # Extract scene and take from audio metadata
                audio_scene = metadata.get("Scene", "")
                audio_take = metadata.get("Take", "")
                filename = os.path.basename(file_path)
                
                # Find matching CSV rows
                matching_rows = []
                
                # Handle flexible scene matching (e.g., "5.1" should match "5.01")
                for row in csv_rows:
                    csv_scene = row[self.scene_column]
                    csv_take = row[self.take_column]
                    
                    # Flexible scene comparison
                    scene_match = False
                    
                    # If scene contains a period, compare parts
                    if "." in audio_scene and "." in csv_scene:
                        # Split into major and minor parts
                        audio_parts = audio_scene.split(".")
                        csv_parts = csv_scene.split(".")
                        
                        if len(audio_parts) >= 2 and len(csv_parts) >= 2:
                            # Try to convert to integers for numerical comparison
                            try:
                                # Compare major part (episode/scene number)
                                audio_major = int(audio_parts[0])
                                csv_major = int(csv_parts[0])
                                
                                # Compare minor part (scene version/number)
                                # Remove any trailing letters
                                audio_minor_str = re.sub(r'[A-Za-z]+$', '', audio_parts[1])
                                csv_minor_str = re.sub(r'[A-Za-z]+$', '', csv_parts[1])
                                
                                # Convert to float or int
                                audio_minor = float(audio_minor_str) if "." in audio_minor_str else int(audio_minor_str)
                                csv_minor = float(csv_minor_str) if "." in csv_minor_str else int(csv_minor_str)
                                
                                # Check if both parts match
                                if audio_major == csv_major and audio_minor == csv_minor:
                                    scene_match = True
                            except (ValueError, IndexError):
                                # If conversion fails, fall back to string comparison
                                scene_match = audio_scene == csv_scene
                    else:
                        # Simple string comparison
                        scene_match = audio_scene == csv_scene
                    
                    # Flexible take comparison
                    take_match = False
                    
                    # Try to convert takes to integers for comparison
                    try:
                        # Remove any non-numeric characters
                        audio_take_num = int(re.sub(r'[^0-9]', '', audio_take))
                        csv_take_num = int(re.sub(r'[^0-9]', '', csv_take))
                        take_match = audio_take_num == csv_take_num
                    except (ValueError, TypeError):
                        # Fall back to string comparison if conversion fails
                        take_match = audio_take == csv_take
                    
                    # Both scene and take must match
                    if scene_match and take_match:
                        matching_rows.append(row)
                
                # Add to matches table
                for row in matching_rows:
                    table_row = self.matches_table.rowCount()
                    self.matches_table.insertRow(table_row)
                    
                    # Add the simplified data to the table: filename, character, scene, take
                    self.matches_table.setItem(table_row, 0, QTableWidgetItem(filename))
                    self.matches_table.setItem(table_row, 1, QTableWidgetItem(row[self.character_column]))
                    self.matches_table.setItem(table_row, 2, QTableWidgetItem(row[self.scene_column]))
                    self.matches_table.setItem(table_row, 3, QTableWidgetItem(row[self.take_column]))
                    
                    # Make sure all items have black text for better readability
                    for col in range(4):
                        item = self.matches_table.item(table_row, col)
                        if item:
                            item.setForeground(QBrush(QColor(0, 0, 0)))
                            
                    total_matches += 1
        
        # Update the summary label
        self.match_summary_label.setText(f"Found {total_matches} matches between audio files and CSV entries.")
        
        # Resize columns to content
        self.matches_table.resizeColumnsToContents()
    
    def validate_current_step(self):
        """Validate the current step before allowing to proceed"""
        print(f"Validating step {self.current_step}")
        
        if self.current_step == 0:  # Character matching
            # Check if CSV file is loaded
            if not self.csv_data:
                QMessageBox.warning(self, "No CSV File", "Please select a CSV file first.")
                print("No CSV file loaded")
                return False
                
            # Check if character column is detected
            if not self.character_column:
                QMessageBox.warning(self, "Missing Column", "Could not detect a character column in the CSV file.")
                print("No character column detected")
                return False
                
            # Check if scene column is detected
            if not self.scene_column:
                QMessageBox.warning(self, "Missing Column", "Could not detect a scene column in the CSV file.")
                print("No scene column detected")
                return False
                
            # Check if take column is detected
            if not self.take_column:
                QMessageBox.warning(self, "Missing Column", "Could not detect a take column in the CSV file.")
                print("No take column detected")
                return False
                
            # Check if any characters are matched
            if not self.character_matches:
                QMessageBox.warning(self, "No Matches", "Please match at least one character before continuing.")
                print("No character matches found")
                return False
                
        print("Validation passed")
        # All validations passed
        return True
    
    def setup_field_mappings(self):
        """Set up the field mappings UI for step 3"""
        # Clear existing mappings
        for i in reversed(range(1, self.mapping_layout.rowCount())):
            for j in range(self.mapping_layout.columnCount()):
                item = self.mapping_layout.itemAtPosition(i, j)
                if item and item.widget():
                    item.widget().deleteLater()
                    
        self.field_mappings_controls = []
        
        # Start with blank row to give some space
        blank_row = 1
        self.mapping_layout.addWidget(QWidget(), blank_row, 0)
        
        # Add field mapping rows
        row = blank_row + 1
        
        # Filter out special fields
        skip_fields = ["Show", "Scene", "Take", "Category"]
        
        # Only show fields in CSV that haven't been matched to key fields
        for i, header in enumerate(self.csv_headers):
            # Skip if it's one of the special fields we already matched
            if header == self.character_column or header == self.scene_column or header == self.take_column:
                continue
                
            # Add CSV field label
            self.mapping_layout.addWidget(QLabel(header), row, 0)
            
            # Add arrow
            self.mapping_layout.addWidget(QLabel("→"), row, 1)
            
            # Add target field combo box
            target_combo = QComboBox()
            # Add all audio metadata fields except those we already mapped
            for field in ["Show", "Scene", "Take", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]:
                if field not in skip_fields:
                    target_combo.addItem(field)
                    
            # Try to auto-select the field based on name similarity
            header_lower = header.lower()
            best_match_idx = 0
            best_match_score = 0
            
            for idx in range(target_combo.count()):
                field = target_combo.itemText(idx).lower()
                # Simple string similarity check
                if header_lower in field or field in header_lower:
                    # Perfect match
                    target_combo.setCurrentIndex(idx)
                    break
                # Partial match
                score = 0
                for word in header_lower.split():
                    if word in field:
                        score += 1
                for word in field.split():
                    if word in header_lower:
                        score += 1
                if score > best_match_score:
                    best_match_score = score
                    best_match_idx = idx
            
            # If no perfect match but we found partial matches, use the best one
            if best_match_score > 0:
                target_combo.setCurrentIndex(best_match_idx)
                
            self.mapping_layout.addWidget(target_combo, row, 2)
            
            # Add include checkbox
            include_cb = QCheckBox()
            include_cb.setChecked(True)  # Default to checked
            self.mapping_layout.addWidget(include_cb, row, 3)
            
            # Store controls for later access
            self.field_mappings_controls.append((header, target_combo, include_cb))
            
            row += 1
                
        # Add a stretch at the end to push everything to the top
        self.mapping_layout.setRowStretch(row, 1)
    
    def select_all_fields(self):
        """Select all fields for import"""
        for _, _, checkbox in self.field_mappings_controls:
            checkbox.setChecked(True)
    
    def select_no_fields(self):
        """Deselect all fields for import"""
        for _, _, checkbox in self.field_mappings_controls:
            checkbox.setChecked(False)
    
    def get_field_mappings(self):
        """Get the field mappings defined by the user"""
        mappings = {}
        for csv_field, target_combo, include_checkbox in self.field_mappings_controls:
            if include_checkbox.isChecked():
                target_field = target_combo.currentText()
                mappings[csv_field] = target_field
        return mappings
    
    def accept(self):
        """When user clicks Finish"""
        # Check if any fields are selected for import
        mappings = self.get_field_mappings()
        if not mappings:
            QMessageBox.warning(self, "No Fields", "Please select at least one field to import.")
            return
            
        super().accept()

    def create_field_mapping_page(self):
        """Create the field mapping page (Step 3)"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Explanation text
        mapping_info = QLabel("Specify how CSV fields should map to audio metadata fields.")
        mapping_info.setStyleSheet("font-style: italic; color: #666666; font-size: 13px;")
        mapping_info.setWordWrap(True)
        layout.addWidget(mapping_info)
        
        # Field mapping group
        field_mapping_group = QGroupBox("Field Mapping")
        field_mapping_layout = QVBoxLayout(field_mapping_group)
        
        # Scroll area for field mappings (in case there are many)
        mapping_scroll = QScrollArea()
        mapping_scroll.setWidgetResizable(True)
        mapping_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container widget for the mappings
        self.mapping_container = QWidget()
        self.mapping_layout = QGridLayout(self.mapping_container)
        self.mapping_layout.setContentsMargins(0, 0, 0, 0)
        self.mapping_layout.setSpacing(8)
        
        # Add headers for the grid
        self.mapping_layout.addWidget(QLabel("CSV Field"), 0, 0)
        self.mapping_layout.addWidget(QLabel("→"), 0, 1)
        self.mapping_layout.addWidget(QLabel("Audio Metadata Field"), 0, 2)
        self.mapping_layout.addWidget(QLabel("Include"), 0, 3)
        
        # Set the container as the scroll area's widget
        mapping_scroll.setWidget(self.mapping_container)
        field_mapping_layout.addWidget(mapping_scroll)
        
        # Quick selection buttons
        selection_layout = QHBoxLayout()
        
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self.select_all_fields)
        selection_layout.addWidget(select_all_button)
        
        select_none_button = QPushButton("Select None")
        select_none_button.clicked.connect(self.select_no_fields)
        selection_layout.addWidget(select_none_button)
        
        selection_layout.addStretch()
        
        field_mapping_layout.addLayout(selection_layout)
        layout.addWidget(field_mapping_group, 1)  # 1 = stretch factor
        
        # Store field mapping controls for later access
        self.field_mappings_controls = []  # Will hold tuples of (csv_field, target_combo, include_checkbox)
        
        return page
     
    def go_back(self):
        """Go to previous step"""
        if self.current_step > 0:
            self.current_step -= 1
            self.stack.setCurrentIndex(self.current_step)
            self.update_step_display()
    
    def go_next(self):
        """Go to next step"""
        # Validate current step before proceeding
        if not self.validate_current_step():
            print("Validation failed, cannot proceed to next step")
            return
            
        print(f"Moving from step {self.current_step} to step {self.current_step + 1}")
        if self.current_step < 2:  # 0-based indexing, we have 3 steps
            self.current_step += 1
            
            # If going to step 2 (entry matching), prepare the matches table
            if self.current_step == 1:
                print("Preparing entry matches for step 2")
                self.prepare_entry_matches()
                
            # If going to step 3 (field mapping), prepare the field mappings
            if self.current_step == 2:
                print("Setting up field mappings for step 3")
                self.setup_field_mappings()
                
            print(f"Setting stack index to {self.current_step}")
            self.stack.setCurrentIndex(self.current_step)
            self.update_step_display()
            print("Step display updated")

    def setup_field_mappings(self):
        """Set up the field mappings UI for step 3"""
        # Clear existing mappings
        for i in reversed(range(1, self.mapping_layout.rowCount())):
            for j in range(self.mapping_layout.columnCount()):
                item = self.mapping_layout.itemAtPosition(i, j)
                if item and item.widget():
                    item.widget().deleteLater()
                    
        self.field_mappings_controls = []
        
        # Start with blank row to give some space
        blank_row = 1
        self.mapping_layout.addWidget(QWidget(), blank_row, 0)
        
        # Add field mapping rows
        row = blank_row + 1
        
        # Filter out special fields
        skip_fields = ["Show", "Scene", "Take", "Category"]
        
        # Only show fields in CSV that haven't been matched to key fields
        for i, header in enumerate(self.csv_headers):
            # Skip if it's one of the special fields we already matched
            if header == self.character_column or header == self.scene_column or header == self.take_column:
                continue
                
            # Add CSV field label
            self.mapping_layout.addWidget(QLabel(header), row, 0)
            
            # Add arrow
            self.mapping_layout.addWidget(QLabel("→"), row, 1)
            
            # Add target field combo box
            target_combo = QComboBox()
            # Add all audio metadata fields except those we already mapped
            for field in ["Show", "Scene", "Take", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]:
                if field not in skip_fields:
                    target_combo.addItem(field)
                    
            # Try to auto-select the field based on name similarity
            header_lower = header.lower()
            best_match_idx = 0
            best_match_score = 0
            
            for idx in range(target_combo.count()):
                field = target_combo.itemText(idx).lower()
                # Simple string similarity check
                if header_lower in field or field in header_lower:
                    # Perfect match
                    target_combo.setCurrentIndex(idx)
                    break
                # Partial match
                score = 0
                for word in header_lower.split():
                    if word in field:
                        score += 1
                for word in field.split():
                    if word in header_lower:
                        score += 1
                if score > best_match_score:
                    best_match_score = score
                    best_match_idx = idx
            
            # If no perfect match but we found partial matches, use the best one
            if best_match_score > 0:
                target_combo.setCurrentIndex(best_match_idx)
                
            self.mapping_layout.addWidget(target_combo, row, 2)
            
            # Add include checkbox
            include_cb = QCheckBox()
            include_cb.setChecked(True)  # Default to checked
            self.mapping_layout.addWidget(include_cb, row, 3)
            
            # Store controls for later access
            self.field_mappings_controls.append((header, target_combo, include_cb))
            
            row += 1
                
        # Add a stretch at the end to push everything to the top
        self.mapping_layout.setRowStretch(row, 1)

    def select_all_fields(self):
        """Select all fields for mapping"""
        for _, _, checkbox in self.field_mappings_controls:
            checkbox.setChecked(True)
            
    def select_no_fields(self):
        """Deselect all fields for mapping"""
        for _, _, checkbox in self.field_mappings_controls:
            checkbox.setChecked(False)
            
    def get_field_mappings(self):
        """Get the field mappings from the UI controls"""
        mappings = {}
        for csv_field, target_combo, include_cb in self.field_mappings_controls:
            if include_cb.isChecked():
                target_field = target_combo.currentText()
                mappings[csv_field] = target_field
        return mappings
        
    def accept(self):
        """Called when the finish button is clicked"""
        # Return the accepted result
        super().accept()

def main():
    app = QApplication(sys.argv)
    window = AudioMetadataEditor()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 