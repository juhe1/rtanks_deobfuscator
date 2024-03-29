from collections.abc import Callable
from dataclasses import dataclass, field
from os.path import join
from typing import Dict, List, IO

import os
import json
from typing_extensions import Tuple
import pyperclip # NOTE: Only used in debugging. So remove if you want.

ALLOWED_FILE_TYPES:List[str] = ["as"]
DEFAULT_DEOBFUSCATED_NAME = "Åobfuscated_nameÅ"
TEST_SOURCE_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\test_data"

# Names are taken from the reference project. So when we are deobfuscating rtanks, this path should countain mytanks sources.
REFERENCE_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\mytanks_sources"

# Target project should contain sources that we are trying to deobfuscate. 
TARGET_PROJECT_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\rtanks_sources_cleaned"

DEOBFUSCATED_CODE_SAVE_PATH = r"D:\juho1\tankkin_modaus\rtanks\python\deobfuscator\data\rtanks_sources_deobfuscated"

FUNCTION_LINE_COUNT_TOLERANCE = 2
OPENING_BRACE = "()"[0] # the "()"[0] is for my stupid lsp which will freak out if i dont close open parenthesis in string
CLOSING_BRACE = "()"[1] # the "()"[1] is for my stupid lsp which will freak out if i dont close open parenthesis in string


@dataclass
class Accesser:
    package_name:str = ""
    file_name:str = ""
    name:str = "" # bassically variable or function name


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

    accessed_class_name_and_package:str
    function_name:str
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
        self.file_name:str = ""
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

        self.parse_file(file_path)

    def get_as_dictionary(self) -> Dict:
        import_datas = [str(x) for x in self.import_datas]
        class_infos = [str(x) for x in self.class_datas]
        interface_infos = [str(x) for x in self.interface_datas]
        global_var_infos = [str(x) for x in self.global_var_datas]
        function_infos = [str(x) for x in self.function_datas]
        access_datas = [str(x) for x in self.access_datas]

        return {
            "package_name":self.package_name,
            "file_name":self.file_name,
            "import_datas":import_datas,
            "class_infos":class_infos,
            "interface_infos":interface_infos,
            "global_var_infos":global_var_infos,
            "function_infos":function_infos,
            "access_datas":access_datas,
        }

    def try_add_import_accesser(self, class_name:str, name:str) -> None:
        imported_classes = [x.import_string.split(".")[-1] for x in self.import_datas]

        if class_name in imported_classes:
            import_string = self.import_datas[imported_classes.index(class_name)].import_string

            accesser = Accesser(
                name = name,
                package_name = self.package_name,
                file_name = self.file_name
            )

            self.import_datas_by_import_string[import_string].accessers.append(accesser)

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
                    implement = implements_name[:-1]
                    implements.append(implement)
                    self.try_add_import_accesser(implement, "")
                    continue

                implements.append(implements_name)
                self.try_add_import_accesser(implements_name, "")
                break

        if EXTENDS_TEXT in line_splitted_by_space:
            extends_index = line_splitted_by_space.index(EXTENDS_TEXT)
            extends = line_splitted_by_space[extends_index + 1]
            self.try_add_import_accesser(extends, "")

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

        self.try_add_import_accesser(type, name)

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

                        self.try_add_import_accesser(var.name, name)

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

                param_type = param.split(":")[1]

                param_names.append(param.split(":")[0])
                param_types.append(param_type)
                self.try_add_import_accesser(param_type, name)

        return_type = ""

        # parse return type if the function has one
        if line_splitted_by_space[-2] == ":":
            return_type = line_splitted_by_space[-1]
            self.try_add_import_accesser(return_type, name)

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
        self.file_name = os.path.basename(file_path)

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
                    file_name = self.file_name,
                    package_name = self.package_name,
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


