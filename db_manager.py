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

def resize_window():
    if os.name == 'nt':
        # 1. Попытка через старый mode (для обычного cmd.exe)
        # Устанавливаем ширину ровно в 99 символов под размер логотипа
        os.system('mode con: cols=99 lines=35')
        # 2. Попытка через ANSI-последовательность
        print("\x1b[8;35;99t", end='', flush=True)

def print_logs():
    if not USER_LOGS:
        return
    # Save current cursor position
    print("\033[s", end="", flush=True)
    
    term_size = shutil.get_terminal_size()
    # Number of log lines to show (max 2)
    num_logs = len(USER_LOGS)
    
    for i, log in enumerate(USER_LOGS):
        # Calculate row (lines is total height, rows are 1-indexed)
        # We want the last num_logs lines
        row = term_size.lines - (num_logs - 1 - i)
        # \033[row;colH moves cursor, \033[K clears the line
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

def explore_tables(connection, db_name):
    while True:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            add_log(f"Error retrieving tables list: {e}")
            return

        clear_screen()
        print(f"\n=== Tables in DB: {db_name} ===")
        for i, table in enumerate(tables):
            print(f"{i}. {table}")
        print("-" * 20)
        print("11. Create new table")
        print("12. Delete table")
        
        print("\nb. Return to main menu")
        print_logs()
        
        choice = get_input("\n\nChoose action or table index: ").lower()
        if choice == 'b':
            add_log("Returned to main menu")
            break
        
        if choice == '11':
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

        if choice == '12':
            clear_screen()
            table_to_del_input = get_input("Enter table name to delete (or its index): ")
            table_to_del = table_to_del_input
            if table_to_del_input.isdigit() and 0 <= int(table_to_del_input) < len(tables):
                table_to_del = tables[int(table_to_del_input)]
            
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
        
        if choice.isdigit() and 0 <= int(choice) < len(tables):
            selected_table = tables[int(choice)]
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT * FROM `{selected_table}` LIMIT 50")
                    rows = cursor.fetchall()
                    add_log(f"Viewed table '{selected_table}'")
                    
                    columns = [desc[0] for desc in cursor.description]
                    clear_screen()
                    print(f"\n=== Content of {selected_table} (up to 50 rows) ===")
                    print(tabulate(rows, headers=columns, tablefmt="grid"))
                    get_input("\nPress Enter to continue...")
            except Exception as e:
                add_log(f"Error reading table {selected_table}: {e}")
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
    resize_window()
    while True:
        templates = load_templates()
        clear_screen()
        print(LOGO)
        print(f"=== Main menu ===")
        print("0. Connect to DB (manual)")
        print("1. Create template")
        print("2. Delete template")
        
        print("-" * 20)
        template_start_index = 3
        for i, t in enumerate(templates):
            db_name = t.get('database', 'No DB specified')
            print(f"{template_start_index + i}. Connect ({t['name']}) - {t['ip']}:{t['port']} [{db_name}]")
        
        print("\nq. Exit")
        print_logs()
        
        choice = get_input("\n\nSelect action: ").lower()
        
        if choice == 'q':
            break
            
        if choice == '0':
            clear_screen()
            print("--- Manual Connection ---")
            ip = get_input("IP: ")
            port = get_input("Port: ")
            user = get_input("User: ")
            password = get_input("Password: ", mask=True)
            database = get_input("Database: ")
            add_log(f"Manual connection to {database}")
            connect_to_db(ip, port, user, password, database)
            
        elif choice == '1':
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
            
        elif choice == '2':
            if not templates:
                add_log("Attempted to delete template when none exist")
                continue
                
            clear_screen()
            print("--- Delete Template ---")
            for i, t in enumerate(templates):
                db_name = t.get('database', 'No DB specified')
                print(f"{i}. {t['name']} ({t['ip']}:{t['port']}) [{db_name}]")
                
            del_choice = get_input("Select template number to delete (b to cancel): ").lower()
            if del_choice == 'b':
                add_log("Delete action cancelled")
                continue
                
            if del_choice.isdigit() and 0 <= int(del_choice) < len(templates):
                deleted = templates.pop(int(del_choice))
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
