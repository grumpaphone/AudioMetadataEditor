#!/usr/bin/env python3

import re

print("Creating a backup of app.py")
import shutil
shutil.copy2('app.py', 'app.py.backup_darkmode2')

# Read the file
with open('app.py', 'r') as f:
    content = f.read()

# 1. Add current_theme initialization in __init__
if 'self.current_theme = \'light\'' not in content:
    # Find the right spot in __init__
    init_pattern = r'(def __init__\(self\):.*?self\.progress_dialog = None)'
    init_replacement = r'\1\n\n        # Set initial theme\n        self.current_theme = \'light\''
    content = re.sub(init_pattern, init_replacement, content, flags=re.DOTALL)

# 2. Replace apply_stylesheet method with one that supports theming
stylesheet_pattern = r'def apply_stylesheet\(self\):.*?self\.setStyleSheet\(stylesheet\)'
stylesheet_replacement = '''def apply_stylesheet(self):
        """Apply a modern macOS-inspired stylesheet with translucent elements"""
        # Define color palettes for light and dark themes
        if self.current_theme == 'light':
            # Light theme color palette
            CP = {
                # Background colors
                "light_bg_primary": "#F5EAD9",  # Main background
                "light_bg_secondary": "#EADDCA",  # Secondary background
                "light_bg_tertiary": "#E1D4BE",  # Tertiary background (more contrast)
                
                # Dark theme equivalents kept for reference
                "dark_bg_primary": "#282828",
                "dark_bg_secondary": "#333333",
                "dark_bg_tertiary": "#3C3C3C",
                
                # Text colors for light theme
                "dark_text_primary": "#333333",
                "dark_text_secondary": "#555555",
                
                # Text colors for dark theme kept for reference
                "light_text_primary": "#E0E0E0",
                "light_text_secondary": "#B0B0B0",
                "almost_white_text": "#F5F5F5",
                
                # Accent colors - shared between themes
                "olive_green": "#748D44",
                "light_olive_green": "#85A156",
                "medium_teal": "#589DA4",
                "dark_teal": "#27768A",
            }
            
            # Text colors
            TC = {
                # On light background
                "primary_on_light": "#333333",
                "secondary_on_light": "#555555",
                "tertiary_on_light": "#777777",
                
                # On dark background 
                "primary_on_dark": "#FFFFFF",
                "secondary_on_dark": "#E0E0E0",
                "tertiary_on_dark": "#B0B0B0",
            }
            
            # UI accent colors
            UA = {
                # Window/widget backgrounds
                "window_bg": "rgba(245, 236, 220, 0.92)",
                "widget_bg": "rgba(255, 255, 255, 0.85)",
                
                # Border colors
                "border_light": "rgba(224, 216, 201, 0.5)",
                "border_medium": "rgba(208, 200, 185, 0.8)",
                "border_dark": "rgba(196, 181, 159, 0.85)",
                
                # Button colors
                "button_primary_bg": "rgba(196, 181, 159, 0.92)",
                "button_primary_hover": "rgba(181, 167, 144, 0.95)",
                "button_primary_pressed": "rgba(166, 152, 127, 1.0)",
                "button_primary_text": "#FFFFFF",
                "button_primary_border": "rgba(181, 167, 144, 0.3)",
                
                "button_secondary_bg": "rgba(245, 236, 220, 0.75)",
                "button_secondary_hover": "rgba(232, 223, 208, 0.85)",
                "button_secondary_pressed": "rgba(224, 216, 201, 0.92)",
                "button_secondary_text": "#333333",
                "button_secondary_border": "rgba(208, 200, 185, 0.8)",
                
                # Selection colors
                "selection_bg": "rgba(232, 223, 208, 0.85)",
                "selection_fg": "#333333",
                
                # Scrollbar
                "scrollbar_bg": "rgba(245, 236, 220, 0.3)",
                "scrollbar_handle": "rgba(196, 181, 159, 0.7)",
                
                # Table
                "table_header_bg": "rgba(255, 255, 255, 0.85)",
                "table_alternate_bg": "rgba(249, 245, 239, 0.75)",
                "table_grid": "rgba(232, 223, 208, 0.8)",
                
                # Input field
                "input_bg": "rgba(255, 255, 255, 0.85)",
                "input_border": "rgba(224, 216, 201, 0.8)",
                "input_focus_border": "rgba(196, 181, 159, 0.92)",
                "input_focus_bg": "rgba(255, 255, 255, 0.95)",
            }
        else:
            # Dark theme color palette
            CP = {
                # Background colors
                "dark_bg_primary": "#282828",  # Main background
                "dark_bg_secondary": "#333333",  # Secondary background
                "dark_bg_tertiary": "#3C3C3C",  # Tertiary background
                
                # Light theme equivalents kept for reference
                "light_bg_primary": "#F5EAD9",
                "light_bg_secondary": "#EADDCA",
                "light_bg_tertiary": "#E1D4BE",
                
                # Text colors for dark theme
                "light_text_primary": "#E0E0E0",
                "light_text_secondary": "#B0B0B0",
                "almost_white_text": "#F5F5F5",
                
                # Text colors for light theme kept for reference
                "dark_text_primary": "#333333",
                "dark_text_secondary": "#555555",
                
                # Accent colors - shared between themes
                "olive_green": "#748D44",
                "light_olive_green": "#85A156",
                "medium_teal": "#589DA4", 
                "dark_teal": "#27768A",
            }
            
            # Text colors
            TC = {
                # On light background
                "primary_on_light": "#333333",
                "secondary_on_light": "#555555",
                "tertiary_on_light": "#777777",
                
                # On dark background 
                "primary_on_dark": "#FFFFFF",
                "secondary_on_dark": "#E0E0E0",
                "tertiary_on_dark": "#B0B0B0",
            }
            
            # UI accent colors for dark theme
            UA = {
                # Window/widget backgrounds
                "window_bg": "rgba(40, 40, 40, 0.95)",
                "widget_bg": "rgba(50, 50, 50, 0.9)",
                
                # Border colors
                "border_light": "rgba(70, 70, 70, 0.5)",
                "border_medium": "rgba(85, 85, 85, 0.7)",
                "border_dark": "rgba(100, 100, 100, 0.85)",
                
                # Button colors
                "button_primary_bg": "rgba(75, 110, 175, 0.9)",
                "button_primary_hover": "rgba(85, 125, 195, 0.95)",
                "button_primary_pressed": "rgba(95, 140, 215, 1.0)",
                "button_primary_text": "#FFFFFF",
                "button_primary_border": "rgba(65, 100, 165, 0.3)",
                
                "button_secondary_bg": "rgba(60, 60, 60, 0.75)",
                "button_secondary_hover": "rgba(70, 70, 70, 0.85)",
                "button_secondary_pressed": "rgba(80, 80, 80, 0.92)",
                "button_secondary_text": "#FFFFFF",
                "button_secondary_border": "rgba(80, 80, 80, 0.8)",
                
                # Selection colors
                "selection_bg": "rgba(70, 90, 120, 0.85)",
                "selection_fg": "#FFFFFF",
                
                # Scrollbar
                "scrollbar_bg": "rgba(40, 40, 40, 0.3)",
                "scrollbar_handle": "rgba(80, 80, 80, 0.7)",
                
                # Table
                "table_header_bg": "rgba(45, 45, 45, 0.85)",
                "table_alternate_bg": "rgba(50, 50, 50, 0.75)",
                "table_grid": "rgba(60, 60, 60, 0.8)",
                
                # Input field
                "input_bg": "rgba(50, 50, 50, 0.85)",
                "input_border": "rgba(70, 70, 70, 0.8)",
                "input_focus_border": "rgba(85, 120, 200, 0.92)",
                "input_focus_bg": "rgba(55, 55, 55, 0.95)",
            }
        }
        
        # Set system font (SF Pro-like) - using system font family
        if sys.platform == "darwin":  # macOS
            app_font = QFont(".AppleSystemUIFont", 12)  # Smaller font size
        else:  # Windows/Linux
            app_font = QFont("Segoe UI", 12)  # Smaller font size
        QApplication.setFont(app_font)
        
        # Create and apply stylesheet
        stylesheet = f"""
        /* Main window - higher alpha for frostier effect */
        QMainWindow {{
            background-color: {UA["window_bg"]};
            border: none;
            border-radius: 10px;
        }}
        
        #central_widget {{
            background-color: {UA["window_bg"]};
            border-radius: 10px;
        }}
        
        /* Content container */
        .content-container {{
            background-color: {UA["widget_bg"]};
            border-radius: 10px;
        }}
        
        /* Title bar */
        #title_bar {{
            background-color: {UA["window_bg"]};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom: 1px solid {UA["border_medium"]};
        }}
        
        /* Icon button style */
        .icon-button {{
            background-color: {UA["button_secondary_bg"]};
            border: none;
            border-radius: 8px;
            padding: 8px;
        }}
        
        .icon-button:hover {{
            background-color: {UA["button_secondary_hover"]};
        }}
        
        .icon-button:pressed {{
            background-color: {UA["button_secondary_pressed"]};
        }}
        
        /* Action button style */
        .action-button {{
            background-color: {UA["button_secondary_bg"]};
            color: {TC["primary_on_" + self.current_theme]};
            border: none;
            border-radius: 8px;
            font-weight: 500;
            font-size: 13px;
        }}
        
        .action-button:hover {{
            background-color: {UA["button_secondary_hover"]};
        }}
        
        .action-button:pressed {{
            background-color: {UA["button_secondary_pressed"]};
        }}
        
        /* Primary button style */
        .action-button.primary {{
            background-color: {UA["button_primary_bg"]};
            color: {UA["button_primary_text"]};
            border: none;
        }}
        
        .action-button.primary:hover {{
            background-color: {UA["button_primary_hover"]};
        }}
        
        .action-button.primary:pressed {{
            background-color: {UA["button_primary_pressed"]};
        }}
        
        /* Search frame styling */
        #search_frame {{
            background-color: {UA["input_bg"]};
            border: 1px solid {UA["input_border"]};
            border-radius: 6px;
            padding: 0px;
        }}
        
        #search_frame QLineEdit {{
            border: none;
            background: transparent;
            padding: 4px 8px;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        #field_indicator, #dropdown_button {{
            color: {TC["secondary_on_" + self.current_theme]};
            background: transparent;
            border: none;
            padding: 6px 4px;
            margin: 0px;
        }}
        
        /* QLineEdit styling */
        QLineEdit {{
            border: 1px solid {UA["input_border"]};
            border-radius: 6px;
            padding: 4px 6px;
            background-color: {UA["input_bg"]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QLineEdit:focus {{
            border: 1px solid {UA["input_focus_border"]};
            background-color: {UA["input_focus_bg"]};
        }}
        
        /* Labels */
        QLabel {{
            color: {TC["primary_on_" + self.current_theme]};
            font-size: 13px;
        }}
        
        /* Title label larger */
        #title_label {{
            font-size: 18px;
            font-weight: 500;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        /* Table styling */
        QTableWidget {{
            border: none;
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            selection-background-color: {UA["selection_bg"]};
            alternate-background-color: {UA["table_alternate_bg"]};
            gridline-color: {UA["table_grid"]};
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QHeaderView::section {{
            background-color: {UA["table_header_bg"]};
            padding: 6px;
            border: none;
            border-bottom: 1px solid {UA["border_medium"]};
            font-weight: 500;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        /* Status bar */
        .status-label {{
            color: {TC["secondary_on_" + self.current_theme]};
            font-size: 12px;
            padding: 4px;
        }}
        
        /* Dialog styling */
        QDialog {{
            background-color: {UA["window_bg"]};
            border-radius: 8px;
        }}
        
        /* Dropdown/ComboBox styling */
        QComboBox {{
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 5px;
            background-color: {UA["input_bg"]};
            color: {TC["primary_on_" + self.current_theme]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
        }}
        
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid {UA["border_medium"]};
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }}
        
        QComboBox::down-arrow {{
            width: 12px;
            height: 12px;
            image: url(:/icons/dropdown_arrow.png);
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {UA["widget_bg"]};
            border: 1px solid {UA["border_medium"]};
            color: {TC["primary_on_" + self.current_theme]};
            selection-background-color: {UA["selection_bg"]};
            selection-color: {UA["selection_fg"]};
        }}
        
        /* Line Edit and ComboBox common styles */
        QLineEdit, QComboBox, QSpinBox {{
            padding: 5px;
            border: 1px solid {UA["border_medium"]};
            border-radius: 4px;
            background-color: {UA["input_bg"]};
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        /* Splitter styling */
        QSplitter::handle {{
            background-color: {UA["border_medium"]};
        }}
        
        /* Menu styling */
        QMenu {{
            background-color: {UA["widget_bg"]};
            border: 1px solid {UA["border_medium"]};
            border-radius: 6px;
            padding: 4px;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QMenu::item {{
            padding: 4px 20px 4px 6px;
            border-radius: 4px;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QMenu::item:selected {{
            background-color: {UA["selection_bg"]};
            color: {UA["selection_fg"]};
        }}
        
        /* QScrollBar styling */
        QScrollBar:vertical {{
            border: none;
            background: {UA["scrollbar_bg"]};
            width: 10px;
            margin: 0px;
            border-radius: 5px;
        }}
        
        QScrollBar::handle:vertical {{
            background: {UA["scrollbar_handle"]};
            min-height: 20px;
            border-radius: 5px;
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        
        QScrollBar:horizontal {{
            border: none;
            background: {UA["scrollbar_bg"]};
            height: 10px;
            margin: 0px;
            border-radius: 5px;
        }}
        
        QScrollBar::handle:horizontal {{
            background: {UA["scrollbar_handle"]};
            min-width: 20px;
            border-radius: 5px;
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            border: none;
            background: none;
            width: 0px;
        }}
        
        /* List Widget */
        QListWidget {{
            background-color: {UA["widget_bg"]};
            border: 1px solid {UA["border_medium"]};
            border-radius: 4px;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        /* Group Box */
        QGroupBox {{
            background-color: {UA["widget_bg"]};
            border: 1px solid {UA["border_medium"]};
            border-radius: 4px;
            margin-top: 12px;
            font-weight: bold;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        /* Checkbox */
        QCheckBox {{
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QCheckBox::indicator:unchecked {{
            border: 1px solid {UA["border_medium"]};
            border-radius: 2px;
            background-color: {UA["widget_bg"]};
        }}
        
        QCheckBox::indicator:checked {{
            border: 1px solid {UA["button_primary_bg"]};
            border-radius: 2px;
            background-color: {UA["button_primary_bg"]};
        }}
        
        /* Progress Dialog */
        QProgressDialog {{
            background-color: {UA["window_bg"]};
            border-radius: 8px;
        }}
        
        QProgressBar {{
            border: 1px solid {UA["border_medium"]};
            border-radius: 3px;
            background-color: {UA["widget_bg"]};
            text-align: center;
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QProgressBar::chunk {{
            background-color: {UA["button_primary_bg"]};
            border-radius: 2px;
        }}
        
        QPushButton {{
            color: {TC["primary_on_" + self.current_theme]};
        }}
        
        QPushButton:disabled {{
            color: {TC["tertiary_on_" + self.current_theme]};
            background-color: {UA["border_light"]};
        }}
        
        /* Mirror Panel */ 
        #MirrorPanel {{
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
            border-left: 1px solid {UA["border_medium"]};
        }}
        
        QWidget#MirrorPanelContent {{
            background-color: {CP["light_bg_primary"] if self.current_theme == 'light' else CP["dark_bg_secondary"]};
        }}
        
        QWidget#MirrorPanel QListWidget::item:selected {{
            background-color: {UA["selection_bg"]};
            color: {UA["selection_fg"]};
        }}
        """
        
        self.setStyleSheet(stylesheet)'''

