#!/usr/bin/env python3
"""This script creates a standalone app that has a toggle theme button."""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

class ThemeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Theme Toggle Demo")
        self.setGeometry(100, 100, 600, 400)
        
        # Set initial theme
        self.current_theme = "light"
        
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Set up layout
        layout = QVBoxLayout(self.central_widget)
        
        # Add a label
        self.label = QLabel("This is a demo showing theme toggling in PyQt6")
        layout.addWidget(self.label)
        
        # Add a theme toggle button
        theme_button = QPushButton("Toggle Theme (Light/Dark)")
        theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(theme_button)
        
        # Apply the initial theme
        self.apply_theme()
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        if self.current_theme == "light":
            self.current_theme = "dark"
        else:
            self.current_theme = "light"
        
        # Apply the new theme
        self.apply_theme()
    
    def apply_theme(self):
        """Apply the current theme to the application"""
        if self.current_theme == "light":
            # Set light theme colors
            self.central_widget.setStyleSheet("""
                background-color: #F5EAD9;
                color: #333333;
            """)
            
            self.label.setStyleSheet("""
                color: #333333;
                font-size: 16px;
            """)
        else:
            # Set dark theme colors
            self.central_widget.setStyleSheet("""
                background-color: #333333;
                color: #F5F5F5;
            """)
            
            self.label.setStyleSheet("""
                color: #F5F5F5;
                font-size: 16px;
            """)

def main():
    app = QApplication(sys.argv)
    window = ThemeWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 