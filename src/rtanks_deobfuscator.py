from collections.abc import Callable
from dataclasses import dataclass
from os.path import join
from typing import Dict, List, IO

import os
import json
import pyperclip # NOTE: Only used in debugging. So remove if you want.

ALLOWED_FILE_TYPES:List[str] = ["as"]
TEST_SOURCE_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"

# Names are taken from the reference project. So when we are deobfuscating rtanks, this path should countain mytanks sources.
REFERENCE_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"

# Target project should contain sources that we are trying to deobfuscate. 
TARGET_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"


@dataclass
class ActionScriptClassData:
    name:str
    implements:List[str]
    extends:str
    visibility:str


@dataclass
class ActionScriptVarData:
    name:str
    visibility:str
    type:str
    static:bool


@dataclass
class ActionScriptFunctionData:
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
        self.class_infos:List[ActionScriptClassData] = []
        self.global_var_infos:List[ActionScriptVarData] = []
        self.function_infos:List[ActionScriptFunctionData] = []

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

        class_info = ActionScriptClassData(
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

        var_info = ActionScriptVarData(
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

        function_info = ActionScriptFunctionData(
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


class ProjectSources:
    def __init__(self) -> None:
        self.actionscript_file_parsers:List[ActionScriptFileParser] = []
        self.new_name_by_old_name:Dict[str, str] = {}

    def get_new_name(self, old_name:str) -> str:
        return self.new_name_by_old_name[old_name]


class BasicImportVarFunctionDeobfuscationPass:
    """
    This pass will find files whose import, variable and function signatures and counts matches.
    """

    def __init__(self, reference_project:ProjectSources, target_project:ProjectSources) -> None:
        self.reference_project:ProjectSources = reference_project
        self.target_project:ProjectSources = target_project

        self.reference_project_action_script_files_by_import_count:Dict[int, List[ActionScriptFileParser]] = self.sort_action_script_file_parsers_by_import_count(reference_project)
        self.target_project_action_script_files_by_import_count:Dict[int, List[ActionScriptFileParser]] = self.sort_action_script_file_parsers_by_import_count(target_project)

    def sort_action_script_file_parsers_by_import_count(self, project:ProjectSources) -> Dict[int, List[ActionScriptFileParser]]:
        out = {}
        for action_script_file_parser in project.actionscript_file_parsers:
            import_count = len(action_script_file_parser.imports)

            if not import_count in out:
                out[import_count] = []

            out[import_count].append(action_script_file_parser)

        return out

    def deobfuscate(self) -> None:
        for action_script_file_parse in self.target_project.actionscript_file_parsers:
            import_count = len(action_script_file_parse.imports)
            reference_script_file_parsers_with_same_import_counts = self.reference_project_action_script_files_by_import_count[import_count]
            
            for reference_script_file_parsers_with_same_import_count in reference_script_file_parsers_with_same_import_counts:
                #reference_script_file_parsers_with_same_import_count.

def parse_project_sources(source_path:str) -> ProjectSources:
    sources = ProjectSources()

    for root, directories, files in os.walk(source_path):
        for filename in files:
            if not filename.split(".")[-1] in ALLOWED_FILE_TYPES:
                continue

            file_path = os.path.join(root, filename)
            as_file_parser = ActionScriptFileParser(file_path)
            sources.actionscript_file_parsers.append(as_file_parser)

    return sources

def test_action_script_file_parser() -> None:
    # Copy the string to the clipboard
    sources = parse_project_sources(TEST_SOURCE_PATH)
    action_script_file_datas = [x.get_as_dictionary() for x in sources.actionscript_file_parsers]
    
    pyperclip.copy(json.dumps(action_script_file_datas))
    print("copied to clipboard!")

def main() -> None:
    reference_project = parse_project_sources(REFERENCE_PROJECT_PATH)
    target_project = parse_project_sources(TARGET_PROJECT_PATH)

if __name__ == "__main__":
    #test_action_script_file_parser()
    main()
