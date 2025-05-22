#!/usr/bin/env python3

import re

print("Creating a backup of app.py")
import shutil
shutil.copy2('app.py', 'app.py.backup_darkmode2')

with open('app.py', 'r') as f:
    content = f.read()

# Add theme variable to __init__
init_pattern = r'(def __init__\(self\):.*?self\.progress_dialog = None)'
init_replace = r'\1\n\n        # Set initial theme\n        self.current_theme = "light"'
content = re.sub(init_pattern, init_replace, content, flags=re.DOTALL)

# Add toggle_theme method
toggle_method = """
    def toggle_theme(self):
        \"\"\"Toggle between light and dark themes\"\"\"
        if self.current_theme == "light":
            self.current_theme = "dark"
            self.status_label.setText("Switched to dark theme")
            
            # Update stylesheet for dark mode
            self.central_widget.setStyleSheet(\"\"\"
                #central_widget {
                    background-color: rgba(40, 40, 40, 0.95);
                    border-radius: 10px;
                }
            \"\"\")
            
            # Update title bar
            if hasattr(self, "title_bar"):
                self.title_bar.setStyleSheet(\"\"\"
                    #title_bar {
                        background-color: rgba(40, 40, 40, 0.95);
                        border-top-left-radius: 10px;
                        border-top-right-radius: 10px;
                        border-bottom: 1px solid rgba(70, 70, 70, 0.7);
                    }
                \"\"\")
                
            # Update search frame
            if hasattr(self, "search_frame"):
                self.search_frame.setStyleSheet(\"\"\"
                    #search_frame {
                        background-color: rgba(50, 50, 50, 0.85);
                        border: 1px solid rgba(70, 70, 70, 0.8);
                        border-radius: 6px;
                    }
                \"\"\")
                
            # Update search input
            if hasattr(self, "search_input"):
                self.search_input.setStyleSheet(\"\"\"
                    QLineEdit {
                        border: none;
                        background: transparent;
                        padding: 4px;
                        color: #E0E0E0;
                    }
                \"\"\")
            
            # Update field indicator
            if hasattr(self, "field_indicator"):
                self.field_indicator.setStyleSheet(\"\"\"
                    #field_indicator {
                        color: #B0B0B0;
                        padding-right: 0px;
                    }
                \"\"\")
                
            # Update dropdown button
            if hasattr(self, "search_field_button"):
                self.search_field_button.setStyleSheet(\"\"\"
                    #dropdown_button {
                        border: none;
                        background: transparent;
                        color: #B0B0B0;
                        padding: 0 5px 0 0;
                        text-align: center;
                        font-size: 10px;
                    }
                    #dropdown_button:hover {
                        color: #E0E0E0;
                    }
                \"\"\")
                
            # Update table colors
            self.metadata_table.setStyleSheet(\"\"\"
                QTableWidget {
                    border: none;
                    background-color: rgba(45, 45, 45, 0.9);
                    selection-background-color: rgba(70, 90, 120, 0.85);
                    alternate-background-color: rgba(50, 50, 50, 0.75);
                    gridline-color: rgba(60, 60, 60, 0.8);
                    color: #E0E0E0;
                }
                
                QHeaderView::section {
                    background-color: rgba(45, 45, 45, 0.85);
                    padding: 6px;
                    border: none;
                    border-bottom: 1px solid rgba(70, 70, 70, 0.8);
                    font-weight: 500;
                    color: #E0E0E0;
                }
            \"\"\")
            
            # Update status label
            self.status_label.setStyleSheet("color: #B0B0B0; font-size: 12px; padding: 4px;")
            
        else:
            self.current_theme = "light"
            self.status_label.setText("Switched to light theme")
            
            # Restore light theme
            self.central_widget.setStyleSheet(\"\"\"
                #central_widget {
                    background-color: rgba(245, 236, 220, 0.92);
                    border-radius: 10px;
                }
            \"\"\")
            
            # Update title bar
            if hasattr(self, "title_bar"):
                self.title_bar.setStyleSheet(\"\"\"
                    #title_bar {
                        background-color: rgba(245, 236, 220, 0.85);
                        border-top-left-radius: 10px;
                        border-top-right-radius: 10px;
                        border-bottom: 1px solid rgba(224, 216, 201, 0.7);
                    }
                \"\"\")
                
            # Update search frame
            if hasattr(self, "search_frame"):
                self.search_frame.setStyleSheet(\"\"\"
                    #search_frame {
                        background-color: rgba(255, 255, 255, 0.85);
                        border: 1px solid rgba(224, 216, 201, 0.8);
                        border-radius: 6px;
                    }
                \"\"\")
                
            # Update search input
            if hasattr(self, "search_input"):
                self.search_input.setStyleSheet(\"\"\"
                    QLineEdit {
                        border: none;
                        background: transparent;
                        padding: 4px;
                        color: #333333;
                    }
                \"\"\")
            
            # Update field indicator
            if hasattr(self, "field_indicator"):
                self.field_indicator.setStyleSheet(\"\"\"
                    #field_indicator {
                        color: #666;
                        padding-right: 0px;
                    }
                \"\"\")
                
            # Update dropdown button
            if hasattr(self, "search_field_button"):
                self.search_field_button.setStyleSheet(\"\"\"
                    #dropdown_button {
                        border: none;
                        background: transparent;
                        color: #666;
                        padding: 0 5px 0 0;
                        text-align: center;
                        font-size: 10px;
                    }
                    #dropdown_button:hover {
                        color: #333;
                    }
                \"\"\")
                
            # Reset table styles
            self.metadata_table.setStyleSheet(\"\"\"
                QTableWidget {
                    border: none;
                    background-color: rgba(255, 255, 255, 0.9);
                    selection-background-color: rgba(232, 223, 208, 0.85);
                    alternate-background-color: rgba(249, 245, 239, 0.75);
                    gridline-color: rgba(232, 223, 208, 0.8);
                    color: #333333;
                }
                
                QHeaderView::section {
                    background-color: rgba(255, 255, 255, 0.85);
                    padding: 6px;
                    border: none;
                    border-bottom: 1px solid rgba(224, 216, 201, 0.8);
                    font-weight: 500;
                    color: #333333;
                }
            \"\"\")
            
            # Reset status label
            self.status_label.setStyleSheet("color: #666666; font-size: 12px; padding: 4px;")
        
        # Update theme icon
        if hasattr(self, "theme_toggle"):
            self.theme_toggle.setIcon(self.create_theme_icon())
"""

