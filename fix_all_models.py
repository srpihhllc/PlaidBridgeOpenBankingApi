#!/usr/bin/env python3
"""Add extend_existing=True to ALL models, handling both tuple and dict __table_args__."""
import os
import re
from pathlib import Path

def process_model_file(file_path):
    """Add extend_existing to model file, handling all __table_args__ formats."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix imports first - change absolute to relative
    content = re.sub(r'^from app\.extensions import db$', r'from ..extensions import db', content, flags=re.MULTILINE)
    content = re.sub(r'^from app import db$', r'from ..extensions import db', content, flags=re.MULTILINE)
    
    # Find models with __tablename__ but no __table_args__
    pattern_no_args = r'(class\s+\w+\([^)]*\b(?:db\.)?Model[^)]*\):\s*\n\s*__tablename__\s*=\s*["\'][^"\']+["\'])\s*\n(\s+(?!__table_args__))'
    
    def add_table_args(match):
        class_and_table = match.group(1)
        next_line_indent = match.group(2)
        return f'{class_and_table}\n    __table_args__ = {{"extend_existing": True}}\n{next_line_indent}'
    
    content = re.sub(pattern_no_args, add_table_args, content)
    
    # Find models with tuple __table_args__ and add extend_existing dict at end
    pattern_tuple_args = r'(__table_args__\s*=\s*\([^)]+)\)(\s*\n)'
    
    def fix_tuple_args(match):
        args_part = match.group(1)
        newline = match.group(2)
        if 'extend_existing' in args_part:
            return match.group(0)  # already has it
        return f'{args_part},\n        {{"extend_existing": True}},\n    ){newline}'
    
    content = re.sub(pattern_tuple_args, fix_tuple_args, content)
    
    # Find models with dict __table_args__ and add extend_existing
    pattern_dict_args = r'(__table_args__\s*=\s*\{)([^}]+)(\})'
    
    def fix_dict_args(match):
        start = match.group(1)
        dict_content = match.group(2)
        end = match.group(3)
        if 'extend_existing' in dict_content:
            return match.group(0)  # already has it
        return f'{start}{dict_content}, "extend_existing": True{end}'
    
    content = re.sub(pattern_dict_args, fix_dict_args, content)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Process all model files
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
        
        if process_model_file(py_file):
            print(f"✅ {py_file}")
            count += 1

print(f"\n✨ Updated {count} files")
