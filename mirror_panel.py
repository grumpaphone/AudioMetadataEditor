import sys
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QGroupBox, QListWidget, QSpinBox, 
                             QCheckBox, QFileDialog, QMessageBox, QListWidgetItem)
from PyQt6.QtCore import Qt

class MirrorPanel(QWidget):
    """Panel for mirroring files to another location with organization options"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("MirrorPanel")
        
        # Initialize variables
        self.selected_rows = []
        self.destination_dir = ""
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self):
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
        
        # Action Buttons
        action_layout = QVBoxLayout()
        mirror_qcode_button = QPushButton("Mirror for QCODE Take Review")
        mirror_qcode_button.clicked.connect(self.mirror_for_qcode)
        action_layout.addWidget(mirror_qcode_button)

        mirror_custom_button = QPushButton("Mirror Files with Custom Organization")
        mirror_custom_button.clicked.connect(self.mirror_with_custom_org)
        action_layout.addWidget(mirror_custom_button)

        layout.addLayout(action_layout)
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
    
    def mirror_for_qcode(self):
        if not self.destination_dir:
            QMessageBox.warning(self, "No Destination", "Please select a destination directory.")
            return
        if hasattr(self.parent, 'mirror_files_qcode_take_review'):
            day_number = self.day_spinner.value()
            overwrite = self.overwrite_checkbox.isChecked()
            self.parent.mirror_files_qcode_take_review(self.selected_rows, self.destination_dir, day_number, overwrite)

    def mirror_with_custom_org(self):
        QMessageBox.information(self, "Not Implemented", "Custom folder organization is not yet implemented.") 