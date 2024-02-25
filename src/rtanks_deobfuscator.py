from collections.abc import Callable
from dataclasses import dataclass, field
from os.path import join
from typing import Dict, List, IO

import os
import json
from typing_extensions import Tuple
import pyperclip # NOTE: Only used in debugging. So remove if you want.

ALLOWED_FILE_TYPES:List[str] = ["as"]
DEFAULT_DEOBFUSCATED_NAME = "deobfuscated_name"
TEST_SOURCE_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\test_data"

# Names are taken from the reference project. So when we are deobfuscating rtanks, this path should countain mytanks sources.
REFERENCE_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\mytanks_sources"

# Target project should contain sources that we are trying to deobfuscate. 
TARGET_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\rtanks_sources_cleaned"

FUNCTION_LINE_COUNT_TOLERANCE = 2
OPENING_BRACE = "()"[0] # the "()"[0] is for my stupid lsp which will freak out if i dont close open parenthesis in string
CLOSING_BRACE = "()"[1] # the "()"[1] is for my stupid lsp which will freak out if i dont close open parenthesis in string


@dataclass
class Accesser:
    class_name_and_package:str = ""
    name:str = ""


class Utils:
    @staticmethod
    def within_tolerance(num1:int, num2:int, tolerance:int) -> bool:
        return abs(num1 - num2) <= tolerance
    
    @staticmethod
    def is_obfuscated(text:str) -> bool:
        return DEFAULT_DEOBFUSCATED_NAME in text

@dataclass
class ActionScriptClassData:
    name:str
    implements:List[str]
    extends:str
    visibility:str


@dataclass
class ActionScriptInterfaceData:
    name:str
    visibility:str


@dataclass
class ActionScriptVarData:
    name:str
    visibility:str
    type:str
    static:bool
    value:str;
    accessers:List[Accesser] = field(default_factory=list)


@dataclass
class ActionScriptFunctionData:
    name:str
    visibility:str
    static:bool
    return_type:str
    param_names:List[str]
    param_types:List[str]
    line_count:int
    setter_getter:str
    accessers:List[Accesser] = field(default_factory=list)


@dataclass
class ActionScriptAccessData:
    """
    example:
        var jea:SomeClass = something;
        jea.nigga.stole.my.bige

    In above example the accessed_class_name_and_package will have "SomeClass" as value and sub_accesses will have ["nigga", "stole", "my", "bige"] as value
    """

    function_name:str
    accessed_class_name_and_package:str
    sub_accesses:List[str]


@dataclass
class ActionScriptImportDatas:
    import_string:str
    accessers:List[Accesser] = field(default_factory=list)


class ProjectSources:
    def __init__(self) -> None:
        self.actionscript_file_parsers:List[ActionScriptFileParser] = []
        self.actionscript_file_parsers_by_class_name_and_package:Dict[str, ActionScriptFileParser] = {} # Example: {"some.package.ExampleClass":ActionScriptFileParser()}
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


