#!/usr/bin/env python3
import os

# App file
app_file = 'app.py'

# Create backup
os.system(f'cp {app_file} {app_file}.bak.darkmode')

# Read app file
with open(app_file, 'r') as f:
    content = f.read()

# ------- ADDITIONS -------

# 1. Add current_theme variable to __init__
init_addition = """        # Set initial theme
        self.current_theme = "light"
"""

# Find the right place to insert
init_pos = content.find('def __init__(self):')
init_end = content.find('# Configure for frameless window', init_pos)
if init_end > init_pos:
    content = content[:init_end] + init_addition + content[init_end:]

# 2. Add toggle_theme method
toggle_theme_method = """
    def toggle_theme(self):
        \"\"\"Toggle between light and dark themes\"\"\"
        if self.current_theme == "light":
            self.current_theme = "dark"
            self.status_label.setText("Switched to dark theme")
            
            # Dark mode for central widget
            self.central_widget.setStyleSheet(\"\"\"
                #central_widget {
                    background-color: rgba(40, 40, 40, 0.95);
                    border-radius: 10px;
                }
            \"\"\")
            
            # Dark mode for metadata table
            self.metadata_table.setStyleSheet(\"\"\"
                QTableWidget {
                    border: none;
                    background-color: rgba(45, 45, 45, 0.9);
                    alternate-background-color: rgba(50, 50, 50, 0.75);
                    color: #E0E0E0;
                }
                
                QHeaderView::section {
                    background-color: rgba(45, 45, 45, 0.85);
                    color: #E0E0E0;
                }
            \"\"\")
        else:
            self.current_theme = "light"
            self.status_label.setText("Switched to light theme")
            
            # Light mode for central widget
            self.central_widget.setStyleSheet(\"\"\"
                #central_widget {
                    background-color: rgba(245, 236, 220, 0.92);
                    border-radius: 10px;
                }
            \"\"\")
            
            # Light mode for metadata table
            self.metadata_table.setStyleSheet(\"\"\"
                QTableWidget {
                    border: none;
                    background-color: rgba(255, 255, 255, 0.9);
                    alternate-background-color: rgba(249, 245, 239, 0.75);
                    color: #333333;
                }
                
                QHeaderView::section {
                    background-color: rgba(255, 255, 255, 0.85);
                    color: #333333;
                }
            \"\"\")
"""

# Add toggle_theme method before setup_shortcuts
setup_pos = content.find('def setup_shortcuts(self):')
if setup_pos > 0:
    content = content[:setup_pos] + toggle_theme_method + "\n" + content[setup_pos:]

# 3. Add button to title bar
title_bar_addition = """        # Add dark mode toggle button
        dark_mode_btn = QPushButton("🌙")
        dark_mode_btn.setToolTip("Toggle Dark Mode")
        dark_mode_btn.setFixedSize(32, 32)
        dark_mode_btn.setStyleSheet(\"\"\"
            QPushButton {
                border: none;
                background-color: rgba(245, 236, 220, 0.75);
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(232, 223, 208, 0.85);
            }
        \"\"\")
        dark_mode_btn.clicked.connect(self.toggle_theme)
        title_layout.addWidget(dark_mode_btn)
"""

# Add dark mode button in title bar right before main layout.addWidget(title_bar)
title_end = content.find('main_layout.addWidget(title_bar)')
if title_end > 0:
    add_pos = content.rfind('\n', 0, title_end)
    content = content[:add_pos] + "\n" + title_bar_addition + content[add_pos:]

# 4. Add shortcut for toggling dark mode
shortcut_addition = """        # Dark mode toggle shortcut
        dark_mode_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        dark_mode_shortcut.activated.connect(self.toggle_theme)
"""

# Add shortcut at the end of setup_shortcuts
setup_end = content.find('def select_search_field', setup_pos)
if setup_end > setup_pos:
    add_pos = content.rfind('\n', setup_pos, setup_end)
    content = content[:add_pos] + "\n" + shortcut_addition + content[add_pos:]

# Write modified content back to file
with open(app_file, 'w') as f:
    f.write(content)

print("Added dark mode toggle functionality to app.py")
print("Use the 🌙 button in the title bar or press Ctrl+D to toggle dark mode") 