import json
import os
import pymysql
import shutil
from tabulate import tabulate

if os.name == 'nt':
    import msvcrt
else:
    msvcrt = None

CONFIG_FILE = "db_templates.json"

RU_CHARS = "йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,ёЁ"
EN_CHARS = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?`~"
LAYOUT_MAPPING = str.maketrans(RU_CHARS, EN_CHARS)

USER_LOGS = []

def add_log(message):
    USER_LOGS.append(message)
    if len(USER_LOGS) > 2:
        USER_LOGS.pop(0)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def resize_window(cols=99, req_lines=35):
    if os.name == 'nt':
        # 1. Попытка через старый mode (для обычного cmd.exe)
        os.system(f'mode con: cols={cols} lines={req_lines}')
        # 2. Попытка через ANSI-последовательность
        print(f"\x1b[8;{req_lines};{cols}t", end='', flush=True)

def print_logs():
    if not USER_LOGS:
        return
    # Save current cursor position
    print("\033[s", end="", flush=True)
    
    term_size = shutil.get_terminal_size()
    num_logs = len(USER_LOGS)
    
    for i, log in enumerate(USER_LOGS):
        # Calculate row (lines is total height, rows are 1-indexed)
        row = term_size.lines - (num_logs - 1 - i)
        # \033[row;1H moves cursor, \033[K clears the line
        print(f"\033[{row};1H\033[K{log}", end="", flush=True)
        
    # Restore cursor position
    print("\033[u", end="", flush=True)

def get_input(prompt, mask=False):
    if msvcrt:
        print(prompt, end='', flush=True)
        chars = []
        while True:
            char = msvcrt.getwch()
            if char in ('\r', '\n'):
                print()
                break
            elif char == '\x08': # Backspace
                if chars:
                    chars.pop()
                    print('\b \b', end='', flush=True)
            elif char == '\x03': # Ctrl+C
                raise KeyboardInterrupt
            elif char in ('\xe0', '\x00'):
                msvcrt.getwch()
            else:
                translated_char = char.translate(LAYOUT_MAPPING)
                chars.append(translated_char)
                if mask:
                    print('*', end='', flush=True)
                else:
                    print(translated_char, end='', flush=True)
        return "".join(chars).strip()
    else:
        import getpass
        if mask:
            text = getpass.getpass(prompt).strip()
        else:
            text = input(prompt).strip()
        return text.translate(LAYOUT_MAPPING)

def load_templates():
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_templates(templates):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=4, ensure_ascii=False)

def connect_to_db(ip, port, user, password, database):
    try:
        print(f"Connecting to {ip}:{port} as user {user} to DB '{database}'...")
        connection = pymysql.connect(
            host=ip,
            port=int(port),
            user=user,
            password=password,
            database=database,
            charset='utf8mb4'
        )
        print("Successful connection!")
        explore_tables(connection, database)
        connection.close()
    except Exception as e:
        print(f"Connection error: {e}")

def manage_table(connection, db_name, table_name):
    while True:
        table_output = "(Table is empty)"
        req_lines = len(USER_LOGS) + 15
        req_cols = 99
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 50")
                rows = cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    table_output = tabulate(rows, headers=columns, tablefmt="grid")
                    table_lines = table_output.split('\n')
                    req_cols = max((len(line) for line in table_lines), default=0) + 4
                    req_lines = len(table_lines) + len(USER_LOGS) + 13
        except Exception as e:
            table_output = f"(Error reading table: {e})"
            req_lines = len(table_output.split('\n')) + len(USER_LOGS) + 13
            
        resize_window(max(99, req_cols), req_lines)
        clear_screen()
        
        print(f"=== Table '{table_name}' in DB '{db_name}' ===")
        print(table_output)
            
        print("\nActions:")
        print("1. Add column")
        print("2. Delete column")
        print("3. Add row")
        print("4. Delete row")
        
        print("-" * 20)
        print("b. Return to tables list\n")
        
        # Reserve lines for logs below the prompt so ANSI restoration doesn't cause overlap
        if USER_LOGS:
            print("\n" * (len(USER_LOGS) + 2), end="")
            print(f"\033[{len(USER_LOGS) + 2}A", end="") # Move cursor back up (gap + logs)
            
        print_logs()
        
        choice = get_input("Select action: ").lower()
        
        if choice == 'b':
            add_log(f"Returned to tables list")
            resize_window(99, 35)
            break
            
        elif choice == '1':
            clear_screen()
            print(f"--- Add column to '{table_name}' ---")
            col_name = get_input("Enter new column name: ")
            if not col_name:
                add_log("Add column cancelled")
                continue
            col_type = get_input("Enter column type (e.g. VARCHAR(255), INT): ")
            if not col_type:
                add_log("Add column cancelled")
                continue
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type}")
                    connection.commit()
                    add_log(f"Column '{col_name}' added to '{table_name}'")
            except Exception as e:
                add_log(f"Error adding column: {e}")
                
        elif choice == '2':
            clear_screen()
            print(f"--- Delete column from '{table_name}' ---")
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns_desc = cursor.fetchall()
            except Exception as e:
                add_log(f"Error reading columns: {e}")
                continue
                
            for i, col in enumerate(columns_desc):
                print(f"{i+1}. {col[0]} ({col[1]})")
                
            print("-" * 20)
            col_input = get_input("Enter column number or name to delete (b to cancel): ")
            if col_input.lower() == 'b' or not col_input:
                add_log("Delete column cancelled")
                continue
                
            col_name = col_input
            if col_input.isdigit() and 1 <= int(col_input) <= len(columns_desc):
                col_name = columns_desc[int(col_input) - 1][0]
                
            confirm = get_input(f"Are you sure you want to delete column '{col_name}'? (y/n): ").lower()
            if confirm == 'y':
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f"ALTER TABLE `{table_name}` DROP COLUMN `{col_name}`")
                        connection.commit()
                        add_log(f"Column '{col_name}' deleted from '{table_name}'")
                except Exception as e:
                    add_log(f"Error deleting column: {e}")
                    
        elif choice == '3':
            clear_screen()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns_desc = cursor.fetchall()
                    
                cols_to_insert = []
                vals_to_insert = []
                print(f"--- Add row to '{table_name}' ---")
                print("Leave empty to skip a column (useful for AUTO_INCREMENT).\n")
                
                for col in columns_desc:
                    col_name = col[0]
                    col_type_str = col[1]
                    val = get_input(f"Value for `{col_name}` ({col_type_str}): ")
                    if val:
                        cols_to_insert.append(f"`{col_name}`")
                        vals_to_insert.append(val)
                        
                if cols_to_insert:
                    placeholders = ", ".join(["%s"] * len(vals_to_insert))
                    cols_str = ", ".join(cols_to_insert)
                    query = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})"
                    
                    with connection.cursor() as cursor:
                        cursor.execute(query, tuple(vals_to_insert))
                        connection.commit()
                        add_log(f"Row added to '{table_name}'")
                else:
                    add_log("Insert skipped: no values provided")
                    
            except Exception as e:
                add_log(f"Error adding row: {e}")
                
        elif choice == '4':
            clear_screen()
            print(f"--- Delete row from '{table_name}' ---")
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns_desc = cursor.fetchall()
            except Exception as e:
                add_log(f"Error reading columns: {e}")
                continue
                
            print("Select column to match for deletion:")
            for i, col in enumerate(columns_desc):
                print(f"{i+1}. {col[0]} ({col[1]})")
                
            print("-" * 20)
            col_input = get_input("Enter column number or name (b to cancel): ")
            if col_input.lower() == 'b' or not col_input:
                add_log("Delete row cancelled")
                continue
                
            col_name = col_input
            if col_input.isdigit() and 1 <= int(col_input) <= len(columns_desc):
                col_name = columns_desc[int(col_input) - 1][0]
                
            val = get_input(f"Enter value for `{col_name}` to delete: ")
            if not val:
                add_log("Delete row cancelled")
                continue
                
            confirm = get_input(f"Are you sure you want to delete row where `{col_name}`='{val}'? (y/n): ").lower()
            if confirm == 'y':
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f"DELETE FROM `{table_name}` WHERE `{col_name}` = %s", (val,))
                        affected = cursor.rowcount
                        connection.commit()
                        add_log(f"Deleted {affected} row(s) from '{table_name}'")
                except Exception as e:
                    add_log(f"Error deleting row: {e}")
                    
        else:
            add_log(f"Invalid choice: {choice}")

def explore_tables(connection, db_name):
    while True:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            add_log(f"Error retrieving tables list: {e}")
            return

        req_lines = len(tables) + len(USER_LOGS) + 14
        resize_window(99, req_lines)
        
        clear_screen()
        print(f"=== Tables in DB: {db_name} ===")
        for i, table in enumerate(tables):
            print(f"{i+1}. {table}")
        print("-" * 20)
        print("c. Create new table")
        print("d. Delete table")
        
        print("\nb. Return to main menu\n")
        
        # Reserve lines for logs below the prompt so ANSI restoration doesn't cause overlap
        if USER_LOGS:
            print("\n" * (len(USER_LOGS) + 2), end="")
            print(f"\033[{len(USER_LOGS) + 2}A", end="") # Move cursor back up (gap + logs)
            
        print_logs()
        
        choice = get_input("Choose action or table index: ").lower()
        if choice == 'b':
            add_log("Returned to main menu")
            break
        
        if choice == 'c':
            clear_screen()
            new_table_name = get_input("Enter new table name: ")
            if new_table_name:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f"CREATE TABLE `{new_table_name}` (id INT AUTO_INCREMENT PRIMARY KEY)")
                        connection.commit()
                        add_log(f"Table '{new_table_name}' created")
                except Exception as e:
                    add_log(f"Error creating table: {e}")
            continue

        if choice == 'd':
            clear_screen()
            print(f"=== Delete table in DB '{db_name}' ===")
            for i, table in enumerate(tables):
                print(f"{i+1}. {table}")
            print("-" * 20)
            
            table_to_del_input = get_input("Enter table number or name to delete (b to cancel): ")
            if table_to_del_input.lower() == 'b' or not table_to_del_input:
                add_log("Delete table cancelled")
                continue
                
            table_to_del = table_to_del_input
            if table_to_del_input.isdigit() and 1 <= int(table_to_del_input) <= len(tables):
                table_to_del = tables[int(table_to_del_input) - 1]
            
            if table_to_del:
                confirm = get_input(f"Are you sure you want to delete table '{table_to_del}'? (y/n): ").lower()
                if confirm == 'y':
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(f"DROP TABLE `{table_to_del}`")
                            connection.commit()
                            add_log(f"Table '{table_to_del}' deleted")
                    except Exception as e:
                        add_log(f"Error deleting table: {e}")
            continue
        
        if choice.isdigit() and 1 <= int(choice) <= len(tables):
            selected_table = tables[int(choice) - 1]
            manage_table(connection, db_name, selected_table)
        else:
            add_log(f"Invalid choice: {choice}")

LOGO = r"""
 ██████╗  █████╗ ████████╗ █████╗ ██████╗ ███████╗███████╗    ██╗   ██╗████████╗██╗██╗     ███████╗
 ██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝    ██║   ██║╚══██╔══╝██║██║     ██╔════╝
 ██║  ██║███████║   ██║   ███████║██████╔╝███████╗█████╗      ██║   ██║   ██║   ██║██║     ███████╗
 ██║  ██║██╔══██║   ██║   ██╔══██║██╔══██╗╚════██║██╔══╝      ██║   ██║   ██║   ██║██║     ╚════██║
 ██████╔╝██║  ██║   ██║   ██║  ██║██████╔╝███████║███████╗    ╚██████╔╝   ██║   ██║███████╗███████║
 ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝     ╚═════╝    ╚═╝   ╚═╝╚══════╝╚══════╝
"""

def main():
    while True:
        templates = load_templates()
        req_lines = len(templates) + len(USER_LOGS) + 24
        resize_window(99, req_lines)
        
        clear_screen()
        print(LOGO)
        print(f"=== Main menu ===")
        print("1. Connect to DB (manual)")
        print("2. Create template")
        print("3. Delete template")
        
        print("-" * 20)
        template_start_index = 4
        for i, t in enumerate(templates):
            db_name = t.get('database', 'No DB specified')
            print(f"{template_start_index + i}. Connect ({t['name']}) - {t['ip']}:{t['port']} [{db_name}]")
        
        print("\nq. Exit\n")
        
        # Reserve lines for logs below the prompt so ANSI restoration doesn't cause overlap
        if USER_LOGS:
            print("\n" * (len(USER_LOGS) + 2), end="")
            print(f"\033[{len(USER_LOGS) + 2}A", end="") # Move cursor back up (gap + logs)
            
        print_logs()
        
        choice = get_input("Select action: ").lower()
        
        if choice == 'q':
            break
            
        if choice == '1':
            clear_screen()
            print("--- Manual Connection ---")
            ip = get_input("IP: ")
            port = get_input("Port: ")
            user = get_input("User: ")
            password = get_input("Password: ", mask=True)
            database = get_input("Database: ")
            add_log(f"Manual connection to {database}")
            connect_to_db(ip, port, user, password, database)
            
        elif choice == '2':
            clear_screen()
            print("--- Create Template ---")
            name = get_input("Name: ")
            ip = get_input("IP: ")
            port = get_input("Port: ")
            user = get_input("User: ")
            password = get_input("Password: ", mask=True)
            database = get_input("Database: ")
            
            templates.append({
                "name": name,
                "ip": ip,
                "port": port,
                "user": user,
                "password": password,
                "database": database
            })
            save_templates(templates)
            add_log(f"Template '{name}' created")
            
        elif choice == '3':
            if not templates:
                add_log("Attempted to delete template when none exist")
                continue
                
            clear_screen()
            print("--- Delete Template ---")
            for i, t in enumerate(templates):
                db_name = t.get('database', 'No DB specified')
                print(f"{i+1}. {t['name']} ({t['ip']}:{t['port']}) [{db_name}]")
                
            del_choice = get_input("Select template number to delete (b to cancel): ").lower()
            if del_choice == 'b':
                add_log("Delete action cancelled")
                continue
                
            if del_choice.isdigit() and 1 <= int(del_choice) <= len(templates):
                deleted = templates.pop(int(del_choice) - 1)
                save_templates(templates)
                add_log(f"Template '{deleted['name']}' deleted")
            else:
                add_log(f"Invalid delete choice: {del_choice}")
                
        elif choice.isdigit():
            choice_num = int(choice)
            if template_start_index <= choice_num < template_start_index + len(templates):
                idx = choice_num - template_start_index
                t = templates[idx]
                
                db_name = t.get('database')
                if not db_name:
                    db_name = get_input(f"Template '{t['name']}' has no database specified. Enter DB name: ")
                
                add_log(f"Connecting to '{t['name']}'")
                connect_to_db(t['ip'], t['port'], t['user'], t['password'], db_name)
            else:
                add_log(f"Invalid menu item: {choice}")
        else:
            add_log(f"Invalid input: {choice}")

if __name__ == "__main__":
    main()
