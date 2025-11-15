"""
Fix all indentation issues in the _get_new_user_dashboard_data function
"""
import re

with open('routes/dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the function
function_pattern = r'(async def _get_new_user_dashboard_data\([^)]+\)[^:]+:.*?)(    except HTTPException:)'
match = re.search(function_pattern, content, re.DOTALL)

if match:
    before_function = content[:match.start(1)]
    function_body = match.group(1)
    after_function = content[match.start(2):]
    
    # Fix indentation issues in function body
    lines = function_body.split('\n')
    fixed_lines = []
    in_outer_try = False
    
    for i, line in enumerate(lines):
        # Check if we're at the outer try block
        if 'try:' in line and i > 0 and '# Initialize cache status tracking' in lines[i+1]:
            in_outer_try = True
            fixed_lines.append(line)
        elif in_outer_try and line.strip().startswith('except ') and 'HTTPException' not in line:
            # This is an inner except, keep as is
            fixed_lines.append(line)
        elif in_outer_try and not line.strip().startswith('#') and line.strip():
            # Check if line needs more indentation
            current_indent = len(line) - len(line.lstrip())
            if current_indent == 4:  # Base function indent, needs to be inside try
                fixed_lines.append('    ' + line)
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    # Reconstruct
    new_content = before_function + '\n'.join(fixed_lines) + after_function
    
    with open('routes/dashboard.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Fixed indentation!")
else:
    print("Could not find function")
