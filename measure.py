import os

def measure_logo():
    path = r'e:\Projects\Code\Python\Short functional scripts\Database-Utils\db_manager.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple extraction (adjusting for the user's manual changes)
    start_str = 'LOGO = r"""'
    start = content.find(start_str) + len(start_str)
    end = content.find('"""', start)
    logo = content[start:end].strip('\n')
    lines = logo.split('\n')
    
    max_w = 0
    for line in lines:
        # We need the visual width, but since we use standard mono chars mostly?
        # Let's see the chars. The block chars are usually double width in some fonts
        # but in measuring 'len(line)' in Python vs terminal display...
        max_w = max(max_w, len(line))
    
    print(f"Max width: {max_w}")

if __name__ == "__main__":
    measure_logo()