class DeobfuscationUtils:
    @staticmethod
    def is_AS_parser_file_name_and_package_name_obfuscated(target_AS_parser:ActionScriptFileParser, project:ProjectSources) -> bool:
        if Utils.is_obfuscated(target_AS_parser.package_name) and not project.is_name_already_deobfuscated(target_AS_parser.package_name):
            return True

        if Utils.is_obfuscated(target_AS_parser.file_name) and not project.is_name_already_deobfuscated(target_AS_parser.file_name):
            return True

        return False


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

        self.target_project.new_name_by_old_name[target_AS_parser.package_name] = reference_AS_parser.package_name
        self.target_project.new_name_by_old_name[target_AS_parser.file_name] = reference_AS_parser.file_name

    def deobfuscate(self) -> None:
        # TODO: narrow down reference files by searching from same package, if package is known
        for target_AS_parser in self.target_project.actionscript_file_parsers:

            import_count = len(target_AS_parser.import_datas)

            if self.is_already_deobfuscated(target_AS_parser):
                continue

            if not import_count in self.reference_project_action_script_files_by_import_count:
                continue

            reference_AS_parsers_with_same_import_counts = self.reference_project_action_script_files_by_import_count[import_count]

            matching_AS_file_pair:Tuple|None = None
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

            if matching_AS_file_pair_count == 1 and matching_AS_file_pair  != None:
                self.AS_parsers_are_matching(matching_AS_file_pair[0], matching_AS_file_pair[1])


@dataclass
class Match:
    target_name:str
    matching_reference_names:List[str] = field(default_factory=list)


class FunctionNameDeobfuscationPass:

    def __init__(self, reference_project:ProjectSources, target_project:ProjectSources, line_count_deobfudcation_enabled:bool) -> None:
        self.reference_project = reference_project
        self.target_project = target_project
        self.line_count_deobfudcation_enabled:bool = line_count_deobfudcation_enabled

    def do_signuture_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> List[Match]:

        def are_params_matching(target_param_names:List[str], target_param_types:List[str], reference_param_names:List[str], reference_param_types:List[str]) -> bool:
            if len(target_param_names) != len(reference_param_names):
                return False

            for index, target_param_name in enumerate(target_param_names):
                target_param_name = self.target_project.try_get_new_name(target_param_name)

                if not Utils.is_obfuscated(target_param_name):
                    if not target_param_name == reference_param_names[index]:
                        return False

                target_param_type = self.target_project.try_get_new_name(target_param_types[index])

                if not Utils.is_obfuscated(target_param_type):
                    if not target_param_type == reference_param_types[index]:
                        return False

            return True

        matches = []

        for target_function_data in target_AS_parser.function_datas:
            match = Match(
                target_name = target_function_data.name
            )

            for reference_function_data in reference_AS_parser.function_datas:
                target_return_type = self.target_project.try_get_new_name(target_function_data.return_type)

                if not Utils.is_obfuscated(target_return_type):
                    if not target_return_type == reference_function_data.return_type:
                        continue

                target_name = self.target_project.try_get_new_name(target_function_data.name)

                if not Utils.is_obfuscated(target_name):
                    if not target_name == reference_function_data.name:
                        continue

                if not target_function_data.visibility == reference_function_data.visibility:
                    continue

                if not target_function_data.static == reference_function_data.static:
                    continue

                if not are_params_matching(target_function_data.param_names, target_function_data.param_types, reference_function_data.param_names, reference_function_data.param_types):
                    continue

                if self.line_count_deobfudcation_enabled and not target_function_data.line_count == reference_function_data.line_count:
                    continue
                
                match.matching_reference_names.append(reference_function_data.name)

            matches.append(match)

        return matches

    def deobfuscate(self) -> None:
        for target_AS_parser in self.target_project.actionscript_file_parsers:
            if DeobfuscationUtils.is_AS_parser_file_name_and_package_name_obfuscated(target_AS_parser, self.target_project):
                continue

            if len(target_AS_parser.class_datas) == 0:
                continue

            target_package_name = self.target_project.try_get_new_name(self.target_project.try_get_new_name(target_AS_parser.package_name))
            target_class_name = self.target_project.try_get_new_name(target_AS_parser.class_datas[0].name)
            target_as_class_name_and_package = target_package_name + "." + target_class_name

            if not target_as_class_name_and_package in self.reference_project.actionscript_file_parsers_by_class_name_and_package:
                continue

            reference_AS_parser = self.reference_project.actionscript_file_parsers_by_class_name_and_package[target_as_class_name_and_package]

            match_list = self.do_signuture_matching(target_AS_parser, reference_AS_parser)

            for match in match_list:
                match_count = len(match.matching_reference_names)
                if match_count > 1:
                    continue

                if match_count == 0:
                    continue

                self.target_project.new_name_by_old_name[match.target_name] = match.matching_reference_names[0]