content = re.sub(stylesheet_pattern, stylesheet_replacement, content, flags=re.DOTALL)

# 3. Replace MacStyleDelegate paint method to support dark mode
delegate_pattern = r'class MacStyleDelegate\(QStyledItemDelegate\):.*?def paint\(self, painter, option, index\):.*?painter\.restore\(\)'
delegate_replacement = '''class MacStyleDelegate(QStyledItemDelegate):
    """Custom delegate for macOS style table items"""
    def paint(self, painter, option, index):
        # Save painter state
        painter.save()
        
        # Get main window reference to check theme
        main_window = None
        widget = option.widget
        while widget is not None:
            if isinstance(widget, AudioMetadataEditor):
                main_window = widget
                break
            widget = widget.parent()
        
        # Default to light theme if can't determine
        is_dark_theme = False
        if main_window is not None:
            is_dark_theme = main_window.current_theme == 'dark'
        
        # Draw background based on theme
        if option.state & QStyle.StateFlag.State_Selected:
            # Selection color
            painter.fillRect(option.rect, QColor("#5E90C4" if is_dark_theme else "#E0F2FF"))
        elif index.row() % 2 == 0:  # Alternating row colors
            painter.fillRect(option.rect, QColor("#3C3C3C" if is_dark_theme else "#FAFAFA"))
        else:
            painter.fillRect(option.rect, QColor("#333333" if is_dark_theme else "#FFFFFF"))
        
        # Draw text with proper padding
        text_rect = option.rect.adjusted(12, 6, -12, -6)  # Add padding
        
        # Set text color based on theme and selection
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QColor("#FFFFFF" if is_dark_theme else "#000000"))
        else:
            painter.setPen(QColor("#E0E0E0" if is_dark_theme else "#000000"))
        
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, index.data())
        
        # Restore painter state
        painter.restore()'''

