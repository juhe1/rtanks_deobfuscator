"""
This script will rename all names that are obuscated with new random name. 
So for example "§5L§" will become "deobfuscated_name_1".
"""

# TODO: deobfuscate also the path

from typing import Dict, List
import os

INPUT_SOURCE_PATH:str = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\rtanks_sources"
OUTPUT_SOURCE_PATH:str = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\rtanks_sources_cleaned"

OBFUSCATION_IDENTIFIER_CHAR:str = "§"
ALLOWED_FILE_TYPES:List[str] = ["as"]
NEW_NAME = "deobfuscated_name"

new_name_by_old_name:Dict[str, str] = {} 
current_name_id = 0

def deobfuscate_name(obfuscated_name:str) -> str:
    global current_name_id

    if obfuscated_name in new_name_by_old_name:
        return new_name_by_old_name[obfuscated_name]
    else:
        new_name = NEW_NAME + "_" + str(current_name_id)
        current_name_id += 1
        new_name_by_old_name[obfuscated_name] = new_name
        return new_name

def edit_line(line:str) -> str:
    global current_name_id
    obfuscated_names = []
    inside_obfuscated_name = False

    for char in line:
        if char == OBFUSCATION_IDENTIFIER_CHAR:
            inside_obfuscated_name = not inside_obfuscated_name
            
            if inside_obfuscated_name:
                obfuscated_names.append("")
            else:
                obfuscated_names[-1] += OBFUSCATION_IDENTIFIER_CHAR

        if inside_obfuscated_name:
            obfuscated_names[-1] += char

    for obfuscated_name in obfuscated_names:
        new_name = deobfuscate_name(obfuscated_name)
        line = line.replace(obfuscated_name, new_name)

    return line

def create_modified_file(dir_relative_path:str, file_name) -> None:
    new_text = ""

    with open(INPUT_SOURCE_PATH + dir_relative_path + "\\" + file_name, "r", encoding="utf-8") as file:
        for line in file:
            new_text += edit_line(line)

    if file_name[0] == OBFUSCATION_IDENTIFIER_CHAR:
        obfuscated_part = "".join(file_name.split(".")[:-1])
        file_name = file_name.replace(obfuscated_part, deobfuscate_name(obfuscated_part))

    new_path = (OUTPUT_SOURCE_PATH + dir_relative_path).replace("\\", "/")

    for folder_name in new_path.split("/"):
        if not folder_name[0] == OBFUSCATION_IDENTIFIER_CHAR:
            continue

        deobfuscated_folder_name = deobfuscate_name(folder_name)
        new_path = new_path.replace(folder_name, deobfuscated_folder_name)

    os.makedirs(new_path, exist_ok=True)

    with open(new_path + "\\" + file_name, 'w', encoding="utf-8") as file:
        file.write(new_text)

def loop_all_files() -> None:
    for root, directories, files in os.walk(INPUT_SOURCE_PATH):
        for filename in files:
            if not filename.split(".")[-1] in ALLOWED_FILE_TYPES:
                continue

            file_path = os.path.join(root, filename)
            dir_relative_path = root.replace(INPUT_SOURCE_PATH, "")
            create_modified_file(dir_relative_path, filename)

if __name__ == "__main__":
    loop_all_files()