class VariableNameDeobfuscationPass:

    """
    This pass will first try to match using only the variable type and value.
    If there is more that one match, then it will use also local access data in the deobfuscation.
    Finaly it will try to use global access data if it still doesn't succeed.
    """

    def __init__(self, reference_project:ProjectSources, target_project:ProjectSources) -> None:
        self.reference_project = reference_project
        self.target_project = target_project

    def do_signuture_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> List[Match]:
        matches = []

        for target_global_var_data in target_AS_parser.global_var_datas:
            match = Match(
                target_name = target_global_var_data.name
            )

            for reference_global_var_data in reference_AS_parser.global_var_datas:
                target_type = self.target_project.try_get_new_name(target_global_var_data.type)

                if not Utils.is_obfuscated(target_type):
                    if not target_type == reference_global_var_data.type:
                        continue

                target_name = self.target_project.try_get_new_name(target_global_var_data.name)

                if not Utils.is_obfuscated(target_name):
                    if not target_name == reference_global_var_data.name:
                        continue

                if not target_global_var_data.visibility == reference_global_var_data.visibility:
                    continue

                if not target_global_var_data.static == reference_global_var_data.static:
                    continue

                match.matching_reference_names.append(reference_global_var_data.name)

            matches.append(match)

        return matches

    def do_accesser_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser, local_matching:bool) -> List[Match]:

        def are_vars_matching(target_var_data:ActionScriptVarData, reference_var_data:ActionScriptVarData) -> bool:
            for target_var_accesser in target_var_data.accessers:
                if local_matching:
                    if target_var_accesser.package_name != target_AS_parser.package_name:
                        continue

                    if target_var_accesser.file_name != target_AS_parser.file_name:
                        continue

                target_var_accesser_package_name = self.target_project.try_get_new_name(target_var_accesser.package_name)

                if Utils.is_obfuscated(target_var_accesser_package_name):
                    continue

                target_var_accesser_file_name = self.target_project.try_get_new_name(target_var_accesser.file_name)

                if Utils.is_obfuscated(target_var_accesser_file_name):
                    continue

                target_var_accesser_name = self.target_project.try_get_new_name(target_var_accesser.name)

                if Utils.is_obfuscated(target_var_accesser_name):
                    continue

                matching_reference_accesser_found = False

                for reference_var_accesser in reference_var_data.accessers:
                    if target_var_accesser_package_name != reference_var_accesser.package_name:
                        continue

                    if target_var_accesser_file_name != reference_var_accesser.file_name:
                        continue

                    if target_var_accesser_name != reference_var_accesser.name:
                        continue

                    matching_reference_accesser_found = True

                if not matching_reference_accesser_found:
                    return False

            return True

        matches = []

        for target_var_data in target_AS_parser.global_var_datas:
            match = Match(
                target_name = target_var_data.name
            )

            for reference_var_data in reference_AS_parser.global_var_datas:
                if are_vars_matching(target_var_data, reference_var_data):
                    match.matching_reference_names.append(reference_var_data.name)

        return matches
                                                

    def deobfuscate(self) -> None:

        for target_AS_parser in self.target_project.actionscript_file_parsers:
            if DeobfuscationUtils.is_AS_parser_file_name_and_package_name_obfuscated(target_AS_parser, self.target_project):
                continue

            if len(target_AS_parser.class_datas) == 0:
                continue

            target_package_name = self.target_project.try_get_new_name(self.target_project.try_get_new_name(target_AS_parser.package_name))
            target_class_name = self.target_project.try_get_new_name(target_AS_parser.class_datas[0].name)
            target_as_class_name_and_package = target_package_name + "." + target_class_name

            if not target_as_class_name_and_package in self.reference_project.actionscript_file_parsers_by_class_name_and_package:
                continue

            reference_AS_parser = self.reference_project.actionscript_file_parsers_by_class_name_and_package[target_as_class_name_and_package]

            match_list = self.do_signuture_matching(target_AS_parser, reference_AS_parser)

            for match in match_list:
                matching_reference_count = len(match.matching_reference_names)
                if matching_reference_count < 2:
                    if matching_reference_count > 0:
                        self.target_project.new_name_by_old_name[match.target_name] = match.matching_reference_names[0]
                    continue

                match_list = self.do_accesser_matching(target_AS_parser, reference_AS_parser, True)

                for match in match_list:
                    matching_reference_count = len(match.matching_reference_names)
                    if matching_reference_count < 2 and matching_reference_count > 0:
                        self.target_project.new_name_by_old_name[match.target_name] = match.matching_reference_names[0]
                        continue

