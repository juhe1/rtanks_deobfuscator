from collections.abc import Callable
from dataclasses import dataclass
from os.path import join
from typing import Dict, List, IO

import os
import json
from typing_extensions import Tuple
import pyperclip # NOTE: Only used in debugging. So remove if you want.

ALLOWED_FILE_TYPES:List[str] = ["as"]
DEFAULT_DEOBFUSCATED_NAME = "deobfuscated_name"
TEST_SOURCE_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"

# Names are taken from the reference project. So when we are deobfuscating rtanks, this path should countain mytanks sources.
REFERENCE_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"

# Target project should contain sources that we are trying to deobfuscate. 
TARGET_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\test_data"

FUNCTION_LINE_COUNT_TOLERANCE = 2


class Utils:
    @staticmethod
    def within_tolerance(num1:int, num2:int, tolerance:int) -> bool:
        return abs(num1 - num2) <= tolerance


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
        package_name = str(self.package_name)
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

    def is_name_already_deobfuscated(self, name:str) -> bool:
        return name in self.new_name_by_old_name

    def try_get_new_name(self, old_name:str) -> str:
        """
        Will return old_name if there is no new name.
        """

        if not old_name in self.new_name_by_old_name:
            return old_name

        return self.new_name_by_old_name[old_name]

    def get_new_names_with_list_of_old_names(self, list_of_old_names:List[str]) -> List[str]:
        """
        Will write old name to new name list, if there is no new name.
        """

        new_names = []

        for old_name in list_of_old_names:
            new_names.append(self.try_get_new_name(old_name))

        return new_names

class BasicClassAndPackageNameDeobfuscationPass:
    """
    This pass will only try to deobfuscate class and package names. It will try to find files from target_project whose import, variable and function signatures and counts matches with reference_project.
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

    def is_already_deobfuscated(self, target_AS_parser:ActionScriptFileParser) -> bool:
        package_name_splitted = target_AS_parser.package_name.split(".")

        for package_part in package_name_splitted:
            if not self.target_project.is_name_already_deobfuscated(package_part):
                return False

        for class_info in target_AS_parser.class_infos:
            if not self.target_project.is_name_already_deobfuscated(class_info.name):
                return False

        return True

    def are_imports_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        for import_text in target_AS_parser.imports:
            import_splitted = import_text.split(".")
            import_splitted = self.target_project.get_new_names_with_list_of_old_names(import_splitted)

            # skip if import_splitted is obfuscated
            if "" in import_splitted:
                continue

            matching_import_found = False

            for reference_import_text in reference_AS_parser.imports:
                reference_import_splitted = reference_import_text.split(".")

                if import_splitted == reference_import_splitted:
                    matching_import_found = True
                    break

            if not matching_import_found:
                return False

        return True

    def are_vars_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        for target_var_info in target_AS_parser.global_var_infos:
            if not self.target_project.is_name_already_deobfuscated(target_var_info.name):
                continue

            matching_var_found = False

            for reference_var_info in reference_AS_parser.global_var_infos:
                if self.target_project.is_name_already_deobfuscated(target_var_info.type):
                    if (target_var_info.type == reference_var_info.type) & matching_var_found:
                        matching_var_found = True
                    else:
                        matching_var_found = False

                if (target_var_info.name == reference_var_info.name) & matching_var_found:
                    matching_var_found = True
                else:
                    matching_var_found = False

                if (target_var_info.visibility == reference_var_info.visibility) & matching_var_found:
                    matching_var_found = True
                else:
                    matching_var_found = False

                if (target_var_info.static == reference_var_info.static) & matching_var_found:
                    matching_var_found = True
                else:
                    matching_var_found = False

                if matching_var_found:
                    break

            if not matching_var_found:
                return False

        return True

    def are_functions_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        for target_function_info in target_AS_parser.function_infos:
            if DEFAULT_DEOBFUSCATED_NAME in target_function_info.name:
                continue

            matching_function_found = False

            for reference_function_info in reference_AS_parser.function_infos:
                if not DEFAULT_DEOBFUSCATED_NAME in target_function_info.return_type:
                    if target_function_info.return_type == reference_function_info.return_type:
                        matching_function_found = True
                    else:
                        matching_function_found = False

                param_types = self.target_project.get_new_names_with_list_of_old_names(target_function_info.param_types)

                # skip if one or more param types are obfuscated
                if not "" in param_types:
                    if (param_types == reference_function_info.param_types) & matching_function_found:
                        matching_function_found = True
                    else:
                        matching_function_found = False

                if (target_function_info.name == reference_function_info.name) & matching_function_found:
                    matching_function_found = True
                else:
                    matching_function_found = False

                if (target_function_info.visibility == reference_function_info.visibility) & matching_function_found:
                    matching_function_found = True
                else:
                    matching_function_found = False

                if (target_function_info.static == reference_function_info.static) & matching_function_found:
                    matching_function_found = True
                else:
                    matching_function_found = False

                if (len(target_function_info.param_names) == len(reference_function_info.param_names)) & matching_function_found:
                    matching_function_found = True
                else:
                    matching_function_found = False

                if (Utils.within_tolerance(target_function_info.line_count, reference_function_info.line_count, FUNCTION_LINE_COUNT_TOLERANCE)) & matching_function_found:
                    matching_function_found = True
                else:
                    matching_function_found = False

                if matching_function_found:
                    break

            if not matching_function_found:
                return False

        return True

    def AS_parsers_are_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> None:
        for index, class_info in enumerate(target_AS_parser.class_infos):
            self.target_project.new_name_by_old_name[class_info.name] = reference_AS_parser.class_infos[index].name

        self.target_project.new_name_by_old_name[target_AS_parser.package_name] = reference_AS_parser.package_name

    def deobfuscate(self) -> None:
        # TODO: narrow down reference files by searching from same package, if package is known
        for target_AS_parser in self.target_project.actionscript_file_parsers:

            import_count = len(target_AS_parser.imports)

            if not import_count in self.reference_project_action_script_files_by_import_count:
                continue

            reference_AS_parsers_with_same_import_counts = self.reference_project_action_script_files_by_import_count[import_count]

            matching_AS_file_pair = None
            matching_AS_file_pair_count = 0

            for reference_AS_parser in reference_AS_parsers_with_same_import_counts:

                if not self.are_imports_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not len(target_AS_parser.global_var_infos) == len(reference_AS_parser.global_var_infos):
                    continue

                if not self.are_vars_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not self.are_functions_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not len(target_AS_parser.function_infos) == len(reference_AS_parser.function_infos):
                    continue

                matching_AS_file_pair_count += 1

                if matching_AS_file_pair_count > 1:
                    break

                matching_AS_file_pair = (target_AS_parser, reference_AS_parser)

            if not matching_AS_file_pair_count > 1:
                self.AS_parsers_are_matching(matching_AS_file_pair[0], matching_AS_file_pair[1])

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
