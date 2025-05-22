#!/usr/bin/env python3
import re

# Make a backup of the original file
import shutil
shutil.copy2('app.py', 'app.py.backup2')

with open('app.py', 'r') as f:
    content = f.read()

# Fix the missing stylesheet section by updating the problematic part
problem_pattern = r'stylesheet = f"""[\s\S]*?background-color: {UA\["selection_bg"\]};[\s\S]*?color: {UA\["selection_fg"\]};[\s\S]*?}}\s*QWidget#MirrorPanelContent QPushButton\.primary'
replacement = '''stylesheet = f"""
        QMainWindow {{
            background-color: {UA["window_bg"]};
            border: 1px solid {UA["border_medium"] if self.current_theme == 'dark' else UA["border_light"]};
            border-radius: 8px;
        }}
        
        QWidget#MirrorPanel QListWidget::item:selected {{
            background-color: {UA["selection_bg"]};
            color: {UA["selection_fg"]};
        }}
        
        QWidget#MirrorPanelContent QPushButton.primary'''

updated_content = re.sub(problem_pattern, replacement, content, flags=re.DOTALL)

with open('app.py', 'w') as f:
    f.write(updated_content)

print('Successfully fixed the stylesheet in app.py') 