from collections.abc import Callable
from dataclasses import dataclass
from os.path import join
from typing import Dict, List, IO

import os
import json
import pprint
import pyperclip # NOTE: Only used in debugging. So remove if you want.

ALLOWED_FILE_TYPES:List[str] = ["as"]
TEST_SOURCE_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"

@dataclass
class ActionScriptClassInfo:
    name:str
    implements:List[str]
    extends:str
    visibility:str

@dataclass
class ActionScriptVarInfo:
    name:str
    visibility:str
    type:str
    static:bool

@dataclass
class ActionScriptFunctionInfo:
    name:str
    visibility:str
    static:bool
    return_type:str
    param_names:List[str]
    param_types:List[str]
    line_count:int

class ActionScriptFileParser:
    def __init__(self, file_path:str) -> None:
        self.package_name:str = ""
        self.imports:List[str] = []
        self.class_infos:List[ActionScriptClassInfo] = []
        self.global_var_infos:List[ActionScriptVarInfo] = []
        self.function_infos:List[ActionScriptFunctionInfo] = []

        self.parse_file(file_path)

    def __str__(self) -> str:
        return f"""
package_name: {self.package_name}
imports: {self.imports}
class_infos: {self.class_infos}
global_var_infos: {self.global_var_infos}
function_infos: {self.function_infos}
        """

    def get_as_dictionary(self) -> Dict:
        package_name = [str(self.package_name)]
        imports = [str(x) for x in self.imports]
        class_infos = [str(x) for x in self.class_infos]
        global_var_infos = [str(x) for x in self.global_var_infos]
        function_infos = [str(x) for x in self.function_infos]

        return {
            "package_name":package_name,
            "imports":imports,
            "class_infos":class_infos,
            "global_var_infos":global_var_infos,
            "function_infos":function_infos
        }

    def parse_package(self, line_splitted_by_space:List[str], word_index:int) -> None:
        if word_index + 1 < len(line_splitted_by_space):
            self.package_name = line_splitted_by_space[word_index + 1]
    
    def parse_import(self, line_splitted_by_space:List[str], word_index:int) -> None:
        self.imports.append(line_splitted_by_space[word_index + 1][:-1])

    def parse_class_definition(self, line_splitted_by_space:List[str], word_index:int) -> None:
        IMPLEMENTS_TEXT = "implements"
        EXTENDS_TEXT = "extends"
        implements = []
        extends = ""
        
        if IMPLEMENTS_TEXT in line_splitted_by_space:
            implements_index = line_splitted_by_space.index(IMPLEMENTS_TEXT)
            while True:
                implements_index += 1
                implements_name = line_splitted_by_space[implements_index]

                if implements_name[-1] == ",":
                    implements.append(implements_name[:-1])
                    continue

                implements.append(implements_name)
                break

        if EXTENDS_TEXT in line_splitted_by_space:
            extends_index = line_splitted_by_space.index(EXTENDS_TEXT)
            extends = line_splitted_by_space[extends_index + 1]

        class_info = ActionScriptClassInfo(
            name=line_splitted_by_space[word_index + 1],
            implements=implements,
            extends=extends,
            visibility=line_splitted_by_space[0]
        )

        self.class_infos.append(class_info)

    def is_static(self, line_splitted_by_space:List[str]) -> bool:
        return "static" in line_splitted_by_space

    def parse_visibility(self, line_splitted_by_space:List[str]) -> str:
        if line_splitted_by_space[0] in ["public", "private", "protected", "internal"]:
            return line_splitted_by_space[0]
        return "public"

    def parse_var_definition(self, line_splitted_by_space:List[str], word_index:int) -> None:
        name_and_type = line_splitted_by_space[word_index + 1][:-1].split(":")
        name = name_and_type[0]
        type = name_and_type[1]
        static = self.is_static(line_splitted_by_space)        
        visibility = self.parse_visibility(line_splitted_by_space)        

        var_info = ActionScriptVarInfo(
            name=name,
            type=type,
            visibility=visibility,
            static=static
        )
        self.global_var_infos.append(var_info)

    def parse_function_definition(self, line_splitted_by_space:List[str], word_index:int, file:IO) -> None:
        OPENING_BRACE = "()"[0] # the "()"[0] is for my stupid lsp which will freak out if i dont close open parenthesis in string
        CLOSING_BRACE = "()"[1] # the "()"[1] is for my stupid lsp which will freak out if i dont close open parenthesis in string

        name = line_splitted_by_space[word_index + 1].split(OPENING_BRACE)[0]
        visibility = self.parse_visibility(line_splitted_by_space)
        static = self.is_static(line_splitted_by_space)

        param_names = []
        param_types = []

        line = "".join(line_splitted_by_space)
        params_string = line.split(OPENING_BRACE)[1].split(CLOSING_BRACE)[0]
        params = params_string.split(",")

        # if there is params, then parse them
        if not params[0] == "":
            for param in params:
                param_names.append(param.split(":")[0])
                param_types.append(param.split(":")[1])

        return_type = ""

        # parse return type if the function has one
        if line_splitted_by_space[-2] == ":":
            return_type = line_splitted_by_space[-1]

        OPENING_CURLY_BRACE = "{}"[0] # the "{}"[0] is for my stupid lsp which will freak out if i dont close open parenthesis in string
        CLOSING_CURLY_BRACE = "{}"[1] # the "{}"[1] is for my stupid lsp which will freak out if i dont close open parenthesis in string
        function_line_count = 0
        scope_depth = 0
        
        for line in file:
            if OPENING_CURLY_BRACE in line:
                scope_depth += 1
            if CLOSING_CURLY_BRACE in line:
                scope_depth -= 1

            if scope_depth == 0:
                break

            function_line_count += 1

        function_info = ActionScriptFunctionInfo(
            name=name,
            visibility=visibility,
            static=static,
            param_names=param_names,
            param_types=param_types,
            return_type=return_type,
            line_count=function_line_count
        )

        self.function_infos.append(function_info)
        
    def parse_line(self, line:str, file:IO) -> None:
        line_without_leading_or_trailing_whitespace = line.strip()
        line_splitted_by_space = line_without_leading_or_trailing_whitespace.split(" ")

        for index, word in enumerate(line_splitted_by_space):
            match word:
                case "package":
                    self.parse_package(line_splitted_by_space, index)
                case "import":
                    self.parse_import(line_splitted_by_space, index)
                case "class":
                    self.parse_class_definition(line_splitted_by_space, index)
                case "var":
                    self.parse_var_definition(line_splitted_by_space, index)
                case "function":
                    self.parse_function_definition(line_splitted_by_space, index, file)
                case _:
                    pass

    def parse_file(self, file_path:str) -> None:
        with open(file_path, "r") as file:
            for line in file:
                self.parse_line(line, file)

def parse_pass(source_path, file_data_parse_functin:Callable) -> None:
    for root, directories, files in os.walk(source_path):
        for filename in files:
            if not filename.split(".")[-1] in ALLOWED_FILE_TYPES:
                continue

            file_path = os.path.join(root, filename)
            as_file_parser = ActionScriptFileParser(file_path)

            as_file_parser_as_dic = as_file_parser.get_as_dictionary()

            # Copy the string to the clipboard
            pyperclip.copy(json.dumps(as_file_parser_as_dic))
            print("copied to clipboard!")

            # TODO: do something with the data

if __name__ == "__main__":
    def none():
        return

    parse_pass(TEST_SOURCE_PATH, none)