content = re.sub(delegate_pattern, delegate_replacement, content, flags=re.DOTALL)

# 4. Add toggle_theme method
if 'def toggle_theme' not in content:
    toggle_theme_pattern = r'(def create_redo_icon\(self\):.*?return QIcon\(pixmap\))'
    toggle_theme_replacement = r'\1\n\n    def toggle_theme(self):\n        """Toggle between light and dark themes"""\n        if self.current_theme == \'light\':\n            self.current_theme = \'dark\'\n            self.status_label.setText("Switched to dark theme")\n        else:\n            self.current_theme = \'light\'\n            self.status_label.setText("Switched to light theme")\n        \n        # Update the application stylesheet\n        self.apply_stylesheet()\n        \n        # Update theme icon\n        self.theme_toggle.setIcon(self.create_theme_icon())\n        \n        # Update table delegate\n        self.metadata_table.setItemDelegate(MacStyleDelegate())'
    content = re.sub(toggle_theme_pattern, toggle_theme_replacement, content, flags=re.DOTALL)

# 5. Add create_theme_icon method
if 'def create_theme_icon' not in content:
    theme_icon_pattern = r'(def create_redo_icon\(self\):.*?return QIcon\(pixmap\))'
    theme_icon_replacement = r'\1\n\n    def create_theme_icon(self):\n        """Create a theme toggle icon from SVG"""\n        # SVG icon for theme toggle\n        if self.current_theme == \'light\':\n            # Moon icon for dark mode\n            svg_content = """\n            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">\n                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n            </svg>\n            """\n        else:\n            # Sun icon for light mode\n            svg_content = """\n            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">\n                <circle cx="12" cy="12" r="5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="12" y1="1" x2="12" y2="3" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="12" y1="21" x2="12" y2="23" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="1" y1="12" x2="3" y2="12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="21" y1="12" x2="23" y2="12" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>\n            </svg>\n            """\n        \n        # Create a QPixmap with transparent background\n        icon_size = 24\n        pixmap = QPixmap(icon_size, icon_size)\n        pixmap.fill(Qt.GlobalColor.transparent)\n        \n        # Create a painter for the pixmap\n        painter = QPainter(pixmap)\n        \n        # Load the SVG content\n        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding=\'utf-8\'))\n        \n        # Render the SVG onto the pixmap\n        svg_renderer.render(painter)\n        \n        # Finish painting\n        painter.end()\n        \n        return QIcon(pixmap)'
    content = re.sub(theme_icon_pattern, theme_icon_replacement, content, flags=re.DOTALL)