class ImportMatchingClassAndPackageNameDeobfuscationPass:
    """
    This pass will only try to deobfuscate class and package names.
    It will try to match imports from target class to reference class imports.
    """

    def __init__(self, reference_project:ProjectSources, target_project:ProjectSources) -> None:
        self.reference_project = reference_project
        self.target_project = target_project

    def do_accesser_matching(self, target_AS_parser:ActionScriptFileParser, reference_AS_parser:ActionScriptFileParser) -> List[Match]:

        def are_accesses_matching(target_accessers:List[Accesser], reference_accessers:List[Accesser]) -> bool:
            for target_accesser in target_accessers:
                target_var_accesser_package_name = self.target_project.try_get_new_name(target_accesser.package_name)

                if Utils.is_obfuscated(target_var_accesser_package_name):
                    continue

                target_accesser_file_name = self.target_project.try_get_new_name(target_accesser.file_name)

                if Utils.is_obfuscated(target_accesser_file_name):
                    continue

                target_accesser_name = self.target_project.try_get_new_name(target_accesser.name)

                if Utils.is_obfuscated(target_accesser_name):
                    continue

                matching_reference_accesser_found = False

                for reference_accesser in reference_accessers:
                    if target_var_accesser_package_name != reference_accesser.package_name:
                        continue

                    if target_accesser_file_name != reference_accesser.file_name:
                        continue

                    if target_accesser_name != reference_accesser.name:
                        continue

                    matching_reference_accesser_found = True

                if not matching_reference_accesser_found:
                    return False

            return True

        matches = []

        for target_import_data in target_AS_parser.import_datas:
            match = Match(
                target_name = target_import_data.import_string
            )

            for reference_import_data in reference_AS_parser.import_datas:
                if are_accesses_matching(target_import_data.accessers, reference_import_data.accessers):
                    match.matching_reference_names.append(reference_import_data.import_string)

            matches.append(match)

        return matches

    def deobfuscate(self) -> None:

        for target_AS_parser in self.target_project.actionscript_file_parsers:
            if DeobfuscationUtils.is_AS_parser_file_name_and_package_name_obfuscated(target_AS_parser, self.target_project):
                continue

            if len(target_AS_parser.class_datas) == 0:
                continue

            target_package_name = self.target_project.try_get_new_name(self.target_project.try_get_new_name(target_AS_parser.package_name))
            target_class_name = self.target_project.try_get_new_name(target_AS_parser.class_datas[0].name)
            target_as_class_name_and_package = target_package_name + "." + target_class_name

            if not target_as_class_name_and_package in self.reference_project.actionscript_file_parsers_by_class_name_and_package:
                continue

            reference_AS_parser = self.reference_project.actionscript_file_parsers_by_class_name_and_package[target_as_class_name_and_package]

            match_list = self.do_accesser_matching(target_AS_parser, reference_AS_parser)

            for match in match_list:
                if not len(match.matching_reference_names) < 2:
                    continue

                if len(match.matching_reference_names) == 0:
                    continue

                if not match.target_name in self.target_project.actionscript_file_parsers_by_class_name_and_package:
                    continue

                if not match.matching_reference_names[0] in self.reference_project.actionscript_file_parsers_by_class_name_and_package:
                    continue

                target_AS_parser = self.target_project.actionscript_file_parsers_by_class_name_and_package[match.target_name]
                reference_AS_parser = self.reference_project.actionscript_file_parsers_by_class_name_and_package[match.matching_reference_names[0]]

                self.target_project.new_name_by_old_name[target_AS_parser.package_name] = reference_AS_parser.package_name
                self.target_project.new_name_by_old_name[target_AS_parser.file_name] = reference_AS_parser.file_name

                if len(target_AS_parser.class_datas) != len(reference_AS_parser.class_datas):
                    continue

                for index, target_class_data in enumerate(target_AS_parser.class_datas):
                    reference_class_data = reference_AS_parser.class_datas[index]
                    self.target_project.new_name_by_old_name[target_class_data.name] = reference_class_data.name


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