# Add create_theme_icon method
theme_icon_method = """
    def create_theme_icon(self):
        \"\"\"Create a theme toggle icon from SVG\"\"\"
        # SVG icon for theme toggle (sun/moon)
        if self.current_theme == "light":
            # Moon icon for dark mode
            svg_content = \"\"\"
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            \"\"\"
        else:
            # Sun icon for light mode
            svg_content = \"\"\"
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="12" y1="1" x2="12" y2="3" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="12" y1="21" x2="12" y2="23" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="1" y1="12" x2="3" y2="12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="21" y1="12" x2="23" y2="12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            \"\"\"
        
        # Create a QPixmap with transparent background
        icon_size = 24
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        # Create a painter for the pixmap
        painter = QPainter(pixmap)
        
        # Load the SVG content
        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding="utf-8"))
        
        # Render the SVG onto the pixmap
        svg_renderer.render(painter)
        
        # Finish painting
        painter.end()
        
        return QIcon(pixmap)
"""

# Insert the theme methods after create_redo_icon method
redo_icon_pattern = r'(def create_redo_icon\(self\):.*?return QIcon\(pixmap\))'
methods_replacement = r'\1' + toggle_method + theme_icon_method
content = re.sub(redo_icon_pattern, methods_replacement, content, flags=re.DOTALL)

# Add theme toggle button to the title bar
title_bar_pattern = r'(# Sidebar toggle button.*?title_layout\.addWidget\(self\.sidebar_toggle\))'
title_bar_replacement = r'\1\n        \n        # Theme toggle button\n        self.theme_toggle = QPushButton()\n        self.theme_toggle.setIcon(self.create_theme_icon())\n        self.theme_toggle.setToolTip("Toggle Theme (Ctrl+D)")\n        self.theme_toggle.setProperty("class", "icon-button")\n        self.theme_toggle.setFixedSize(32, 32)\n        self.theme_toggle.clicked.connect(self.toggle_theme)\n        title_layout.addWidget(self.theme_toggle)'
content = re.sub(title_bar_pattern, title_bar_replacement, content, flags=re.DOTALL)

# Add theme shortcut
shortcuts_pattern = r'(# Toggle panel shortcut \(Ctrl\+T\).*?toggle_panel_shortcut\.activated\.connect\(self\.toggle_mirror_panel\))'
shortcuts_replacement = r'\1\n        \n        # Toggle theme shortcut (Ctrl+D)\n        theme_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)\n        theme_shortcut.activated.connect(self.toggle_theme)'
content = re.sub(shortcuts_pattern, shortcuts_replacement, content, flags=re.DOTALL)

# Save the modified file
with open('app.py', 'w') as f:
    f.write(content)

print("Dark mode functionality has been added!")
print("You can now toggle between light and dark themes with Ctrl+D or using the theme toggle button.") 