class ActionScriptFileParser:
    def __init__(self, file_path:str) -> None:
        self.package_name:str = ""
        #self.imports:List[str] = []
        self.import_datas:List[ActionScriptImportDatas] = []
        self.class_datas:List[ActionScriptClassData] = []
        self.interface_datas:List[ActionScriptInterfaceData] = []
        self.global_var_datas:List[ActionScriptVarData] = []
        self.function_datas:List[ActionScriptFunctionData] = []
        self.access_datas:List[ActionScriptAccessData] = []
        self.import_datas_by_import_string:Dict[str, ActionScriptImportDatas] = {}
        self.global_var_datas_by_name:Dict[str, ActionScriptVarData] = {}
        self.function_datas_by_name:Dict[str, ActionScriptFunctionData] = {}
        #self.import_accesser_names_by_import_name:Dict[str, List[str]] = {} # Example: {"jea.something":["some_function"]}, so jea.something is accessed in some_function

        self.parse_file(file_path)

    def __str__(self) -> str:
        return f"""
package_name: {self.package_name}
import_datas: {self.import_datas}
class_datas: {self.class_datas}
global_var_datas: {self.global_var_datas}
function_datas: {self.function_datas}
access_datas: {self.access_datas}
        """

    def get_as_dictionary(self) -> Dict:
        package_name = str(self.package_name)
        import_datas = [str(x) for x in self.import_datas]
        class_infos = [str(x) for x in self.class_datas]
        interface_infos = [str(x) for x in self.interface_datas]
        global_var_infos = [str(x) for x in self.global_var_datas]
        function_infos = [str(x) for x in self.function_datas]
        access_datas = [str(x) for x in self.access_datas]

        return {
            "package_name":package_name,
            "import_datas":import_datas,
            "class_infos":class_infos,
            "interface_infos":interface_infos,
            "global_var_infos":global_var_infos,
            "function_infos":function_infos,
            "access_datas":access_datas,
        }

    def parse_package(self, line_splitted_by_space:List[str], word_index:int) -> None:
        if word_index + 1 < len(line_splitted_by_space):
            self.package_name = line_splitted_by_space[word_index + 1]
    
    def parse_import(self, line_splitted_by_space:List[str], word_index:int) -> None:
        import_data = ActionScriptImportDatas(
            import_string = line_splitted_by_space[word_index + 1][:-1]
        )
        self.import_datas.append(import_data)
        self.import_datas_by_import_string[import_data.import_string] = import_data

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

        self.class_datas.append(class_info)

    def is_static(self, line_splitted_by_space:List[str]) -> bool:
        return "static" in line_splitted_by_space

    def parse_visibility(self, line_splitted_by_space:List[str]) -> str:
        if line_splitted_by_space[0] in ["public", "private", "protected", "internal"]:
            return line_splitted_by_space[0]
        return "public"

    def parse_var_definition(self, line_splitted_by_space:List[str], word_index:int) -> None:
        name_and_type = line_splitted_by_space[word_index + 1].split(":")
        name = name_and_type[0]
        type = name_and_type[1]

        if type[-1] == ";":
            type = type[:-1]

        static = self.is_static(line_splitted_by_space)        
        visibility = self.parse_visibility(line_splitted_by_space)        
        
        value = ""

        if "=" in line_splitted_by_space:
            value = "".join(line_splitted_by_space[line_splitted_by_space.index("=") + 1:])[:-1]

        var_info = ActionScriptVarData(
            name=name,
            type=type,
            visibility=visibility,
            static=static,
            value=value
        )
        self.global_var_datas.append(var_info)
        self.global_var_datas_by_name[name] = var_info

        imported_classes = [x.import_string.split(".")[-1] for x in self.import_datas]
        if type in imported_classes:
            import_string = self.import_datas[imported_classes.index(type)].import_string
            accesser = Accesser(
                name = name,
                class_name_and_package = self.package_name + "." + self.class_datas[0].name
            )

            self.import_datas_by_import_string[import_string].accessers.append(accesser)

    def parse_local_var_definition(self, line_splitted_by_space:List[str], word_index:int) -> ActionScriptVarData | None:
        t = line_splitted_by_space[word_index + 1].split(":")

        if len(t) < 2:
            return None

        name, type = t
        return ActionScriptVarData(
            name=name,
            type=type,
            visibility="",
            static=False,
            value="",
        )

    def parse_access(self, line:str, local_vars_by_name:Dict[str, ActionScriptVarData], function_name:str) -> None:
        for word in line.split(" "):
            if not "." in word:
                continue

            current_word = ""
            accesses = []

            for char in word:
                if not char.isalpha() and char != "_" and char != ".":
                    if accesses == []:
                        current_word = ""
                        continue

                    accesses.append(current_word)
                    break

                if char == ".":
                    accesses.append(current_word)
                    current_word = ""
                    continue

                current_word += char

            imported_classes = [x.import_string.split(".")[-1] for x in self.import_datas]
            first_access = accesses[0]
            is_first_access_in_imported_classes = first_access in imported_classes

            class_name_and_package = ""

            if first_access != "this" and not is_first_access_in_imported_classes:
                if not first_access in local_vars_by_name:
                    continue

                class_name = local_vars_by_name[first_access].type

                if not class_name in imported_classes:
                    continue

                class_name_and_package = self.import_datas[imported_classes.index(class_name)].import_string

            if is_first_access_in_imported_classes:
                class_name_and_package = self.import_datas[imported_classes.index(first_access)].import_string

            if first_access == "this":
                class_name_and_package = self.package_name + "." + self.class_datas[-1].name

            if class_name_and_package == "" or len(accesses) < 2:
                continue

            sub_accesses = accesses[1:]

            access_data = ActionScriptAccessData(
                accessed_class_name_and_package = class_name_and_package,
                sub_accesses = sub_accesses,
                function_name = function_name
            )

            self.access_datas.append(access_data)

    def parse_function_definition(self, line_splitted_by_space:List[str], word_index:int, file:IO) -> None:
        local_vars_by_name = {}

        def parse_line_from_function(line:str) -> None:
            local_line_splitted_by_space = line.split(" ")
            for index, word in enumerate(local_line_splitted_by_space):
                if word == "var":
                    var = self.parse_local_var_definition(local_line_splitted_by_space, index)

                    if not var == None:
                        local_vars_by_name[var.name] = var

                        imported_classes = [x.import_string.split(".")[-1] for x in self.import_datas]

                        if var.type in imported_classes and len(self.class_datas) > 0:
                            import_string = self.import_datas[imported_classes.index(var.type)].import_string

                            accesser = Accesser(
                                name = name,
                                class_name_and_package = self.package_name + "." + self.class_datas[-1].name
                            )

                            self.import_datas_by_import_string[import_string].accessers.append(accesser)

                if "." in word:
                    self.parse_access(line, local_vars_by_name, name)

        line = " ".join(line_splitted_by_space)
        name = line.split(OPENING_BRACE)[0].split(" ")[-1]
        visibility = self.parse_visibility(line_splitted_by_space)
        static = self.is_static(line_splitted_by_space)
        setter_getter = ""

        if "get" in line_splitted_by_space:
            setter_getter = "get"

        if "set" in line_splitted_by_space:
            setter_getter = "set"

        param_names = []
        param_types = []

        params_string = line.split(OPENING_BRACE)[1].split(CLOSING_BRACE)[0]
        params = params_string.split(",")

        # if there is params, then parse them
        if not params[0] == "":
            for param in params:
                # this is for handling variable-length argument list
                if "..." in param:
                    param_names.append(param)
                    param_types.append("...")
                    continue

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

        if not line[-1] == ";":
            for line in file:
                if OPENING_CURLY_BRACE in line:
                    scope_depth += 1
                if CLOSING_CURLY_BRACE in line:
                    scope_depth -= 1

                if scope_depth == 0:
                    break

                function_line_count += 1

                parse_line_from_function(line)

        function_data = ActionScriptFunctionData(
            name=name,
            visibility=visibility,
            static=static,
            param_names=param_names,
            param_types=param_types,
            return_type=return_type,
            line_count=function_line_count,
            setter_getter=setter_getter
        )

        self.function_datas.append(function_data)
        self.function_datas_by_name[name] = function_data

    def parse_interface_definition(self, line_splitted_by_space:List[str], word_index:int) -> None:
        interface_data = ActionScriptInterfaceData(
            name = line_splitted_by_space[word_index + 1],
            visibility = self.parse_visibility(line_splitted_by_space)
        )

        self.interface_datas.append(interface_data)
        
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
                case "interface":
                    self.parse_interface_definition(line_splitted_by_space, index)
                case _:
                    pass

    def parse_file(self, file_path:str) -> None:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                self.parse_line(line, file)

    def sort_accesses(self, project:ProjectSources) -> None:
        for access in self.access_datas:
            if not access.accessed_class_name_and_package in project.actionscript_file_parsers_by_class_name_and_package:
                continue

            accessed_AS_parser = project.actionscript_file_parsers_by_class_name_and_package[access.accessed_class_name_and_package]
            
            for index, access_name in enumerate(access.sub_accesses):
                access_target = None

                if access_name in accessed_AS_parser.global_var_datas_by_name:
                    access_target = accessed_AS_parser.global_var_datas_by_name[access_name]

                if access_name in accessed_AS_parser.function_datas_by_name:
                    access_target = accessed_AS_parser.function_datas_by_name[access_name]

                accesser = Accesser(
                    class_name_and_package = self.package_name + "." + self.class_datas[0].name,
                    name = access.function_name
                )

                if access_target:
                    access_target.accessers.append(accesser)

                if isinstance(access_target, ActionScriptVarData) and index < len(access.sub_accesses) - 1:
                    imported_classes = [x.import_string.split(".")[-1] for x in self.import_datas]

                    if not access_target.type in imported_classes:
                        continue

                    import_string = self.import_datas[imported_classes.index(access_target.type)].import_string

                    if not import_string in project.actionscript_file_parsers_by_class_name_and_package:
                        continue

                    accessed_AS_parser = project.actionscript_file_parsers_by_class_name_and_package[import_string]

        self.access_datas = []


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
            import_count = len(action_script_file_parser.import_datas)

            if not import_count in out:
                out[import_count] = []

            out[import_count].append(action_script_file_parser)

        return out

    def is_already_deobfuscated(self, target_AS_parser:ActionScriptFileParser) -> bool:
        if not self.target_project.is_name_already_deobfuscated(target_AS_parser.package_name) and Utils.is_obfuscated(target_AS_parser.package_name):
            return False

        for target_class_info in target_AS_parser.class_datas:
            if not self.target_project.is_name_already_deobfuscated(target_class_info.name) and Utils.is_obfuscated(target_class_info.name):
                return False

        for target_interface_data in target_AS_parser.interface_datas:
            if not self.target_project.is_name_already_deobfuscated(target_interface_data.name) and Utils.is_obfuscated(target_interface_data.name):
                return False

        return True

    def are_imports_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        for import_data in target_AS_parser.import_datas:
            target_import_text = import_data.import_string
            target_import_text = self.target_project.try_get_new_name(target_import_text)

            if Utils.is_obfuscated(target_import_text):
                continue

            matching_import_found = False
            
            for import_data in reference_AS_parser.import_datas:
                reference_import_text = import_data.import_string
                if target_import_text == reference_import_text:
                    matching_import_found = True

            if not matching_import_found:
                return False

        return True

    def are_vars_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:

        def are_var_datas_matching(target_var_data, reference_var_data):
            type = self.target_project.try_get_new_name(target_var_data.type)
            if not Utils.is_obfuscated(type):
                if not type == reference_var_data.type:
                    return False

            name = self.target_project.try_get_new_name(target_var_data.name)
            if not Utils.is_obfuscated(name):
                if not name == reference_var_data.name:
                    return False

            if not target_var_data.visibility == reference_var_data.visibility:
                return False

            if not target_var_data.static == reference_var_data.static:
                return False

            return True

        for target_var_data in target_AS_parser.global_var_datas:
            matching_var_found = False

            for reference_var_data in reference_AS_parser.global_var_datas:
                matching_var_found = are_var_datas_matching(target_var_data, reference_var_data)

                if matching_var_found:
                    break

            if not matching_var_found:
                return False

        return True

    def are_functions_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:

        def are_function_datas_matching(target_function_data, reference_function_data):
            return_type = self.target_project.try_get_new_name(target_function_data.return_type)
            if not Utils.is_obfuscated(return_type) and not return_type == reference_function_data.return_type:
                return False

            if not len(target_function_data.param_types) == len(reference_function_data.param_types):
                return False
            else:
                param_types = self.target_project.get_new_names_with_list_of_old_names(target_function_data.param_types)

                # skip if one or more param types are obfuscated
                if not "" in param_types:
                    if not param_types == reference_function_data.param_types:
                        return False

            name = self.target_project.try_get_new_name(target_function_data.name)
            if not Utils.is_obfuscated(name) and not name == reference_function_data.name:
                return False

            if not target_function_data.visibility == reference_function_data.visibility:
                return False

            if not target_function_data.static == reference_function_data.static:
                return False

            if not target_function_data.setter_getter == reference_function_data.setter_getter:
                return False

            if not Utils.within_tolerance(target_function_data.line_count, reference_function_data.line_count, FUNCTION_LINE_COUNT_TOLERANCE):
                return False

            return True

        for target_function_data in target_AS_parser.function_datas:

            matching_function_found = False

            for reference_function_data in reference_AS_parser.function_datas:
                matching_function_found = are_function_datas_matching(target_function_data, reference_function_data)

                if matching_function_found:
                    break
                
            if not matching_function_found:
                return False

        return True

    def are_class_signutures_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        if not len(target_AS_parser.class_datas) == len(reference_AS_parser.class_datas):
            return False

        for class_info_index, target_class_data in enumerate(target_AS_parser.class_datas):
            reference_class_data = reference_AS_parser.class_datas[class_info_index]

            name = self.target_project.try_get_new_name(target_class_data.name)
            if not Utils.is_obfuscated(name):
                if not name == reference_class_data.name:
                    return False
            
            if not len(target_class_data.implements) == len(reference_class_data.implements):
                return False

            for implement_index, implement in enumerate(target_class_data.implements):
                implement = self.target_project.try_get_new_name(implement)
                if not Utils.is_obfuscated(implement):
                    if not implement == reference_class_data.implements[implement_index]:
                        return False

            extends = self.target_project.try_get_new_name(target_class_data.extends)
            if not Utils.is_obfuscated(extends):
                if not extends == reference_class_data.extends:
                    return False

            if not target_class_data.visibility == reference_class_data.visibility:
                return False

        return True

    def are_interface_signutures_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        if not len(target_AS_parser.interface_datas) == len(reference_AS_parser.interface_datas):
            return False

        for index, target_interface in enumerate(target_AS_parser.interface_datas):
            reference_interface = reference_AS_parser.interface_datas[index]

            name = self.target_project.try_get_new_name(target_interface.name)
            if not Utils.is_obfuscated(name):
                if not name == reference_interface.name:
                    return False

            if not target_interface.visibility == reference_interface.visibility:
                return False

        return True

    def are_package_names_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> bool:
        target_package_name = self.target_project.try_get_new_name(target_AS_parser.package_name)

        if Utils.is_obfuscated(target_package_name):
            return True

        return target_package_name == reference_AS_parser.package_name

    def AS_parsers_are_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> None:
        for index, target_class_info in enumerate(target_AS_parser.class_datas):
            self.target_project.new_name_by_old_name[target_class_info.name] = reference_AS_parser.class_datas[index].name

        for index, target_interface_data in enumerate(target_AS_parser.interface_datas):
            self.target_project.new_name_by_old_name[target_interface_data.name] = reference_AS_parser.interface_datas[index].name

        target_package_name_splitted = target_AS_parser.package_name.split(".")
        reference_package_name_splitted = target_AS_parser.package_name.split(".")

        for index, target_package_name_part in enumerate(target_package_name_splitted):
            self.target_project.new_name_by_old_name[target_package_name_part] = reference_AS_parser.package_name

    def deobfuscate(self) -> None:
        # TODO: narrow down reference files by searching from same package, if package is known
        for target_AS_parser in self.target_project.actionscript_file_parsers:

            import_count = len(target_AS_parser.import_datas)

            if self.is_already_deobfuscated(target_AS_parser):
                continue

            if not import_count in self.reference_project_action_script_files_by_import_count:
                continue

            reference_AS_parsers_with_same_import_counts = self.reference_project_action_script_files_by_import_count[import_count]

            matching_AS_file_pair = None
            matching_AS_file_pair_count = 0

            for reference_AS_parser in reference_AS_parsers_with_same_import_counts:

                if not self.are_package_names_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not self.are_class_signutures_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not self.are_interface_signutures_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not self.are_imports_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not len(target_AS_parser.global_var_datas) == len(reference_AS_parser.global_var_datas):
                    continue

                if not self.are_vars_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not self.are_functions_matching(target_AS_parser, reference_AS_parser):
                    continue

                if not len(target_AS_parser.function_datas) == len(reference_AS_parser.function_datas):
                    continue

                matching_AS_file_pair_count += 1

                if matching_AS_file_pair_count > 1:
                    break

                matching_AS_file_pair = (target_AS_parser, reference_AS_parser)

            if matching_AS_file_pair_count == 1:
                self.AS_parsers_are_matching(matching_AS_file_pair[0], matching_AS_file_pair[1])