def apply_deobfuscations_to_files(source_path:str, new_sources:str, new_name_by_old_name:Dict[str, str]) -> None:
    def loop_file_content(file_path:str) -> str:
        with open(file_path, 'r', encoding='utf-8') as file:
            new_text = ""

            for line in file:
                new_line = line
                inside_obfuscated_name = False
                obfuscated_name = ""

                for char in line:
                    if char == "Å":
                        inside_obfuscated_name = not inside_obfuscated_name

                        if not inside_obfuscated_name:
                            obfuscated_name += "Å"

                            if obfuscated_name in new_name_by_old_name:
                                new_line = new_line.replace(obfuscated_name, new_name_by_old_name[obfuscated_name])
                            else:
                                new_line = new_line.replace(obfuscated_name, obfuscated_name[1:-1])

                            obfuscated_name = ""

                    if inside_obfuscated_name:
                        obfuscated_name += char

                new_text += new_line

        return new_text

    for root, dirs, files in os.walk(source_path):
        for file in files:
            file_path = os.path.join(root, file)

            if not file.split(".")[-1] in ALLOWED_FILE_TYPES:
                continue

            new_content = loop_file_content(file_path)

            file_name = os.path.basename(file_path)

            package_name = file_path.replace(source_path, "").replace(file_name, "").replace("\\", ".")
            if len(package_name) < 2:
                package_name = ""
            else:
                if package_name[0] == ".":
                    package_name = package_name[1:]
                if package_name[-1] == ".":
                    package_name = package_name[:-1]

                if package_name in new_name_by_old_name:
                    package_name = new_name_by_old_name[package_name]

            if file_name in new_name_by_old_name:
                file_name = new_name_by_old_name[file_name]

            new_path = new_sources + "\\" + package_name.replace(".", "\\")

            os.makedirs(new_path, exist_ok=True)

            with open(new_path + "\\" + file_name, 'w', encoding="utf-8") as file:
                file.write(new_content)

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
    function_name_deobfuscation_pass = FunctionNameDeobfuscationPass(reference_project, target_project, line_count_deobfudcation_enabled=True)
    variable_name_deobfuscation_pass = VariableNameDeobfuscationPass(reference_project, target_project)
    import_deobfuscation_pass = ImportMatchingClassAndPackageNameDeobfuscationPass(reference_project, target_project)

    basic_class_and_package_name_deobfuscation_pass.deobfuscate()
    function_name_deobfuscation_pass.deobfuscate()
    variable_name_deobfuscation_pass.deobfuscate()
    import_deobfuscation_pass.deobfuscate()
    basic_class_and_package_name_deobfuscation_pass.deobfuscate()
    function_name_deobfuscation_pass.deobfuscate()
    variable_name_deobfuscation_pass.deobfuscate()
    import_deobfuscation_pass.deobfuscate()

    apply_deobfuscations_to_files(TARGET_PROJECT_PATH, DEOBFUSCATED_CODE_SAVE_PATH, target_project.new_name_by_old_name)
    
    #pyperclip.copy(json.dumps(target_project.new_name_by_old_name))
    #print("copied new_name_by_old_name to clipboard!")

    print("DONE!")

if __name__ == "__main__":
    #test_action_script_file_parser()
    main()
