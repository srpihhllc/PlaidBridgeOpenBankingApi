#!/usr/bin/env python3
"""Add extend_existing=True to all SQLAlchemy models."""
import os
import re
from pathlib import Path

def add_extend_existing_to_model(file_path):
    """Add __table_args__ with extend_existing to a model file if not present."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find class definitions that inherit from db.Model or Model
    class_pattern = r'(class\s+\w+\([^)]*\b(?:db\.)?Model[^)]*\):\s*\n\s*__tablename__\s*=\s*["\'][^"\']+["\'])'
    
    modified = False
    def replacer(match):
        nonlocal modified
        class_def = match.group(1)
        # Check if extend_existing is already present
        if 'extend_existing' in class_def or '__table_args__' in content[match.start():match.start()+500]:
            return class_def
        
        # Add __table_args__
        modified = True
        return class_def + '\n    __table_args__ = {"extend_existing": True}'
    
    new_content = re.sub(class_pattern, replacer, content)
    
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

# Process all model files in both app trees
model_dirs = [
    Path('app/models'),
    Path('PlaidBridgeOpenBankingApi/app/models'),
]

count = 0
for model_dir in model_dirs:
    if not model_dir.exists():
        continue
    
    for py_file in model_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue
        
        if add_extend_existing_to_model(py_file):
            print(f"✅ Added extend_existing to {py_file}")
            count += 1
        else:
            print(f"⏭️  Skipped {py_file} (already has extend_existing or no model found)")

print(f"\n✨ Processed {count} files")
