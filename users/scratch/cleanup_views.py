
import os

path = r'c:\Users\denisdev\Documents\tournament_platform\core\users\views.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# I will find the last occurrence of 'def home' and assume everything before it is mostly safe.
# Actually, I'll just find the first occurrence of all standard functions and keep them.

seen_defs = set()
new_lines = []
skip_mode = False

import re

def_pattern = re.compile(r'^def\s+(\w+)\(')
login_required_pattern = re.compile(r'^@login_required')

buffer = []
for line in lines:
    m = def_pattern.match(line)
    if m:
        func_name = m.group(1)
        if func_name in seen_defs:
            # Check if this is a known duplicate we want to skip
            # For now, let's keep only the FIRST occurrence of everything EXCEPT the ones we specifically fixed.
            # Wait, that's dangerous.
            
            # Let's try a different approach: I KNOW what the file SHOULD look like from 1500 onwards.
            pass

# ALRIGHT, I will just write the Correct implementation of the end of the file.
# I'll find where the mess starts.
# It seems the mess starts after 'def delete_task'.

# Let's find the index of the FIRST 'def delete_task' and keep everything up to its end.
# Then I'll append the correct versions of everything else.

def find_func_start(name, lines):
    for i, line in enumerate(lines):
        if f'def {name}(' in line:
            return i
    return -1

delete_task_start = find_func_start('delete_task', lines)
# It probably ends around 20 lines later.

# This is still risky.