class ImportMatchingClassAndPackageNameDeobfuscationPass:
    """
    This pass will only try to deobfuscate class and package names.
    It will try to match imports from target class to reference class imports.
    """

    def __init__(self) -> None:
        return

    def deobfuscate(self) -> None:
        pass


def parse_project_sources(source_path:str) -> ProjectSources:
    sources = ProjectSources()

    for root, directories, files in os.walk(source_path):
        for filename in files:
            if not filename.split(".")[-1] in ALLOWED_FILE_TYPES:
                continue

            file_path = os.path.join(root, filename)
            as_file_parser = ActionScriptFileParser(file_path)
            sources.actionscript_file_parsers.append(as_file_parser)

            for class_data in as_file_parser.class_datas:
                sources.actionscript_file_parsers_by_class_name_and_package[as_file_parser.package_name + "." + class_data.name] = as_file_parser

    for AS_file_parser in sources.actionscript_file_parsers:
        AS_file_parser.sort_accesses(sources)

    return sources

def test_action_script_file_parser() -> None:
    # Copy the string to the clipboard
    sources = parse_project_sources(TEST_SOURCE_PATH)
    action_script_file_datas = [x.get_as_dictionary() for x in sources.actionscript_file_parsers]
    
    pyperclip.copy(json.dumps(action_script_file_datas))
    print("copied action_script_file_datas to clipboard!")

def main() -> None:
    reference_project = parse_project_sources(REFERENCE_PROJECT_PATH)
    target_project = parse_project_sources(TARGET_PROJECT_PATH)

    basic_class_and_package_name_deobfuscation_pass = BasicClassAndPackageNameDeobfuscationPass(reference_project, target_project)
    basic_class_and_package_name_deobfuscation_pass.deobfuscate()
    basic_class_and_package_name_deobfuscation_pass.deobfuscate()
    
    pyperclip.copy(json.dumps(target_project.new_name_by_old_name))
    print("copied new_name_by_old_name to clipboard!")

if __name__ == "__main__":
    #test_action_script_file_parser()
    main()