# 6. Add theme toggle button in create_integrated_title_bar
if 'self.theme_toggle' not in content:
    title_bar_pattern = r'(# Sidebar toggle button.*?title_layout\.addWidget\(self\.sidebar_toggle\))'
    title_bar_replacement = r'\1\n        \n        # Theme toggle button\n        self.theme_toggle = QPushButton()\n        self.theme_toggle.setIcon(self.create_theme_icon())\n        self.theme_toggle.setToolTip("Toggle Theme (Ctrl+D)")\n        self.theme_toggle.setProperty("class", "icon-button")\n        self.theme_toggle.setFixedSize(32, 32)\n        self.theme_toggle.clicked.connect(self.toggle_theme)\n        title_layout.addWidget(self.theme_toggle)'
    content = re.sub(title_bar_pattern, title_bar_replacement, content, flags=re.DOTALL)

# 7. Add keyboard shortcut for theme toggle
shortcuts_pattern = r'(# Toggle panel shortcut \(Ctrl\+T\).*?toggle_panel_shortcut\.activated\.connect\(self\.toggle_mirror_panel\))'
shortcuts_replacement = r'\1\n        \n        # Toggle theme shortcut (Ctrl+D)\n        theme_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)\n        theme_shortcut.activated.connect(self.toggle_theme)'
content = re.sub(shortcuts_pattern, shortcuts_replacement, content, flags=re.DOTALL)

# Write changes back to file
with open('app.py', 'w') as f:
    f.write(content)

print("Dark mode functionality has been fully implemented!")
print("You can now toggle between light and dark themes with Ctrl+D or using the theme toggle button in the title bar.") 