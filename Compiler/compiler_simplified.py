import ast
import copy
import itertools
import logging
import os
import shutil
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from inspect import currentframe, getframeinfo
from pprint import pformat
from typing import List, Any, Dict, Union

import astor
import boto3

# from compiler_module import loadbalancer_configuration, original_code
# import loadbalancer

# compiler_module_config = loadbalancer.ModuleConfigClass()
benchmark_dir = "../BenchmarkApplication"
# file_name = compiler_module_config.file_name

# Logging Configuration
modules_for_removing_debug = [
    "urllib3",
    "s3transfer",
    "boto3",
    "botocore",
    "urllib3",
    "requests",
    "paramiko",
]
for name in modules_for_removing_debug:
    logging.getLogger(name).setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)
logger.propagate = False
logFormatter = logging.Formatter(
    "%(asctime)s [%(levelname)-6s] [%(filename)s:%(lineno)-4s]  %(message)s"
)
# fileHandler = logging.FileHandler(compiler_module_config.result_logfile_name)
consoleHandler = logging.StreamHandler()
# fileHandler.setFormatter(logFormatter)
consoleHandler.setFormatter(logFormatter)
# logger.addHandler(fileHandler)
logger.addHandler(consoleHandler)
logger.setLevel(logging.DEBUG)

CREDENTIALS = {}
s3_client = boto3.client("s3", **CREDENTIALS)
s3 = boto3.resource("s3", **CREDENTIALS)


@dataclass
class TargetGoalConfig:
    cost: float = 2.3
    performance: float = 1.2


def return_vm_types():
    vm_types_list = [
        "c5.large",
        "c3.large",
        "m4.large",
        "m3.large",
        "c5.2xlarge",
        "c3.2xlarge",
    ]
    return vm_types_list


@dataclass
class VMRuntimeConfig:
    vm_instance_selection_list: List = field(default_factory=return_vm_types)
    region_name: str = "us-east-1"


@dataclass
class FunctionWithServiceCandidate:
    service_candidate: str = None
    merge_function: str = None
    rules_for_scaling_policy: dict = field(default_factory=defaultdict)


@dataclass
class UserInputClass:
    original_file: str = "image_processing_1_1.py"
    target_goal_config: TargetGoalConfig = field(default_factory=TargetGoalConfig)
    vm_runtime_config: VMRuntimeConfig = field(default_factory=VMRuntimeConfig)


def terminate_instance(instance_id, region_name="us-east-1"):
    ec2_client = boto3.client("ec2", region_name=region_name, **CREDENTIALS)
    ec2_client.terminate_instances(InstanceIds=[instance_id, ], )
    logger.info(f"Terminating instance - {instance_id}")


def user_annotation_for_application() -> UserInputClass:
    """
    Make info from user annotation
    1. Original File
    2. VM Runtime configuration
    3. Target Goal
    3. Function service with parameters
    """

    # Fist make dataclass and save default values
    user_input_class = UserInputClass()

    # Input source code
    source_code = input("enter your application code:\n")
    if source_code != "":
        user_input_class.original_file = source_code

    # Target Goal - Cost or Performance
    target_goal_config = TargetGoalConfig()
    cost_goal = input("Enter the cost goal ($):\n")
    if cost_goal != "":
        target_goal_config.cost = int(cost_goal)

    # Performance goal
    performance_goal = input("Enter the performance goal (ms):\n")
    if performance_goal != "":
        target_goal_config.performance = float(performance_goal)

    # Add target_goal_config to user_input_class
    user_input_class.target_goal_config = target_goal_config

    # VM Runtime Configuration, VM AWS RegionName
    vm_runtime_config = VMRuntimeConfig()
    vm_instance_types = input(f"VM Selection: select VM types : {return_vm_types()}\n")
    if vm_instance_types != "":
        vm_selection_list = [
            x.strip() for x in vm_instance_types.split(",") if vm_instance_types
        ]
        vm_runtime_config.vm_instance_selection_list = vm_selection_list

    # AWS Region
    vm_region_name = input("Choose aws region for VM:\n")
    if vm_region_name != "":
        vm_runtime_config.region_name = vm_region_name

    # Add vm_runtime_config to user input class
    user_input_class.vm_runtime_config = vm_runtime_config
    logging.debug(f"user_input_class is \n {pformat(user_input_class.__dict__)}")

    return user_input_class


def make_dataclass_that_contains_whole_info(original_code_script, original_filename):
    """
    save original code and module object and copied module object
    """
    original_ast: ast.Module = ast.parse(original_code_script.read())
    module_for_analysis = copy.deepcopy(original_ast)

    whole_info_class = WholeASTInfoClass(
        file_name=original_filename,
        original_code_module=original_ast,
        copied_module_for_analysis=module_for_analysis,
    )
    return whole_info_class


@dataclass
class ASTObjectInfoClass:
    line_number: int
    ast_object: Any


@dataclass(order=True)
class ImportInfoClass(ASTObjectInfoClass):
    # import_name: List = field(default_factory=list)
    import_name: str = None
    # import_object: Any = None
    # object_list: List = field(default_factory=list)
    from_python_script: bool = False
    from_import: list = field(default_factory=list)
    # import_as: List = field(default_factory=list)
    import_as: list = field(default_factory=list)
    assign_targets_from_non_func: set = field(default_factory=set)


def give_services_input():
    return "{IaaS, FaaS}"


@dataclass
class ServiceTypeForFunction:
    service_type: List = field(default_factory=give_services_input)


@dataclass
class LambdaConfig:
    memory_size: int = 512
    timeout: int = 100
    runtime: str = "py37"
    function_name: str = None


@dataclass
class FunctionMetricRules:
    use_default_value_for_cpu_util: bool = True
    cpu_util_operand: float = 40
    cpu_util_operator: str = ">"

    use_default_value_for_memory_util: bool = True
    memory_util_operand: float = 30
    memory_util_operator: str = ">"

    use_default_value_for_arrival_rate: bool = True
    arrival_rate_operand: int = 5
    arrival_rate_operator: str = ">"


@dataclass
class Boto3AndJsonImportClass:
    ast_object: Any


@dataclass(order=True)
class NonFunctionInfoClass(ASTObjectInfoClass):
    non_func_object_type: str = None
    import_name_list: set = field(default_factory=set)
    assign_targets: list = field(default_factory=list)
    description: str = None


# @dataclass(order=True)
# class ObjectsInIfMainInfoClass(ASTObjectInfoClass):
#     object_type: str = None
#     import_name_list: set = field(default_factory=set)
#     assign_targets: list = field(default_factory=list)
#     description: str = None


@dataclass(order=True)
class FunctionDefinition(ASTObjectInfoClass):
    func_name: str = False
    # from_python_script: bool = False
    import_name_list: set = field(default_factory=set)
    assign_targets: list = field(default_factory=list)
    function_parameters: list = field(default_factory=list)
    return_objects: list = field(default_factory=list)
    return_object_ast: Any = None

    # service_type_for_function: ServiceTypeForFunction = field(
    #     default_factory=ServiceTypeForFunction
    # )

    lambda_runtime_conf: LambdaConfig = field(default_factory=LambdaConfig)
    function_metric_rules: FunctionMetricRules = field(
        default_factory=FunctionMetricRules
    )
    initial_pragma: str = None
    # merge_function: str = None
    # initial_metric: Dict[str, Dict] = field(default_factory=defaultdict)
    lambda_group_name: str = "Default"
    func_call_for_lambda_handler: Union[ast.Assign, ast.Expr] = field(
        default_factory=list
    )


@dataclass
class FunctionCallInfo(ASTObjectInfoClass):
    object_type: str = None
    caller_object: ast.FunctionDef = None
    caller_object_name: str = None
    callee_object: ast.Call = None
    callee_object_name: str = None
    assign_targets: list = field(default_factory=list)
    call_func_params: list = field(default_factory=list)


@dataclass
class FunctionCallInsideIfMain(ASTObjectInfoClass):
    object_type: str = None
    # called_in_function_object: ast.FunctionDef = None
    # called_in_function_object_name: str = None
    callee_object: ast.Call = None
    callee_object_name: str = None
    # assign_targets: list = field(default_factory=list)
    # call_func_params: list = field(default_factory=list)


@dataclass
class LambdaBasedFunctionCallInfoClass:
    copied_func_call_info: FunctionCallInfo
    original_func_call_info: FunctionCallInfo


@dataclass
class CompilerGeneratedLambda:
    lambda_name: str
    original_func_name: str
    lambda_module: ast.Module
    lambda_handler_func_object: ast.FunctionDef
    original_ast_object: ast.FunctionDef
    lambda_event_input_objs: list = field(default_factory=list)
    input_parameter: List[ast.Assign] = field(default_factory=list)
    import_info_dict: dict = field(default_factory=defaultdict)
    return_objects: list = field(default_factory=list)
    import_name_list: list = field(default_factory=list)  # for offloading whole app


@dataclass
class MergedCompilerGeneratedLambda:
    lambda_group_name: str
    lambda_name_list: list
    lambda_module: ast.Module
    lambda_handler_func_object: ast.FunctionDef
    original_ast_object_list: list
    lambda_event_input_objs: dict = field(default_factory=defaultdict)
    input_parameter: List[ast.Assign] = field(default_factory=list)
    return_objects: list = field(default_factory=list)
    import_name_list: list = field(default_factory=list)
    lambda_input_per_if_statement: dict = field(default_factory=defaultdict)
    parse_input_per_if_statement: dict = field(default_factory=defaultdict)
    return_obj_per_if_statement: dict = field(default_factory=defaultdict)


@dataclass
class CompilerGeneratedLambdaForIFMainObject:
    lambda_name: str
    lambda_based_module_ast_object: ast.Module
    original_if_main_ast_object: ast.FunctionDef
    # lambda_event_input_objs: List[ast.Assign] = field(default_factory=list)
    # import_info_dict: dict = field(default_factory=defaultdict)


@dataclass
class LambdaHandlerModuleObject:
    module_object = ast.Module


@dataclass
class AnnotationClass:
    lambda_pragma: str = "# Pragma BEU FaaS"
    vm_pragma: str = "# Pragma BEU IaaS"
    hybrid_pragma: str = "# Pragma BEU {IaaS, FaaS}"


@dataclass
class LambdaDeployInfo:
    # lambda_name: str
    original_func_name: str
    lambda_zip_name: str
    lambda_name_to_make_on_aws: str
    lambda_arn: str
    handler_name: str
    zip_file_name_in_s3: str
    aws_role: str = "arn:aws:iam::206135129663:role/mj_boss"
    region: str = "us-east-1"
    runtime: str = "python3.7"
    memory_size: int = 512
    time_out: int = 100


@dataclass
class FunctionWithPragma:
    function_name: str = None
    pragma: str = "Both"


@dataclass
class WholeASTInfoClass:
    file_name: str

    # Module
    original_code_module: ast.Module
    copied_module_for_analysis: ast.Module
    hybrid_code_module: ast.Module = None
    annotated_code_module_for_user: ast.Module = None

    # If offloading whole application
    # pragma_exist_in_main_function: bool = False
    offloading_whole_application: bool = False

    # Import Information
    import_information: Dict[str, ImportInfoClass] = field(default_factory=dict)
    # imports_from_python_script: List[str] = field(default_factory=list)
    boto3_and_json_imports: Dict[str, Boto3AndJsonImportClass] = field(
        default_factory=dict
    )

    # Function and Non-Function and Function Call
    non_function_object_info: Dict[
        Union[ast.Expr, ast.Assign], NonFunctionInfoClass
    ] = field(default_factory=dict)

    function_information: Dict[str, FunctionDefinition] = field(default_factory=dict)
    function_list_for_annotation: List[str] = field(default_factory=list)
    sort_by_lambda_group: Dict[str, List] = field(default_factory=dict)

    function_call_info_class: Dict[
        Union[ast.Expr, ast.Assign], FunctionCallInfo
    ] = field(default_factory=dict)

    # When there is if __main__ object
    objects_inside_if_main: dict = field(default_factory=defaultdict)
    function_call_inside_if_main: dict = field(default_factory=defaultdict)

    # # When offloading whole application
    module_info_for_offloading_whole_app: CompilerGeneratedLambda = None
    deployment_name_for_offloading_whole_app: str = None
    #
    # services_for_function: dict = field(default_factory=defaultdict)
    parsed_function_info_for_faas: dict = field(default_factory=defaultdict)
    if_main_object: NonFunctionInfoClass = None
    # # non_func_object_to_info_class_dict: dict =
    # # field(default_factory=NonFunctionInfoClass)
    func_call_using_lambda: list = field(default_factory=list)
    combined_func_call_using_lambda: Dict[str, List] = field(default_factory=dict)
    lambda_invoke_function: ast.FunctionDef = None
    # compiler_generated_lambda_handler_dict: dict = field(default_factory=defaultdict)
    lambda_handler_module_dict: dict = field(default_factory=defaultdict)
    #
    lambda_function_info: dict = field(default_factory=defaultdict)
    lambda_deployment_zip_info: dict = field(default_factory=defaultdict)
    lambda_config_for_whole_application: LambdaConfig = None
    # metrics_for_whole_application: FunctionMetricRules = None

    # raw_pragma_and_metrics_in_main_function: list = field(default_factory=list)
    # main_func_info_parsed_to_loadbalancer: FunctionWithServiceCandidate = None
    map_func_to_func_arn_object: ast.Assign = None


def find_user_annotation_in_code(whole_info_class: WholeASTInfoClass, ):
    """
    Let users choose which functions they want to annotate
    """

    logger.info("Find pragma")

    whole_module = whole_info_class.copied_module_for_analysis

    func_information = defaultdict(FunctionDefinition)
    func_names_to_annotate = []

    # function_list_with_services = {
    #     "Lambda": defaultdict(),
    #     "VM": defaultdict(),
    #     "Both": defaultdict(),
    # }

    # Find pragma before annotation
    for child in ast.iter_child_nodes(whole_module):
        if isinstance(child, ast.FunctionDef):

            f_def_class = FunctionDefinition(
                func_name=child.name, ast_object=child, line_number=child.lineno
            )

            f_def_class = find_pragma_in_function(child, f_def_class)

            # Save function info
            func_information[child.name] = f_def_class

            # No pragma then compiler will provide user annotation
            if f_def_class.initial_pragma is None:
                func_names_to_annotate.append(child.name)

            # Main function and Pragma BEU FaaS  -> Offloading whole app
            if f_def_class.initial_pragma == "FaaS" and f_def_class.func_name == "main":
                logger.info("\tWill offload whole application")
                whole_info_class.offloading_whole_application = True

    # logger.debug(func_information)

    whole_info_class.function_information = dict(func_information)
    whole_info_class.function_list_for_annotation = func_names_to_annotate

    # whole_info_class.function_list_with_services = dict(function_list_with_services)

    # Skipping user annotation for now
    # else:
    #     # Function annotation with services
    #     func_to_annotate = choose_functions_to_annotate(func_names_to_annotate)
    #
    #     if not func_to_annotate.strip():
    #         logger2.info("[Faas, IaaS] to all functions")
    #
    #     elif func_to_annotate == "whole":
    #         set_configuration_for_whole_app(func_information, whole_info_class)
    #         return
    #
    #     else:
    #         func_to_annotate = [x.strip() for x in func_to_annotate.split(",")]
    #
    #         # Iterate each function
    #         for each_func_name in func_to_annotate:
    #             set_config_for_each_function(
    #                 each_func_name, func_information, function_list_with_services,
    #             )
    #
    #     # Add remaining_func_list to {IaaS, FaaS}
    #     remaining_func_list = [
    #         f for f in func_names_to_annotate if f not in func_to_annotate
    #     ]
    #     function_list_with_services["Both"] = remaining_func_list
    #
    #     # Save function info and function with service candidate
    #     whole_info_class.function_definition = dict(func_information)
    #     whole_info_class.services_for_function = dict(function_list_with_services)


def choose_functions_to_annotate(func_names_to_annotate):
    functions_to_annotate = input(
        f"Choose functions you want to annotate "
        f"(f1, f2) or whole : {func_names_to_annotate}\n"
    )
    # functions_to_annotate = "whole"
    return functions_to_annotate


def set_config_for_each_function(
        each_func_name, map_func_name_to_function_info_class, service_info_per_functions
):
    # Lambda, VM, Both
    func_service = provide_user_with_service_type(each_func_name)  # FIXME :test

    # Get FunctionDefinition for each function
    function_info: FunctionDefinition = map_func_name_to_function_info_class[
        each_func_name
    ]
    # Write service type for each function
    if func_service.strip():

        function_info.service_type_for_function.service_type = func_service

        save_service_per_function(
            service_info_per_functions, func_service, each_func_name
        )

        # In case of using FaaS, need to set lambda runtime conf
        if func_service in ("{IaaS, FaaS}", "FaaS"):
            # Lambda configuration
            provide_user_with_lambda_config(function_info, each_func_name)

            # Scaling Policy Metrics
            provide_user_with_cpu_utilization(function_info)
            provide_user_with_arrival_rate(function_info)
            provide_user_with_memory_utilization(function_info)


def set_configuration_for_whole_app(
        map_func_name_to_function_info_class, whole_info_class
):
    logger.info("Annotating Whole Application")

    whole_info_class.offloading_whole_application = True
    whole_info_class.function_information = dict(map_func_name_to_function_info_class)

    logger.info("Setting Metrics for whole application")

    lambda_config = set_lambda_config_for_whole_app()
    whole_info_class.lambda_config_for_whole_application = lambda_config

    metrics_for_whole_app = set_metrics_for_whole_app()
    whole_info_class.metrics_for_whole_application = metrics_for_whole_app


def find_pragma_in_function(child, func_def: FunctionDefinition):
    # Iterate child node in function definition
    for child_node in ast.iter_child_nodes(child):

        # Find comment
        if isinstance(child_node, ast.Expr):
            if isinstance(child_node.value, ast.Str):
                split_comments = child_node.value.s.strip().split()

                # Iterator
                it = iter(split_comments)

                # Fetch function metric rules
                func_metrics = FunctionMetricRules()

                iterate_comments_and_save_pragma(func_def, func_metrics, it)

    return func_def


def iterate_comments_and_save_pragma(func_def, function_metric_rules, it):
    try:
        while True:

            c = next(it)
            # logger.debug(c)
            if c == "Pragma":
                if next(it) == "BEU":
                    func_def.initial_pragma = next(it)

            if c == "Combine":
                func_def.lambda_group_name = next(it)

            if c == "Metric":
                c = next(it)

                if "arrival_rate" in c:
                    function_metric_rules.use_default_value_for_arrival_rate = False
                    function_metric_rules.arrival_rate_operator = next(it)
                    function_metric_rules.arrival_rate_operand = next(it)[:-1]

                elif "cpu_util" in c:
                    function_metric_rules.use_default_value_for_cpu_util = False
                    function_metric_rules.cpu_util_operator = next(it)
                    function_metric_rules.cpu_util_operand = next(it)[:-1]

                elif "memory_util" in c:
                    function_metric_rules.use_default_value_for_memory_util = False
                    function_metric_rules.memory_util_operator = next(it)
                    function_metric_rules.memory_util_operator = next(it)[:-1]

    except StopIteration:
        pass

    func_def.function_metric_rules = function_metric_rules


def see_if_main_function_has_pragma(child, split_comments, whole_info_class):
    if child.name == "main":
        whole_info_class.pragma_exist_in_main_function = True
        whole_info_class.raw_pragma_and_metrics_in_main_function = split_comments


def set_metrics_for_whole_app():
    logger.info("Setting metrics for whole application")

    metrics_for_whole_app = FunctionMetricRules()

    # cpu_util = input('cpu_util (80):\n')
    # cpu_util_operator = input(f'operator (>=):\n')
    cpu_util, cpu_util_operator = "", ""

    if cpu_util.strip():
        metrics_for_whole_app.cpu_util_operand = int(cpu_util)
        metrics_for_whole_app.use_default_value_for_cpu_util = False

    if cpu_util_operator.strip():
        metrics_for_whole_app.cpu_operator = cpu_util_operator
        metrics_for_whole_app.use_default_value_for_cpu_util = False

    # arrival_rate = input(f'arrival_rate (5) :\n')
    # arrival_rate_operator = input(f'operator (>=):\n')
    arrival_rate, arrival_rate_operator = "5", ">="

    if arrival_rate.strip():
        metrics_for_whole_app.arrival_rate_operand = int(arrival_rate)
        metrics_for_whole_app.use_default_value_for_arrival_rate = False

    if arrival_rate_operator.strip():
        metrics_for_whole_app.arrival_rate_operator = arrival_rate_operator
        metrics_for_whole_app.use_default_value_for_arrival_rate = False

    # memory_util = input(f'memory_util (70):\n')
    # memory_util_operators = input(f'operator : (>=) :\n')
    memory_util, memory_util_operators = "", ""

    if memory_util.strip():
        metrics_for_whole_app.memory_util_operand = int(memory_util)
        metrics_for_whole_app.use_default_value_for_memory_util = False

    if memory_util_operators.strip():
        metrics_for_whole_app.memory_util_operator = memory_util_operators
        metrics_for_whole_app.use_default_value_for_memory_util = False

    return metrics_for_whole_app


def set_lambda_config_for_whole_app():
    logger.info("Lambda configuration for whole application")
    lambda_config_for_whole_app = LambdaConfig()

    # lambda_memory = input(f"lambda_config : [memory_size (512):\n")
    lambda_memory = ""
    if lambda_memory.strip():
        lambda_config_for_whole_app.memory_size = lambda_memory

    # lambda_timeout = input(f'lambda_config '
    #                               f': [time_out (100):\n')
    lambda_timeout = ""
    if lambda_timeout.strip():
        lambda_config_for_whole_app.timeout = lambda_timeout

    # lambda_runtime = input(f'lambda_config : '
    #                               f'[runtime (py37):\n')
    lambda_runtime = ""
    if lambda_runtime.strip():
        lambda_config_for_whole_app.runtime = lambda_runtime

    # lambda_name = input(f'lambda_config : '
    #                               f'[name (None):\n')
    lambda_name = "resnet18_lambda"  # FIXME: for test
    if lambda_name.strip():
        lambda_config_for_whole_app.function_name = lambda_name

    return lambda_config_for_whole_app


def provide_user_with_service_type(each_func_name):
    # Input for Service Type
    mixture_pragma = "IaaS, FaaS, {IaaS, FaaS}(default)"

    # func_service = input(
    #     f"{each_func_name} configuration : " f"service type - {mixture_pragma}:\n "
    # )

    func_service = "FaaS"  # FIXME: for test -> comment later

    return func_service


def provide_user_with_memory_utilization(function_info):
    # memory_util = input(f'{each_func_name} target metrics : memory_util (70):\n')
    # memory_util_operators = input(f'{each_func_name} operator : (>=) :\n')
    memory_util, memory_util_operators = "", ""  # FIXME: for test -> comment later

    if memory_util != "":
        function_info.function_metric_rules.memory_util_operand = int(memory_util)
        function_info.function_metric_rules.use_default_value_for_memory_util = False

    if memory_util_operators != "":
        function_info.function_metric_rules.memory_util_operator = memory_util_operators
        function_info.function_metric_rules.use_default_value_for_memory_util = False


def provide_user_with_arrival_rate(function_info):
    # arrival_rate = input(f'{each_func_name} target metrics : arrival_rate (5) :\n')
    # arrival_rate_operator = input(f'{each_func_name} target metrics :operator (>=):\n')
    # FIXME: for test -> comment later
    arrival_rate, arrival_rate_operator = "5", ">="

    if arrival_rate != "":
        function_info.function_metric_rules.arrival_rate_operand = int(arrival_rate)
        function_info.function_metric_rules.use_default_value_for_arrival_rate = False

    if arrival_rate_operator != "":
        function_info.function_metric_rules.arrival_rate_operator = (
            arrival_rate_operator
        )
        function_info.function_metric_rules.use_default_value_for_arrival_rate = False


def provide_user_with_cpu_utilization(function_info):
    # cpu_util = input(f'{each_func_name}:metrics : cpu_util (80):\n')
    # cpu_util_operator = input(f'{each_func_name}:metrics : operator (>=):\n')
    cpu_util, cpu_util_operator = "", ""  # FIXME: for test -> comment later

    if cpu_util != "":
        function_info.function_metric_rules.cpu_util_operand = int(cpu_util)
        function_info.function_metric_rules.use_default_value_for_cpu_util = False

    if cpu_util_operator != "":
        function_info.function_metric_rules.cpu_operator = cpu_util_operator
        function_info.function_metric_rules.use_default_value_for_cpu_util = False


def provide_user_with_lambda_config(function_info, each_func_name):
    # Memory
    # lambda_config_memory = input(f'{each_func_name} lambda_config '
    #                              f': [memory_size (512):\n')
    lambda_config_memory = ""  # FIXME: for test -> comment later
    if lambda_config_memory.strip():
        function_info.lambda_runtime_conf.memory_size = lambda_config_memory

    # timeout
    # lambda_config_timeout = input(f'{each_func_name} lambda_config '
    #                               f': [time_out (100):\n')
    lambda_config_timeout = ""  # FIXME: for test
    if lambda_config_timeout.strip():
        function_info.lambda_runtime_conf.timeout = lambda_config_timeout

    # Lambda Runtime
    # lambda_config_runtime = input(f'{each_func_name} lambda_config : '
    #                               f'[runtime (py37):\n')
    lambda_config_runtime = ""  # FIXME: for test
    if lambda_config_runtime.strip():
        function_info.lambda_runtime_conf.runtime = lambda_config_runtime


def save_service_per_function(service_for_functions, func_service, each_func_name):
    """
    Save service type for each function
    """
    if func_service == "IaaS":
        service_for_functions["VM"].append(each_func_name)

    elif func_service == "FaaS":
        service_for_functions["Lambda"].append(each_func_name)


def parse_info_for_functions(whole_ast_info: WholeASTInfoClass):
    """
    make information : function and function rules for parsing to loadbalancer
    """

    logger.info("Parse info for functions")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Info exist in function definition")
        # parse_and_save_info_for_whole_application(whole_ast_info)

    else:
        parse_and_save_info_for_each_function(whole_ast_info)


def parse_and_save_info_for_each_function(whole_ast_info: WholeASTInfoClass):
    function_info_dict = whole_ast_info.function_information
    services_for_function = whole_ast_info.function_list_with_services

    function_with_service_candidate = defaultdict()

    for service_type, function_list in services_for_function.items():

        # Iterate each service
        for each_function_name in function_list:

            # fetch function info for each function
            function_info: FunctionDefinition = function_info_dict.get(
                each_function_name
            )
            # Put information about initial pragma
            if function_info.initial_pragma:
                function_with_service_candidate[
                    each_function_name
                ] = FunctionWithServiceCandidate(
                    service_candidate=function_info.initial_pragma,
                    merge_function=function_info.merge_function,
                )

            # fetch scaling policy for each function from user annotation
            else:
                metrics_for_scaling_policy = function_info.function_metric_rules

                metrics_dict = defaultdict(list)

                # Add metrics with compare_operators
                if metrics_for_scaling_policy.use_default_value_for_memory_util:
                    pass

                else:  # False means user annotation
                    metrics_dict["memory_util"].append(
                        metrics_for_scaling_policy.memory_util_operand
                    )
                    metrics_dict["memory_util"].append(
                        metrics_for_scaling_policy.memory_util_operator
                    )

                if metrics_for_scaling_policy.use_default_value_for_cpu_util:
                    pass
                else:
                    metrics_dict["cpu_util"].append(
                        metrics_for_scaling_policy.cpu_util_operand
                    )
                    metrics_dict["cpu_util"].append(
                        metrics_for_scaling_policy.cpu_operator
                    )

                if metrics_for_scaling_policy.use_default_value_for_arrival_rate:
                    pass

                else:
                    metrics_dict["arrival_rate"].append(
                        metrics_for_scaling_policy.arrival_rate_operand
                    )
                    metrics_dict["arrival_rate"].append(
                        metrics_for_scaling_policy.arrival_rate_operator
                    )

                function_with_service_candidate[
                    each_function_name
                ] = FunctionWithServiceCandidate(
                    service_candidate=service_type,
                    rules_for_scaling_policy=metrics_dict,
                )

    logging.debug("\n" + pformat(dict(function_with_service_candidate)))
    whole_ast_info.parsed_function_info_for_faas = function_with_service_candidate


# def parse_and_save_info_for_whole_application(whole_ast_info):
#     main_info = whole_ast_info.function_information.get("main")
#
#     service_with_metric_for_whole_app = FunctionWithServiceCandidate()
#     metrics_dict = defaultdict(deque)
#     it = iter(pragma_and_metrics)
#     # logger2.debug(pragma_and_metrics)
#     try:
#         while True:
#             c = next(it)
#             if c == "BEU":
#                 service_with_metric_for_whole_app.service_candidate = next(it)
#
#             if c == "Metric":
#                 c = next(it)
#                 if "arrival_rate" in c:
#                     metrics_dict[c].appendleft(next(it))
#                     metrics_dict[c].appendleft(next(it)[:-1])
#                 if "cpu_util" in c:
#                     metrics_dict[c].appendleft(next(it))
#                     metrics_dict[c].appendleft(next(it)[:-1])
#                 if "memory_util" in c:
#                     metrics_dict[c].appendleft(next(it))
#                     metrics_dict[c].appendleft(next(it)[:-1])
#
#     except StopIteration:
#         pass
#
#     for _, value in metrics_dict.items():
#         value = list(value)
#     service_with_metric_for_whole_app.rules_for_scaling_policy = metrics_dict
#     whole_ast_info.main_func_info_parsed_to_loadbalancer = (
#         service_with_metric_for_whole_app
#     )


def show_result(whole_info):
    logger.debug("\n" + pformat(whole_info.__dict__))


def put_faas_pragma(beu_pragma_to_add, func_info_class):
    """
    Put FaaS pragma in case of [IaaS, FaaS] or FaaS. Also will put scaling policy metrics
    """
    metrics_for_lb = func_info_class.function_metric_rules

    # Add scaling policy metrics if user annotation
    metrics_to_add = []
    if not metrics_for_lb.use_default_value_for_arrival_rate:
        metrics_to_add.append(
            f"arrival_rate "
            f"{metrics_for_lb.arrival_rate_operator} "
            f"{metrics_for_lb.arrival_rate_operand}"
        )

    if not metrics_for_lb.use_default_value_for_cpu_util:
        metrics_to_add.append(
            f"cpu_util {metrics_for_lb.cpu_operator} {metrics_for_lb.cpu_util_operand}"
        )

    if not metrics_for_lb.use_default_value_for_memory_util:
        metrics_to_add.append(
            f"memory_util "
            f"{metrics_for_lb.memory_util_operator} {metrics_for_lb.memory_util_operand}"
        )

    # Remove quote in element in list
    translation = {39: None}
    beu_pragma_to_add = (
        f"\n\t{beu_pragma_to_add} " f"{str(metrics_to_add).translate(translation)}\n\t"
    )

    # Make or attach pragma to comment
    comment_node = [
        child
        for child in ast.iter_child_nodes(func_info_class.ast_object)
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Str)
    ]
    if comment_node:
        comment_node[0].value.s = comment_node[0].value.s + beu_pragma_to_add + "\n\t"
    else:
        func_info_class.ast_object.body.insert(
            0, ast.Expr(value=ast.Str(s=beu_pragma_to_add))
        )
    ast.fix_missing_locations(func_info_class.ast_object)


def put_iaas_pragma(func_info_class, pragma_class):
    """
    Put IaaS Pragma -> No metrics needed
    """
    comment_node = [
        child
        for child in ast.iter_child_nodes(func_info_class.ast_object)
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Str)
    ]
    if comment_node:
        comment_node[0].value.s = (
                comment_node[0].value.s + pragma_class.vm_pragma + "\n\t"
        )
    else:
        func_info_class.ast_object.body.insert(
            0, ast.Expr(value=ast.Str(s=pragma_class.vm_pragma))
        )

    ast.fix_missing_locations(func_info_class.ast_object)


def put_pragma_comment_in_func(func_info_class: FunctionDefinition):
    """
    Put Pragma comment in function
    """
    pragma_class = AnnotationClass()

    if func_info_class.service_type_for_function.service_type == "IaaS":
        put_iaas_pragma(func_info_class, pragma_class)

    if func_info_class.service_type_for_function.service_type in [
        "FaaS",
        "{IaaS, FaaS}",
    ]:
        pass
        # put_faas_pragma(pragma_class.lambda_pragma, func_info_class)
        # TODO: Comment above line since we are focusing on static phase

    # elif func_info_class.service_type_for_function.service_type == "{IaaS, FaaS}":
    #     put_faas_pragma(pragma_class.hybrid_pragma, func_info_class)


def put_pragma_in_functions(whole_ast_info: WholeASTInfoClass, tree: ast.AST):
    """
    Add pragma in function from user chosen functions
    """

    logger.info("Skip since we focus on already pragma exist")

    # Whole Application
    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Check if pragma already exist")

        # if whole_ast_info.offloading_whole_application:
        #     logger.info("Already pragma for whole application -> Skipping")
        #     return
        # else:
        #     # logger2.info(whole_ast_info.lambda_config_for_whole_application)
        #
        #     logger.info("Metrics for offloading whole application")
        #     logger.info(
        #         f"Function config : {whole_ast_info.lambda_config_for_whole_application}"
        #     )
        #     metrics = whole_ast_info.metrics_for_whole_application
        #     if not metrics.use_default_value_for_cpu_util:
        #         logger.info(f"CPU -> {metrics.cpu_util_operand} {metrics.cpu_operator}")
        #     if not metrics.use_default_value_for_arrival_rate:
        #         logger.info(
        #             f"Arrival Rate : {metrics.arrival_rate_operand}"
        #             f" {metrics.arrival_rate_operator}"
        #         )
        #     if not metrics.use_default_value_for_memory_util:
        #         logger.info(
        #             f"Memory -> {metrics.memory_util_operand} {metrics.memory_util_operator}"
        #         )

    # else:
    #
    #     function_dict_name_to_object = whole_ast_info.function_information
    #
    #     function_info_class: FunctionDefinition
    #
    #     for _, function_info_class in function_dict_name_to_object.items():
    #
    #         if function_info_class.initial_pragma:
    #             continue
    #         else:
    #             put_pragma_comment_in_func(function_info_class)
    #
    #     ast.fix_missing_locations(tree)

    # return


@dataclass
class ModuleConfigClass:
    # File Name
    f_name: str = "resnet18_vm_for_test.py"

    # Workload Result Log
    result_logfile_name: str = "log_folder/result_log/splice_result.log"
    worker_log_file: str = "log_folder/workers_from_lb/workers.json"

    # Compiler Result Log
    bench_dir: str = "../BenchmarkApplication"
    module_dir: str = "import_modules"
    output_path_dir: str = "output"
    lambda_code_dir_path: str = output_path_dir + "/lambda_codes"
    deployment_zip_dir: str = output_path_dir + "/deployment_zip_dir"
    hybrid_code_dir: str = output_path_dir + "/hybrid_vm"
    hybrid_code_file_name: str = "compiler_generated_hybrid_code"
    bucket_for_hybrid_code: str = "coco-hybrid-bucket-mj"
    bucket_for_lambda_handler_zip: str = "faas-code-deployment-bucket"
    # log_folder_dir: str = "coco-hybrid-bucket"


class ImportAndFunctionAnalyzer(ast.NodeVisitor):
    def __init__(
            self, whole_ast_info: WholeASTInfoClass, config_info: ModuleConfigClass,
    ):
        self.whole_ast_info = whole_ast_info
        self.file_name = whole_ast_info.file_name  # benchmark name
        self.target_source_code = whole_ast_info.copied_module_for_analysis  # benchmark

        self.config_info = config_info

    def visit_Import(self, node):
        """
        handle import numpy or import numpy as np
        """
        import_info_class = ImportInfoClass(line_number=node.lineno, ast_object=node)

        # logger2.info(node.names[0].name)

        import_name_to_add = node.names[0].name

        for alias in node.names:
            if "." in alias.name:
                # logger2.info(alias.name)
                import_info_class.import_name = alias.name.split(".")[0]
                import_name_to_add = alias.name.split(".")[0]
            else:
                import_info_class.import_name = alias.name  # numpy

            if alias.asname is not None:  # numpy as np
                import_info_class.import_as.append(alias.asname)

        self.whole_ast_info.import_information[import_name_to_add] = import_info_class
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """
        from multiprocessing import Pool
        from                 import
        """
        import_info_class = ImportInfoClass(line_number=node.lineno, ast_object=node)
        # from multiprocessing.dummy -> multiprocessing
        node_module_name = node.module.split(".")[0]
        import_info_class.import_name = node_module_name
        for alias in node.names:
            if alias.asname:  # from multiprocessing.dummy import Pool as ThreadPool
                import_info_class.from_import.append(
                    alias.asname
                )  # multiprocessing -> ThreadPool
            else:
                import_info_class.from_import.append(alias.name)
        # whole_information.import_information[node.lineno] = import_info_class
        self.whole_ast_info.import_information[node_module_name] = import_info_class
        self.generic_visit(node)

    def find_import_that_is_python_code(self, target_file_name):
        """
        iterate through benchmark directory and find code that is ".py"
        """

        imports_from_python_script = []

        # move to benchmark_dir
        os.chdir(self.config_info.benchmark_dir)

        # Iterate through directory and find python code that is ".py"
        for file in os.listdir(os.getcwd()):
            filename = os.fsdecode(file)
            if (
                    filename.endswith(".py")
                    and filename != os.path.basename(file)
                    and filename != target_file_name
            ):
                imports_from_python_script.append(filename.replace(".py", ""))

        # Iterate imports and mark "True" if import is from python code
        for _, import_info_class in self.whole_ast_info.import_information.items():
            if import_info_class.import_name in imports_from_python_script:
                import_info_class.from_python_script = True

        # move back to original directory
        os.chdir("../..")

    # noinspection PyTypeChecker
    def find_func_call_in_func_obj_assign(
            self, assign_targets_list, child: ast.Assign, node: ast.FunctionDef
    ):
        """
        find function call in assign object in function object
        """

        assign_obj = child

        if isinstance(assign_obj.value, (ast.Call, ast.BinOp)):
            assign_node_value_obj = assign_obj.value

            # iterate and find import from assign value
            for assign_node_value_child in ast.walk(assign_node_value_obj):
                if isinstance(assign_node_value_child, ast.Name):
                    name_id = assign_node_value_child.id  # a = b -> b

                    func_list = list(self.whole_ast_info.function_information.keys())
                    if name_id in func_list:
                        func_call_info_class = FunctionCallInfo(
                            line_number=child.lineno,
                            ast_object=child,
                            object_type="Assign",
                            caller_object=node,
                            caller_object_name=node.name,
                            callee_object=assign_node_value_obj,
                            callee_object_name=name_id,
                            assign_targets=assign_targets_list,
                            call_func_params=assign_node_value_obj.args,
                        )

                        # save it to whole_ast_info
                        self.whole_ast_info.function_call_info_class[
                            child
                        ] = func_call_info_class

    def find_import_in_func_obj_assign(
            self, child, assign_target_list, each_func_info: FunctionDefinition
    ):
        """
        find import in assign object in function object
        """
        assign_obj = child

        if isinstance(assign_obj.value, (ast.Call, ast.BinOp)):

            value_obj = assign_obj.value

            for assign_node_value_child in ast.walk(value_obj):
                self.find_import_list_from_assign_target(
                    assign_node_value_child, assign_target_list, each_func_info
                )

        each_func_info.assign_targets.extend(assign_target_list)

    def find_import_list_from_assign_target(
            self,
            assign_node_value_child,
            assign_targets_list,
            specific_func_dict: (NonFunctionInfoClass, FunctionDefinition),
    ):
        logger.debug(specific_func_dict)
        logger.debug(assign_node_value_child)
        # logger.debug(astor.to_source(assign_node_value_child))

        if isinstance(assign_node_value_child, ast.Name):
            # logger.debug()
            logger.debug(specific_func_dict)
            # use name (not object)
            value_obj = assign_node_value_child.id

            # Iterate target list
            for each_assign_target in assign_targets_list:

                import_info: ImportInfoClass  #
                for (_, import_info) in self.whole_ast_info.import_information.items():
                    if (
                            value_obj in import_info.import_as + import_info.import_as
                            or value_obj == import_info.import_name
                            or value_obj in import_info.assign_targets_from_non_func
                    ):
                        logger.debug(import_info.import_name)

                        import_info.assign_targets_from_non_func.add(each_assign_target)
                        specific_func_dict.import_name_list.add(import_info.import_name)
                        logger.debug(pformat(specific_func_dict))

    def find_func_call_in_func_obj_expr(self, expr_value, expr_node, func_node):
        for expr_value_child in ast.walk(expr_value):
            if isinstance(expr_value_child, ast.Name):

                name_id = expr_value_child.id

                func_list = list(self.whole_ast_info.function_information.keys())

                if name_id in func_list:
                    func_call_info_class = FunctionCallInfo(
                        line_number=expr_node.lineno,
                        ast_object=expr_node,
                        object_type="Expr",
                        caller_object=func_node,
                        caller_object_name=func_node.name,
                        callee_object=expr_value,
                        callee_object_name=name_id,
                        call_func_params=expr_value.args,
                    )
                    self.whole_ast_info.function_call_info_class[
                        expr_node
                    ] = func_call_info_class

    def find_imports_in_expr_obj(
            self, expr_value, specific_func_dict: FunctionDefinition
    ):

        for child_of_expr_value in ast.walk(expr_value):

            if isinstance(child_of_expr_value, ast.Name):
                self.find_import_in_name_object(child_of_expr_value, specific_func_dict)

    def find_import_in_name_object(self, expr_value_child, each_func_info):

        name_id = expr_value_child.id

        import_info: ImportInfoClass
        for _, import_info in self.whole_ast_info.import_information.items():

            if (
                    name_id in import_info.import_as + import_info.from_import
                    or name_id == import_info.import_name
                    or name_id in import_info.assign_targets_from_non_func
            ):
                each_func_info.import_name_list.add(import_info.import_name)

    def find_imports_in_expr_objs_from_non_func_objs(
            self, expr_node: ast.Expr, non_func_obj: NonFunctionInfoClass
    ):
        non_func_obj.non_func_object_type = "Expr"
        non_func_obj.assign_targets = None

        for child in ast.walk(expr_node):
            if isinstance(child, ast.Name):  # b -> child : b
                self.find_import_in_name_object(child, non_func_obj)

    def find_imports_in_assign_objs_from_non_func_objs(
            self,
            assign_node: (ast.Assign, ast.AugAssign),
            non_func_obj_info: NonFunctionInfoClass,
    ):

        # Mark object_type as assign
        non_func_obj_info.non_func_object_type = "Assign"
        assign_targets_list = get_assign_target_in_assign_objs(assign_node)
        logger.debug(non_func_obj_info)
        logger.debug(assign_targets_list)
        # From assign value, if imports
        logger.debug(astor.to_source(assign_node))
        logger.debug((assign_node.value))
        if isinstance(assign_node.value, (ast.Call, ast.BinOp)):
            logger.debug(non_func_obj_info)
            for child in ast.walk(assign_node.value):
                self.find_import_list_from_assign_target(
                    child, assign_targets_list, non_func_obj_info
                )

        # save assign targets in non_func_obj_info
        non_func_obj_info.assign_targets.extend(assign_targets_list)

    def iterate_module_and_analyze(self, module_node: ast.Module):
        """
        Iterate over function and non-function and find expr_node and assign nodes
        """
        for node in ast.iter_child_nodes(module_node):

            # Non-Functional
            if not isinstance(
                    node, (ast.FunctionDef, ast.ImportFrom, ast.Import, ast.If)
            ):
                self.non_function_handle(node)

            # Function object
            elif isinstance(node, ast.FunctionDef):
                self.function_object_handle(node)

            # If main object
            elif isinstance(node, ast.If):
                self.if_main_object_handle(node)

    def non_function_handle(self, node):
        """
        Save non_func_obj_info and find imports in objects
        Parameters
        ----------
        node - None-Function Node
        """
        # Add to whole_information
        non_func_obj = NonFunctionInfoClass(ast_object=node, line_number=node.lineno)
        self.whole_ast_info.non_function_object_info[node] = non_func_obj
        logger.debug(non_func_obj)
        # Assign or Augassign object
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            self.find_imports_in_assign_objs_from_non_func_objs(node, non_func_obj)

        # Expr without comment
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            self.find_imports_in_expr_objs_from_non_func_objs(node, non_func_obj)

    def function_object_handle(self, node: ast.FunctionDef) -> None:
        """
        find expr and assign in function object and find import and function call
        """
        # Add to whole_information
        func_dict = self.whole_ast_info.function_information

        # Fetch function info that corresponds to function name
        each_func_info: FunctionDefinition = func_dict.get(node.name)

        # Add parameters and return info to function object in whole_information
        get_parameters_and_return_objects(node, each_func_info)

        for child in ast.iter_child_nodes(node):

            # Expr Object
            if isinstance(child, ast.Expr):
                self.analyze_expr_objects(child, node, each_func_info)

            # Assign Object
            # TODO - when value is more than 1
            elif isinstance(child, (ast.Assign, ast.AugAssign)):

                # Find imports and function in assign object.
                self.analyze_assign_objects(child, node, each_func_info)

            elif isinstance(child, ast.With):

                for each_with_item in child.items:

                    if isinstance(each_with_item, ast.withitem):
                        call_obj_in_with = each_with_item.context_expr

                        self.find_imports_in_expr_obj(call_obj_in_with, each_func_info)
                        self.find_func_call_in_func_obj_expr(
                            call_obj_in_with, child, node
                        )  # child isn't expr

                # TODO - need to handle body inside with item
                # for fieldname, VALUE in ast.iter_fields(child):
                #     debug(fieldname)
                #     debug(VALUE)

            else:
                remaining_node = child
                for child_node in ast.walk(remaining_node):
                    if isinstance(child_node, ast.Expr):
                        self.analyze_expr_objects(child_node, node, each_func_info)
                    elif isinstance(child_node, (ast.Assign, ast.AugAssign)):
                        self.analyze_assign_objects(child_node, node, each_func_info)
                    elif isinstance(child_node, ast.Name):
                        self.find_import_in_name_object(child_node, each_func_info)

    def if_main_object_handle(self, node):
        """
        if __name__ == main:
        """
        if isinstance(node.test, ast.Compare):

            # Add to whole_information
            non_func_obj = NonFunctionInfoClass(
                ast_object=node, line_number=node.lineno
            )
            self.whole_ast_info.if_main_object = non_func_obj

            if node.test.left.id == "__name__":

                for child_node in node.body:
                    #  Assign
                    if isinstance(child_node, (ast.Assign, ast.AugAssign)):
                        self.find_function_call_of_assign_obj_inside_if_main(child_node)

                    #  Expr
                    elif isinstance(child_node, ast.Expr) and isinstance(
                            child_node.value, ast.Call
                    ):
                        self.find_function_call_of_expr_obj_inside_if_main(child_node)

    def find_function_call_of_assign_obj_inside_if_main(self, child_node):
        # logging.debug(child_node.__dict__)
        non_func_obj = NonFunctionInfoClass(
            ast_object=child_node, line_number=child_node.lineno
        )
        self.whole_ast_info.objects_inside_if_main[child_node] = non_func_obj

        if isinstance(child_node.value, (ast.Call, ast.BinOp)):
            assign_node_value_obj = child_node.value

            for assign_node_value_child in ast.walk(assign_node_value_obj):
                if isinstance(assign_node_value_child, ast.Name):
                    name_id = assign_node_value_child.id  # a = b -> b
                    func_list = list(self.whole_ast_info.function_information.keys())
                    if name_id in func_list:
                        func_call_info_class = FunctionCallInsideIfMain(
                            line_number=child_node.lineno,
                            ast_object=child_node,
                            object_type="Assign",
                            callee_object=assign_node_value_obj,
                            callee_object_name=name_id,
                        )
                        self.whole_ast_info.function_call_inside_if_main.setdefault(
                            child_node, []
                        ).append(func_call_info_class)

    def find_function_call_of_expr_obj_inside_if_main(self, child_node):
        # logging.debug(child_node.__dict__)
        non_func_obj = NonFunctionInfoClass(
            ast_object=child_node, line_number=child_node.lineno
        )
        self.whole_ast_info.objects_inside_if_main[child_node] = non_func_obj
        expr_value = child_node.value
        if isinstance(expr_value, ast.Str):
            pass
        for expr_value_child in ast.walk(expr_value):
            if isinstance(expr_value_child, ast.Name):
                name_id = expr_value_child.id

                func_list = list(self.whole_ast_info.function_information.keys())
                if name_id in func_list:
                    func_call_info_class = FunctionCallInsideIfMain(
                        line_number=child_node.lineno,
                        ast_object=child_node,
                        object_type="Expr",
                        callee_object=expr_value,
                        callee_object_name=name_id,
                    )
                    self.whole_ast_info.function_call_inside_if_main.setdefault(
                        child_node, []
                    ).append(func_call_info_class)

    def analyze_assign_objects(self, child, node, specific_func_dict):

        target_list = get_assign_target_in_assign_objs(child)
        self.find_import_in_func_obj_assign(child, target_list, specific_func_dict)
        self.find_func_call_in_func_obj_assign(target_list, child, node)

    def analyze_expr_objects(
            self,
            child,
            node,
            specific_func_dict: (FunctionDefinition, NonFunctionInfoClass),
    ):
        """
        handle expr object in function or non_func_obj
        """

        # Expr Value Object
        expr_value = child.value

        # Exclude comments
        if isinstance(expr_value, ast.Str):
            pass

        # Find imports and function call_obj
        elif isinstance(expr_value, ast.Call):
            self.find_imports_in_expr_obj(expr_value, specific_func_dict)
            self.find_func_call_in_func_obj_expr(expr_value, child, node)

    # noinspection PyTypeChecker
    def add_boto3_and_json_module(self) -> None:
        """
        add boto3 and json object for Lambda when the code doesn't have them

        """
        # Load import info in whole_information
        import_name_list = list(self.whole_ast_info.import_information.keys())

        if "boto3" not in import_name_list:
            boto3_object = ast.Import(names=[ast.alias(name="boto3", asname=None)])
            boto3_object = ast.fix_missing_locations(boto3_object)
            boto3_info = Boto3AndJsonImportClass(ast_object=boto3_object)
            self.whole_ast_info.boto3_and_json_imports["boto3"] = boto3_info

        if "json" not in import_name_list:
            json_object = ast.Import(names=[ast.alias(name="json", asname=None)])
            json_object = ast.fix_missing_locations(json_object)
            json_info = Boto3AndJsonImportClass(ast_object=json_object)
            self.whole_ast_info.boto3_and_json_imports["json"] = json_info

    def start_analyzing(self):
        """
        Find import that is python code
        Iterate module and analyze all for import statements and functions
        Lastly add boto3 and json imports
        """

        self.find_import_that_is_python_code(self.file_name)

        self.iterate_module_and_analyze(self.target_source_code)

        self.add_boto3_and_json_module()

        # return self.whole_ast_info


def get_parameters_and_return_objects(node, specific_func_dict):
    """
    find parameters and return information in function object

    Parameters
    ----------
    node : ast.FunctionDef
    specific_func_dict : FunctionDefinition
    """
    function_parameters = [
        VALUE
        for obj in node.args.args
        for fieldname, VALUE in ast.iter_fields(obj)
        if fieldname == "arg"
    ]
    specific_func_dict.function_parameters = function_parameters

    # last object
    last_object_in_function = node.body[-1]
    if isinstance(last_object_in_function, ast.Return):

        specific_func_dict.return_object_ast = last_object_in_function

        # when number of return object is more than 2
        if isinstance(last_object_in_function.value, ast.Tuple):
            return_objects = []
            for each_object in last_object_in_function.value.elts:
                return_objects.append(each_object)
            specific_func_dict.return_objects = return_objects

        # return object's number is 1
        elif isinstance(last_object_in_function.value, ast.Name):
            specific_func_dict.return_objects.append(last_object_in_function.value)

        # TODO : Add Subscript - a[3]


def get_assign_target_in_assign_objs(node: (ast.Assign, ast.AugAssign)):
    """
    Get Assign Target for example a = 3 -> get a,    b += 3 -> get b
    """
    assign_targets_list = []

    if isinstance(node, ast.Assign):
        for each_target in node.targets:

            #  In case of tuple assignment e.g., a,b
            if isinstance(each_target, ast.Tuple):
                for each_element in each_target.elts:
                    assign_targets_list.append(each_element.id)

            # In case of Subscript, e.g., a[3]
            elif isinstance(each_target, ast.Subscript):
                # TODO: current is astor.to_source() but there must be better
                # ways
                assign_targets_list.append(
                    str(astor.to_source(each_target)).replace("\n", "")
                )

            #  In general case
            else:
                assign_targets_list.append(each_target.id)

    #  a += 3
    elif isinstance(node, ast.AugAssign):
        if isinstance(node.target, ast.Tuple):
            for each_element in node.target.elts:
                assign_targets_list.append(each_element.id)
        else:
            assign_targets_list.append(node.target.id)

    return assign_targets_list


def make_lambda_based_function(whole_ast_info: WholeASTInfoClass):
    """
    make function lambda based on annotation information
    """

    logger.info("Change function definition to lambda function")

    if whole_ast_info.offloading_whole_application:
        # (later) Replace if main object with lambda name -> Not right now
        # if whole_ast_info.if_main_object:
        #     make_lambda_function_for_if_main_object(whole_ast_info)
        # else:
        #     make_lambda_for_main_function(whole_ast_info)

        logger.info("[Offloading whole app]: Making only one function")

        make_lambda_for_main_function(whole_ast_info)

    else:  # Not whole application
        function_information = whole_ast_info.function_information
        sort_by_lambda_group = whole_ast_info.sort_by_lambda_group

        lambda_number_idx = 1  # lambda_handler number index
        for lambda_group, function_list in sort_by_lambda_group.items():
            if lambda_group == "Default":  # In case of lambda group case
                lambda_number_idx = make_lambda_func_for_default_group(
                    function_information,
                    function_list,
                    lambda_number_idx,
                    whole_ast_info,
                )

            else:
                lambda_number_idx = make_lambda_func_for_lambda_group(
                    function_information,
                    function_list,
                    lambda_number_idx,
                    lambda_group,
                    whole_ast_info,
                )

    return


def make_lambda_func_for_default_group(
        function_information, function_list, lambda_number_idx, whole_ast_info
):
    for each_func_name in function_list:

        original_func_info = function_information.get(each_func_name)

        # Change lambda function name
        func_name = "lambda_handler_" + str(lambda_number_idx)
        function_args = get_default_lambda_function_inputs()

        # Get arguments for function parameters with a = event['a']
        func_call_arguments_list = []  # for function callee
        function_body = []  # a = event['a]
        function_event_input_assign_list = []  # a, b, c
        return_objects = []  # return result

        for each_param in original_func_info.function_parameters:
            # func_call(A,B) -> get A, B
            call_args = ast.Name(id=each_param, ctx=ast.Store())
            func_call_arguments_list.append(call_args)

            # A = event['A'], B = event['B']
            subscript_ast = ast.Subscript(
                value=ast.Name(id="event", ctx=ast.Load()),
                slice=ast.Index(value=ast.Str(s=each_param)),
                ctx=ast.Load(),
            )
            name_ast = ast.Name(id=each_param, ctx=ast.Store())
            assign_ast = ast.Assign(targets=[name_ast], value=subscript_ast)

            # Add A = event['A']
            function_body.append(assign_ast)  # a = event['a']
            # For saving it to lambda function info
            function_event_input_assign_list.append(assign_ast)

        # function callee in lambda handler function
        value_obj = ast.Call(
            func=ast.Name(id=original_func_info.func_name, ctx=ast.Load()),
            args=func_call_arguments_list,
            keywords=[],
        )

        # If return object exist
        if original_func_info.return_objects:
            # Add assign object with main function callee
            assign_target_obj = ast.Name(id="result", ctx=ast.Store())
            assign_ast = ast.Assign(targets=[assign_target_obj], value=value_obj)
            function_body.append(assign_ast)
            # Append return object
            return_obj = ast.Return(value=ast.Name(id="result", ctx=ast.Load()))
            function_body.append(return_obj)
            return_objects.append(return_obj)
        else:
            # Just add function call with no assigned targets
            expr_obj = ast.Expr(value=value_obj)
            function_body.append(expr_obj)
        # Create new lambda handler with main function callee_object
        lambda_handler = ast.FunctionDef(
            name=func_name,
            args=function_args,
            body=function_body,
            decorator_list=[],
            returns=None,
        )
        # Add function definition and lambda handler
        lambda_module = ast.Module(
            body=[original_func_info.ast_object] + [lambda_handler]
        )

        # Save it into whole_information
        compiler_generated_lambda_info = CompilerGeneratedLambda(
            lambda_name=func_name,
            original_ast_object=original_func_info.ast_object,
            lambda_module=lambda_module,
            lambda_handler_func_object=lambda_handler,
            original_func_name=original_func_info.func_name,
            lambda_event_input_objs=function_event_input_assign_list,
            input_parameter=original_func_info.function_parameters,
            return_objects=return_objects,
        )

        whole_ast_info.lambda_function_info[
            original_func_info.func_name
        ] = compiler_generated_lambda_info

        lambda_number_idx += 1
        return lambda_number_idx


def make_lambda_func_for_lambda_group(
        function_information, function_list, lambda_number_idx, lambda_group, whole_ast_info
):
    # Sort function info by line number
    func_info_list = [function_information.get(x) for x in function_list]
    sorted_func_info_list = sorted(func_info_list, key=lambda x: x.line_number)

    # Make object of func_with_params = event['func_with_params']
    subscript_ast = ast.Subscript(
        value=ast.Name(id="event", ctx=ast.Load()),
        slice=ast.Index(value=ast.Str(s="func_with_params")),
        ctx=ast.Load(),
    )
    name_ast = ast.Name(id="func_with_params", ctx=ast.Store())
    func_with_params_assign_ast = ast.Assign(targets=[name_ast], value=subscript_ast)

    # Make func call in lambda_handler
    lambda_event_inputs_per_function = defaultdict(list)
    for func_info in sorted_func_info_list:
        make_func_call_for_grouped_lambda_handler(
            func_info, lambda_event_inputs_per_function
        )

    # Get all the combination for switch case
    lambda_combination_list = []
    for i in range(len(sorted_func_info_list)):
        for subset in itertools.combinations(sorted_func_info_list, i + 1):
            lambda_combination_list.append(subset)

    # Make switch case for every subset of combinations
    if_statement_list = []
    lambda_input_per_if_statement = defaultdict()
    parse_input_per_if_statement = defaultdict()
    return_obj_per_if_statement = defaultdict()
    for each_comb in lambda_combination_list:

        if len(each_comb) == 1:  # Number of function is 1
            make_func_call_for_one_func_combination(
                each_comb,
                if_statement_list,
                lambda_event_inputs_per_function,
                lambda_input_per_if_statement,
                parse_input_per_if_statement,
                return_obj_per_if_statement,
            )
        else:
            make_func_call_for_multiple_funcs_combination(
                each_comb,
                if_statement_list,
                lambda_event_inputs_per_function,
                lambda_input_per_if_statement,
                parse_input_per_if_statement,
                return_obj_per_if_statement,
            )

    lambda_handler = ast.FunctionDef(
        name="lambda_handler_" + str(lambda_number_idx),
        args=get_default_lambda_function_inputs(),
        body=[func_with_params_assign_ast] + if_statement_list,
        decorator_list=[],
        returns=None,
    )

    function_object_list = [x.ast_object for x in sorted_func_info_list]
    lambda_module = ast.Module(body=function_object_list + [lambda_handler])
    ast_object_list = [x.ast_object for x in sorted_func_info_list]

    logger.debug(astor.to_source(lambda_module))

    merged_lambda_info = MergedCompilerGeneratedLambda(
        lambda_group_name="lambda_handler_" + str(lambda_number_idx),
        lambda_name_list=function_list,
        lambda_module=lambda_module,
        lambda_handler_func_object=lambda_handler,
        original_ast_object_list=ast_object_list,
        lambda_event_input_objs=lambda_event_inputs_per_function,
        lambda_input_per_if_statement=lambda_input_per_if_statement,
        parse_input_per_if_statement=parse_input_per_if_statement,
        return_obj_per_if_statement=return_obj_per_if_statement,
    )
    whole_ast_info.lambda_function_info[lambda_group] = merged_lambda_info
    lambda_number_idx += 1
    return lambda_number_idx


def make_func_call_for_one_func_combination(
        each_comb,
        if_statement_list,
        lambda_event_inputs_per_function,
        input_per_if_statement,
        parse_input_per_if_statement,
        return_obj_per_if_statement,
):
    # Tuple -> index0 will be func_info
    func_info = each_comb[0]

    # Add a = event['a']
    lambda_event_input_list = []
    event_input_arg_obj_list = []
    for each_argument in lambda_event_inputs_per_function[func_info.func_name]:
        name_ast = ast.Name(id=each_argument.slice.value.s, ctx=ast.Store())
        assign_ast = ast.Assign(targets=[name_ast], value=each_argument)
        event_input_arg_obj_list.append(assign_ast)
        lambda_event_input_list.append(name_ast)

    # Make if statement
    left_obj = ast.Name(id="func_with_params", ctx=ast.Load())
    ops_obj = [ast.Eq()]
    comparators_obj = [ast.Str(s=func_info.func_name)]
    test_obj = ast.Compare(left=left_obj, ops=ops_obj, comparators=comparators_obj)

    return_objs = []
    if func_info.return_objects:
        return_obj = ast.Return(value=ast.Name(id="result", ctx=ast.Load()))
        return_objs.append(return_obj.value.id)
        if_statement_obj = ast.If(
            test=test_obj,
            body=event_input_arg_obj_list
                 + [func_info.func_call_for_lambda_handler]
                 + [return_obj],
            orelse=[],
        )
    else:
        if_statement_obj = ast.If(
            test=test_obj,
            body=event_input_arg_obj_list + [func_info.func_call_for_lambda_handler],
            orelse=[],
        )
    logger.debug(astor.to_source(if_statement_obj))

    # Add if statement for later putting them in lambda function
    if_statement_list.append(if_statement_obj)
    input_per_if_statement[if_statement_obj] = lambda_event_input_list
    parse_input_per_if_statement[if_statement_obj] = event_input_arg_obj_list
    return_obj_per_if_statement[if_statement_obj] = return_objs


def make_func_call_for_multiple_funcs_combination(
        function_combination_list,
        if_statement_list,
        lambda_event_inputs_per_function,
        input_per_if_statement,
        parse_input_per_if_statement,
        return_obj_per_if_statement,
):
    # get combined_function_name
    lambda_name_list = [func_info.func_name for func_info in function_combination_list]
    combined_function_name = "_and_".join(lambda_name_list)

    # See if first function is an assign object
    first_function_info: FunctionDefinition = function_combination_list[0]

    # If assign object -> output will be used for next function
    if isinstance(first_function_info.func_call_for_lambda_handler, ast.Assign):

        lambda_event_input_list = []
        # Add a = event['a'] for putting this in switch case
        event_input_arg_obj_list = []
        for each_argument in lambda_event_inputs_per_function[
            first_function_info.func_name
        ]:
            logger.debug(astor.to_source(each_argument))
            name_ast = ast.Name(id=each_argument.slice.value.s, ctx=ast.Store())
            assign_ast = ast.Assign(targets=[name_ast], value=each_argument)
            event_input_arg_obj_list.append(assign_ast)
            lambda_event_input_list.append(name_ast)

        # Change remaining_func_call_except_first to use output from first function
        assign_targets = first_function_info.func_call_for_lambda_handler.targets

        remaining_func_call_except_first = [
            x.func_call_for_lambda_handler for x in function_combination_list[1:]
        ]

        # for each_func_call in remaining_func_call_except_first:
        #     logger.debug(astor.to_source(each_func_call))

        # sys.exit(getframeinfo(currentframe()))

        # Change target depending on the last object
        copied_remaining_func_call_except_first = copy.deepcopy(
            remaining_func_call_except_first
        )
        for x in copied_remaining_func_call_except_first:
            x.value.args = assign_targets

        # If condition object
        left_obj = ast.Name(id="func_with_params", ctx=ast.Load())
        ops_obj = [ast.Eq()]
        comparators_obj = [ast.Str(s=combined_function_name)]
        test_obj = ast.Compare(left=left_obj, ops=ops_obj, comparators=comparators_obj)

        # make if statement object
        last_func_info = function_combination_list[-1]
        return_objs = []
        if last_func_info.return_objects:
            return_obj = ast.Return(value=ast.Name(id="result", ctx=ast.Load()))
            return_objs.append(return_obj.value.id)
            if_statement_obj = ast.If(
                test=test_obj,
                body=event_input_arg_obj_list
                     + [first_function_info.func_call_for_lambda_handler]
                     + copied_remaining_func_call_except_first
                     + [return_obj],
                orelse=[],
            )
        else:
            if_statement_obj = ast.If(
                test=test_obj,
                body=event_input_arg_obj_list
                     + [first_function_info.func_call_for_lambda_handler]
                     + copied_remaining_func_call_except_first,
                orelse=[],
            )

        if_statement_list.append(if_statement_obj)
        input_per_if_statement[if_statement_obj] = lambda_event_input_list
        parse_input_per_if_statement[if_statement_obj] = event_input_arg_obj_list
        return_obj_per_if_statement[if_statement_obj] = return_objs


def make_func_call_for_grouped_lambda_handler(
        func_info, lambda_event_inputs_per_function
):
    func_call_arguments_list = []  # for function callee

    for each_param in func_info.function_parameters:
        subscript_ast = ast.Subscript(
            value=ast.Subscript(
                ast.Name(id="event", ctx=ast.Load()),
                slice=ast.Index(value=ast.Str(s=func_info.func_name)),
                ctx=ast.Load(),
            ),
            slice=ast.Index(value=ast.Str(s=each_param)),
            ctx=ast.Load(),
        )

        call_args = ast.Name(id=each_param, ctx=ast.Store())
        func_call_arguments_list.append(call_args)
        logger.debug(astor.to_source(call_args))
        # assign_ast = ast.Assign(targets=[name_ast], value=subscript_ast)

        # func_call_arguments_list.append(subscript_ast)
        lambda_event_inputs_per_function[func_info.func_name].append(subscript_ast)

    # Assign or Expr -> save this in function information
    # resize(image_for_resize) or result = gray_scale(image_for_gray_scale)
    value_obj = ast.Call(
        func=ast.Name(id=func_info.func_name, ctx=ast.Load()),
        args=func_call_arguments_list,
        keywords=[],
    )
    if func_info.return_objects:
        assign_target_obj = ast.Name(id="result", ctx=ast.Store())
        assign_ast = ast.Assign(targets=[assign_target_obj], value=value_obj)
        func_info.func_call_for_lambda_handler = assign_ast
    else:
        expr_obj = ast.Expr(value=value_obj)
        func_info.func_call_for_lambda_handler = expr_obj
        # logger.debug(astor.to_source(expr_obj))
        # sys.exit(getframeinfo(currentframe()))


def make_lambda_function_for_default_group(
        each_func_name, function_information, lambda_number_idx, whole_ast_info
):
    # Get function info class for each function
    original_func_info = function_information.get(each_func_name)

    # Change lambda function name
    func_name = "lambda_handler_" + str(lambda_number_idx)
    function_args = get_default_lambda_function_inputs()

    # Get arguments for function parameters with a = event['a']
    func_call_arguments_list = []  # for function callee
    function_body = []  # a = event['a]
    function_event_input_assign_list = []  # a, b, c
    return_objects = []  # return result

    for each_param in original_func_info.function_parameters:
        # func_call(A,B) -> get A, B
        call_args = ast.Name(id=each_param, ctx=ast.Store())
        func_call_arguments_list.append(call_args)

        # A = event['A'], B = event['B']
        subscript_ast = ast.Subscript(
            value=ast.Name(id="event", ctx=ast.Load()),
            slice=ast.Index(value=ast.Str(s=each_param)),
            ctx=ast.Load(),
        )
        name_ast = ast.Name(id=each_param, ctx=ast.Store())
        assign_ast = ast.Assign(targets=[name_ast], value=subscript_ast)

        # Add A = event['A']
        function_body.append(assign_ast)  # a = event['a']

        # For saving it to lambda function info
        function_event_input_assign_list.append(assign_ast)

    # function callee in lambda handler function
    value_obj = ast.Call(
        func=ast.Name(id=original_func_info.func_name, ctx=ast.Load()),
        args=func_call_arguments_list,
        keywords=[],
    )

    # If return object exist
    if original_func_info.return_objects:

        # Add assign object with main function callee
        assign_target_obj = ast.Name(id="result", ctx=ast.Store())
        assign_ast = ast.Assign(targets=[assign_target_obj], value=value_obj)
        function_body.append(assign_ast)

        # Append return object
        return_obj = ast.Return(value=ast.Name(id="result", ctx=ast.Load()))
        function_body.append(return_obj)
        return_objects.append(return_obj)
    else:

        # Just add function call with no assigned targets
        expr_obj = ast.Expr(value=value_obj)
        function_body.append(expr_obj)

    # Create new lambda handler with main function callee_object
    lambda_handler = ast.FunctionDef(
        name=func_name,
        args=function_args,
        body=function_body,
        decorator_list=[],
        returns=None,
    )

    # Add function definition and lambda handler
    lambda_module = ast.Module(body=[original_func_info.ast_object] + [lambda_handler])

    # Save it into whole_information
    compiler_generated_lambda_info = CompilerGeneratedLambda(
        lambda_name=func_name,
        original_ast_object=original_func_info.ast_object,
        lambda_module=lambda_module,
        lambda_handler_func_object=lambda_handler,
        original_func_name=original_func_info.func_name,
        lambda_event_input_objs=function_event_input_assign_list,
        input_parameter=original_func_info.function_parameters,
        return_objects=return_objects,
    )
    whole_ast_info.lambda_function_info[
        original_func_info.func_name
    ] = compiler_generated_lambda_info


def make_lambda_for_main_function(whole_ast_info: WholeASTInfoClass):
    # Fetch main function definition
    main_function_info = whole_ast_info.function_information.get("main")

    # Lambda function name with parameters
    func_name = "lambda_handler_" + whole_ast_info.file_name.split(".")[0]
    function_args = get_default_lambda_function_inputs()

    # Get arguments for function parameters with a = event['a']
    func_call_arguments_list = []  # for main function callee
    function_body = []  # for a = event['a]
    function_event_input_assign_list = []
    return_objects = []
    for each_param in main_function_info.function_parameters:
        call_args = ast.Name(id=each_param, ctx=ast.Store())

        subscript_ast = ast.Subscript(
            value=ast.Name(id="event", ctx=ast.Load()),
            slice=ast.Index(value=ast.Str(s=each_param)),
            ctx=ast.Load(),
        )

        name_ast = ast.Name(id=each_param, ctx=ast.Store())

        assign_ast = ast.Assign(targets=[name_ast], value=subscript_ast)

        func_call_arguments_list.append(call_args)

        function_body.append(assign_ast)  # a = event['a']
        function_event_input_assign_list.append(assign_ast)

    # Main function callee in lambda handler function
    value_obj = ast.Call(
        func=ast.Name(id=main_function_info.func_name, ctx=ast.Load()),
        args=func_call_arguments_list,
        keywords=[],
    )
    # If return object exist
    if main_function_info.return_objects:

        # Add assign object with main function callee
        assign_target_obj = ast.Name(id="result", ctx=ast.Store())
        assign_ast = ast.Assign(targets=[assign_target_obj], value=value_obj)
        function_body.append(assign_ast)

        # Append return object
        return_obj = ast.Return(value=ast.Name(id="result", ctx=ast.Load()))
        function_body.append(return_obj)
        return_objects.append(return_obj)
    else:

        # Just add function call with no assigned targets
        expr_obj = ast.Expr(value=value_obj)
        function_body.append(expr_obj)

    # Create new lambda handler with main function callee_object
    lambda_handler = ast.FunctionDef(
        name=func_name,
        args=function_args,
        body=function_body,
        decorator_list=[],
        returns=None,
    )

    # Fetch module body and remove if main object
    module_body = whole_ast_info.copied_module_for_analysis.body[:]
    module_body.remove(whole_ast_info.if_main_object.ast_object)

    # Make new module with module body and new lambda handler
    lambda_module = ast.Module(body=module_body + [lambda_handler])

    # Save it into whole_information
    compiler_generated_lambda_info = CompilerGeneratedLambda(
        lambda_name=func_name,
        original_ast_object=main_function_info.ast_object,
        lambda_module=lambda_module,
        lambda_handler_func_object=lambda_handler,
        original_func_name=main_function_info.func_name,
        lambda_event_input_objs=function_event_input_assign_list,
        input_parameter=main_function_info.function_parameters,
        return_objects=return_objects,
    )
    whole_ast_info.module_info_for_offloading_whole_app = compiler_generated_lambda_info


# def make_lambda_handler_from_if_main(function_info, whole_ast_info):
#     # Make lambda function which has function call
#     function_call_info_class = whole_ast_info.function_call_info_class
#     # There is function call
#     if function_call_info_class:
#
#         function_call_info: FunctionCallInfo
#
#         for i, (_, function_call_info) in enumerate(function_call_info_class.items()):
#
#             # function call that is called in main function
#             if function_call_info.caller_object_name == "main":
#                 function_object_that_is_called = function_call_info.caller_object
#
#                 copied_function_object = copy.deepcopy(function_object_that_is_called)
#                 fund_info = function_info.get(function_object_that_is_called.name)
#
#                 # Lambda definition with event and context
#                 copied_function_object.name = "lambda_handler_" + str(i + 1)
#                 copied_function_object.args.args = ["event", "context"]
#
#                 # Lambda parameters
#                 lambda_event_input_objs = []
#                 for each_param in fund_info.function_parameters:
#                     name_ast = ast.Name(id=each_param, ctx=ast.Store())
#                     subscript_ast = ast.Subscript(
#                         value=ast.Name(id="event", ctx=ast.Load()),
#                         slice=ast.Index(value=ast.Str(s=each_param)),
#                         ctx=ast.Load(),
#                     )
#                     assign_ast = ast.Assign(targets=[name_ast], value=subscript_ast)
#                     copied_function_object.body.insert(0, assign_ast)
#                     lambda_event_input_objs.append(assign_ast)
#
#                 # Copy copied module "body"
#                 module_to_copy = whole_ast_info.copied_module_for_analysis
#                 module_body_for_offloading_whole = module_to_copy.body[:]
#
#                 # Replace created function with main function
#                 module_body_for_offloading_whole = [
#                     copied_function_object if x == function_object_that_is_called else x
#                     for x in module_body_for_offloading_whole
#                 ]
#                 # Remove if main object since we don't need it
#                 module_body_for_offloading_whole.remove(
#                     whole_ast_info.if_main_object.ast_object
#                 )
#
#                 # Make module
#                 module_for_offloading_whole_app = ast.Module(
#                     body=module_body_for_offloading_whole
#                 )
#
#                 # Save it into whole_information
#                 compiler_generated_lambda_info = CompilerGeneratedLambdaForIFMainObject(
#                     lambda_name=copied_function_object.name,
#                     original_if_main_ast_object=function_object_that_is_called,
#                     lambda_based_module_ast_object=module_for_offloading_whole_app,
#                 )
#
#                 whole_ast_info.module_info_for_offloading_whole_app = (
#                     compiler_generated_lambda_info
#                 )


# def make_lambda_function_for_if_main_object(whole_ast_info):
#     # fetch if main object if exist
#     if_main_obj_info = whole_ast_info.if_main_object
#     if_main_obj = if_main_obj_info.ast_object
#
#     # Make lambda_handler function
#     function_name = "lambda_handler"
#     # Get function arguments
#     function_args = get_default_lambda_function_inputs()
#     # logger2.info(whole_ast_info.if_main_object.ast_object.__dict__)
#     # Make lambda function and put object inside if main
#     final_function_obj = ast.FunctionDef(
#         name=function_name,
#         args=function_args,
#         body=if_main_obj.body,
#         decorator_list=[],
#         returns=None,
#     )
#
#     # Copy copied module "body" -> body
#     module_to_copy = whole_ast_info.copied_module_for_analysis
#     module_body_for_offloading_whole = module_to_copy.body[:]
#     # Replace created function with if_main_object
#     module_body_for_offloading_whole = [
#         final_function_obj if x == if_main_obj else x
#         for x in module_body_for_offloading_whole
#     ]
#     module_for_offloading_whole_application = ast.Module(
#         body=module_body_for_offloading_whole
#     )
#     # Save it into whole_information
#     compiler_generated_lambda_info = CompilerGeneratedLambdaForIFMainObject(
#         lambda_name=function_name,
#         original_if_main_ast_object=if_main_obj,
#         lambda_based_module_ast_object=module_for_offloading_whole_application,
#     )
#     whole_ast_info.module_info_for_offloading_whole_app = compiler_generated_lambda_info


def get_default_lambda_function_inputs():
    return ast.arguments(
        posonlyargs=[],
        args=[
            ast.arg(arg="event", annotation=None),
            ast.arg(arg="context", annotation=None),
        ],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )


def make_orchestrator_function() -> ast.FunctionDef:
    function_name = "invoke_function_using_lambda"
    function_args_field_obj = return_function_args_object()

    upload_input_obj = make_for_object_of_uploading_input_to_s3()

    invoke_function_and_download_output_to_vm = ast.If(
        test=ast.Name(id="assign_obj", ctx=ast.Load()),
        body=[
            invoke_func_for_assign_obj(),
            parse_result_from_lambda_result(),
            download_output_to_vm(),
            ast.Return(value=ast.Name(id="result", ctx=ast.Load())),
        ],
        orelse=[
            ast.If(
                test=ast.Name(id="expr_obj", ctx=ast.Load()),
                body=[invoke_func_for_expr_obj(), ],
                orelse=[],
            ),
        ],
    )

    function_body = [upload_input_obj, invoke_function_and_download_output_to_vm]

    final_function_obj = ast.FunctionDef(
        name=function_name,
        args=function_args_field_obj,
        body=function_body,
        decorator_list=[],
        returns=None,
    )

    return final_function_obj


def invoke_func_for_expr_obj():
    return ast.Expr(value=make_lambda_invoke_using_client_object())


def make_lambda_invoke_using_client_object():
    return ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="lambda_client", ctx=ast.Load()),
            attr="invoke",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[
            ast.keyword(
                arg="FunctionName",
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="map_func_to_func_arn_dict", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="function_name", ctx=ast.Load()), ],
                    keywords=[],
                ),
            ),
            ast.keyword(arg="InvocationType", value=ast.Str(s="RequestResponse")),
            ast.keyword(
                arg="Payload",
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="json", ctx=ast.Load()),
                        attr="dumps",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="input_dict", ctx=ast.Load()), ],
                    keywords=[],
                ),
            ),
        ],
    )


def download_output_to_vm():
    return ast.If(
        test=ast.Name(id="download_output_from_s3", ctx=ast.Load()),
        body=[
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="s3_client", ctx=ast.Load()),
                        attr="download_file",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Str(s="bucket-for-coco-compiler"),
                        ast.Name(id="result", ctx=ast.Load()),
                        ast.BinOp(
                            left=ast.Str(s="/tmp/"),
                            op=ast.Add(),
                            right=ast.Name(id="result", ctx=ast.Load()),
                        ),
                    ],
                    keywords=[],
                )
            ),
        ],
        orelse=[],
    )


def parse_result_from_lambda_result():
    return ast.Assign(
        targets=[ast.Name(id="result", ctx=ast.Store()), ],
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="json", ctx=ast.Load()), attr="loads", ctx=ast.Load()
            ),
            args=[
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Subscript(
                                    value=ast.Name(id="response", ctx=ast.Load()),
                                    slice=ast.Index(value=ast.Str(s="Payload")),
                                    ctx=ast.Load(),
                                ),
                                attr="read",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[],
                        ),
                        attr="decode",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                ),
            ],
            keywords=[],
        ),
    )


def invoke_func_for_assign_obj():
    return ast.Assign(
        targets=[ast.Name(id="response", ctx=ast.Store()), ],
        value=make_lambda_invoke_using_client_object(),
    )


def return_function_args_object():
    function_parameters = [
        ast.arg(arg="function_name", annotation=None),
        ast.arg(arg="input_dict", annotation=None),
        ast.arg(arg="assign_obj", annotation=None),
        ast.arg(arg="expr_obj", annotation=None),
        ast.arg(arg="input_to_s3", annotation=None),
        ast.arg(arg="download_output_from_s3", annotation=None),
    ]
    function_parameters_default_value = [
        ast.NameConstant(value=False),
        ast.NameConstant(value=False),
        ast.NameConstant(value=False),
        ast.NameConstant(value=False),
    ]
    function_field_args = ast.arguments(
        args=function_parameters,
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=function_parameters_default_value,
    )

    return function_field_args


def make_for_object_of_uploading_input_to_s3():
    return ast.For(
        target=ast.Name(id="each_input", ctx=ast.Store()),
        iter=return_iteration_for_uploading_input_to_s3(),
        body=[return_body_object_for_uploading_input_to_s3()],
        orelse=[],
    )


def return_body_object_for_uploading_input_to_s3():
    return ast.If(
        test=ast.Name(id="input_to_s3", ctx=ast.Load()),
        body=[
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="s3_client", ctx=ast.Load()),
                        attr="upload_file",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.BinOp(
                            left=ast.Str(s="/tmp/"),
                            op=ast.Add(),
                            right=ast.Name(id="each_input", ctx=ast.Load()),
                        ),
                        ast.Str(s="bucket-for-coco-compiler"),
                        ast.Name(id="each_input", ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            ),
        ],
        orelse=[],
    )


def return_iteration_for_uploading_input_to_s3():
    return ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="input_dict", ctx=ast.Load()),
            attr="values",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )


def return_func_call_arguments(function_return_objects) -> List[ast.keyword]:
    """
    Fetch download_output_from_s3, assign_obj, input_to_s3
    Returns
    -------
    list of keywords
    """

    # logging.debug(function_return_objects)

    if function_return_objects:
        ast_keyword_for_download_output_from_s3 = ast.keyword(
            arg="download_output_from_s3", value=ast.NameConstant(value=True)
        )

        args_keywords = [
            ast.keyword(arg="assign_obj", value=ast.NameConstant(value=True)),
            ast.keyword(arg="input_to_s3", value=ast.NameConstant(value=False)),
            ast_keyword_for_download_output_from_s3,
        ]
        return args_keywords
    else:
        ast_keyword_for_download_output_from_s3 = ast.keyword(
            arg="download_output_from_s3", value=ast.NameConstant(value=False)
        )

        args_keywords = [
            ast.keyword(arg="expr_obj", value=ast.NameConstant(value=True)),
            ast.keyword(arg="input_to_s3", value=ast.NameConstant(value=False)),
            ast_keyword_for_download_output_from_s3,
        ]
        return args_keywords

    # ast_keyword_for_download_output_from_s3 = ast.keyword(
    #     arg="download_output_from_s3", value=ast.NameConstant(value=False)
    # )
    #
    # args_keywords = [
    #     ast.keyword(arg="expr_obj", value=ast.NameConstant(value=True)),
    #     ast.keyword(arg="input_to_s3", value=ast.NameConstant(value=True)),
    #     ast_keyword_for_download_output_from_s3,
    # ]
    # return args_keywords


def change_func_call_for_default_lambda_group(
        func_call_obj, func_call_obj_name, whole_ast_info
):
    # Fetch function information
    function_info_class: FunctionDefinition = whole_ast_info.function_information[
        func_call_obj_name
    ]
    function_return_objects = function_info_class.return_objects

    # Change function name to invoke_func_by_lambda
    # resize (a) -> invoke_function_using_lambda(a)
    func_call_obj.func = ast.Name(id="invoke_function_using_lambda", ctx=ast.Load())

    # Make dictionary for function parameters - {'a' : a},
    # invoke_function_using_lambda('resize', {'img_file_name':a)
    str_obj_of_call_func_params, name_obj_of_call_func_params = [], []
    for idx, each_argument in enumerate(func_call_obj.args):
        name_obj_of_call_func_params.append(each_argument)
        str_obj_of_call_func_params.append(each_argument.id)

    # add function parameters - download_output_from_s3, input_to_s3, assign_obj
    func_call_obj.keywords = return_func_call_arguments(function_return_objects)

    logger.debug(astor.to_source(func_call_obj))


def check_data_dependency(
        copied_func_call: FunctionCallInfo, whole_ast_info: WholeASTInfoClass
):
    """
    For function call -> b
    a = b()
    c = d(a)
    Then we mark output_to_s3 = True
    """

    input_dependency(copied_func_call, whole_ast_info)

    output_dependency(copied_func_call, whole_ast_info)


def output_dependency(copied_func_call, whole_ast_info):
    callee_func_name: str = copied_func_call.caller_object_name
    assign_node_target_list: list = copied_func_call.assign_targets
    call_obj: ast.Call = copied_func_call.callee_object

    # Iterate function calls to find dependency
    each_function_call: FunctionCallInfo
    for _, each_function_call in whole_ast_info.function_call_info_class.items():

        # get function call input parameters and call object
        function_call_input_list = [i.id for i in each_function_call.call_func_params]

        # fetch func call object
        calling_obj_from_each_function_call = each_function_call.callee_object

        # check if function calls are in the same function callee object
        if callee_func_name == each_function_call.caller_object_name:

            # check if assign target of copied_func_call is used other function calls

            if set(assign_node_target_list).intersection(set(function_call_input_list)):

                # check if line number for ordering -
                if call_obj.lineno < calling_obj_from_each_function_call.lineno:
                    for each_keyword in call_obj.keywords:
                        if each_keyword.arg == "download_output_from_s3":
                            each_keyword.value.value = True


def input_dependency(copied_func_call, whole_ast_info):
    """
    Input to S3 : True
    :param copied_func_call:
    :param whole_ast_info:
    :return:
    """
    call_func_params = copied_func_call.call_func_params
    call_func_parameters_name = [i.id for i in call_func_params]
    callee_func_name: str = copied_func_call.caller_object_name
    call_obj: ast.Call = copied_func_call.callee_object

    each_function_call: FunctionCallInfo
    for _, each_function_call in whole_ast_info.function_call_info_class.items():

        if each_function_call.object_type == "Assign":

            assign_targets = each_function_call.assign_targets

            calling_obj_from_each_function_call = each_function_call.callee_object

            if callee_func_name == each_function_call.caller_object_name:

                if set(assign_targets).intersection(set(call_func_parameters_name)):

                    if call_obj.lineno > calling_obj_from_each_function_call.lineno:
                        for each_keyword in call_obj.keywords:
                            if each_keyword.arg == "input_to_s3":
                                each_keyword.value.value = True


def function_call_orchestrator(whole_ast_info: WholeASTInfoClass) -> None:
    """
    Make function call to lambda function call
    """

    logger.info("Make function call orchestrator")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Skipping function_call_orchestrator")
        return

    else:
        function_information = whole_ast_info.function_information
        sort_by_lambda_group = whole_ast_info.sort_by_lambda_group

        # Fetch function that is lambda
        function_of_lambda = []
        for func_list in sort_by_lambda_group.values():
            function_of_lambda.extend(func_list)

        # Find function call whose calling object is in lambda based function
        func_call = whole_ast_info.function_call_info_class
        func_call_of_lambda = [
            x
            for x in list(func_call.values())
            if x.callee_object_name in list(function_of_lambda)
        ]

        # Sort above func call by line number
        func_call_of_lambda = sorted(func_call_of_lambda, key=lambda x: x.line_number)

        # Group by lambda group name
        group_func_call = defaultdict(list)
        for x in func_call_of_lambda:
            for group_name, func_list in sort_by_lambda_group.items():
                if x.callee_object_name in func_list:
                    group_func_call[group_name].append(x)

        # Make lambda call orchestrator function
        if func_call_of_lambda:
            make_function_orchestrator_func(whole_ast_info)

        # For lambda group
        # Sort function definition by line number
        func_info_list = [function_information.get(x) for x in function_of_lambda]
        sorted_func_info_list = sorted(func_info_list, key=lambda x: x.line_number)
        sorted_func_name_list = [x.func_name for x in sorted_func_info_list]

        for lambda_group, func_call_list in group_func_call.items():
            if lambda_group == "Default":

                for idx, each_func_call_info in enumerate(func_call_list):
                    # Copy function_call_info_class. Need original later for dependency
                    copied_func_call = copy.deepcopy(each_func_call_info)
                    func_call_obj: ast.Call = copied_func_call.callee_object
                    func_call_obj_name = copied_func_call.callee_object_name

                    # Add it to whole_information
                    whole_ast_info.func_call_using_lambda.append(
                        LambdaBasedFunctionCallInfoClass(
                            copied_func_call_info=copied_func_call,
                            original_func_call_info=each_func_call_info,
                        )
                    )

                    change_func_call_for_default_lambda_group(
                        func_call_obj, func_call_obj_name, whole_ast_info
                    )
                    check_data_dependency(copied_func_call, whole_ast_info)

            else:
                logger.debug("lambda_group")
                merge_func_call = True
                logger.debug(sort_by_lambda_group.get(lambda_group))
                logger.debug(func_call_list)
                func_name_list = sort_by_lambda_group.get(lambda_group)
                for i, j in zip(func_call_list, func_name_list):
                    if i.callee_object_name == j:
                        continue
                    else:
                        merge_func_call = False

                if merge_func_call:
                    logger.info("Merge Function Call")

                    first_func_call = func_call_list[0]
                    # Copy function_call_info_class. Need original later for dependency
                    copied_func_call = copy.deepcopy(first_func_call)
                    func_call_obj: ast.Call = copied_func_call.callee_object
                    func_call_obj_name = copied_func_call.callee_object_name

                    lambda_info_list = []
                    first_lambda_info_for_function_call = LambdaBasedFunctionCallInfoClass(
                        copied_func_call_info=copied_func_call,
                        original_func_call_info=first_func_call,
                    )
                    lambda_info_list.append(first_lambda_info_for_function_call)

                    # whole_ast_info.combined_func_call_using_lambda[lambda_group].append(
                    #     first_lambda_info_for_function_call
                    # )

                    function_info_class: FunctionDefinition = whole_ast_info.function_information[
                        func_call_obj_name
                    ]

                    function_parameters = function_info_class.function_parameters
                    function_parameters = [
                        ast.Str(s=each_param) for each_param in function_parameters
                    ]
                    function_return_objects = function_info_class.return_objects

                    # Change function name to invoke_func_by_lambda
                    # resize (a) -> invoke_function_using_lambda(a)
                    func_call_obj.func = ast.Name(
                        id="invoke_function_using_lambda", ctx=ast.Load()
                    )

                    str_obj_of_call_func_params, name_obj_of_call_func_params = [], []
                    for idx, each_argument in enumerate(func_call_obj.args):
                        str_obj_of_call_func_params.append(each_argument.id)
                        name_obj_of_call_func_params.append(each_argument)

                    func_call_obj.args = [
                        ast.Str(s="_and_".join(func_name_list)),
                        ast.Dict(
                            keys=[ast.Str(s="func_with_params")],
                            values=[
                                ast.Dict(
                                    keys=[ast.Str(s="_and_".join(func_name_list))],
                                    values=[
                                        ast.Dict(
                                            keys=function_parameters,
                                            values=name_obj_of_call_func_params,
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ]
                    # Module(body=[Expr(value=Dict(keys=[Str(s='gray_scale_and_resize')], values=[Dict(keys=[Str(s='image_for_gray_scale')], values=[Name(id='modified_image_from_filter', ctx=Load())])]))])
                    # add function parameters - download_output_from_s3, input_to_s3, assign_obj
                    func_call_obj.keywords = return_func_call_arguments(
                        function_return_objects
                    )

                    # logger.debug(astor.to_source((func_call_obj)))
                    # sys.exit(getframeinfo(currentframe()))

                    last_func_call = func_call_list[-1]
                    copied_last_func_call = copy.deepcopy(last_func_call)
                    last_lambda_info_for_function_call = LambdaBasedFunctionCallInfoClass(
                        copied_func_call_info=None,
                        original_func_call_info=last_func_call,
                    )
                    lambda_info_list.append(last_lambda_info_for_function_call)

                    whole_ast_info.combined_func_call_using_lambda[
                        lambda_group
                    ] = lambda_info_list

                    input_dependency(copied_func_call, whole_ast_info)

                    callee_func_name: str = copied_last_func_call.caller_object_name
                    assign_node_target_list: list = copied_last_func_call.assign_targets
                    call_obj: ast.Call = copied_func_call.callee_object

                    # Iterate function calls to find dependency
                    each_function_call: FunctionCallInfo
                    for (
                            _,
                            each_function_call,
                    ) in whole_ast_info.function_call_info_class.items():

                        # get function call input parameters and call object
                        function_call_input_list = [
                            i.id for i in each_function_call.call_func_params
                        ]

                        # fetch func call object
                        calling_obj_from_each_function_call = (
                            each_function_call.callee_object
                        )

                        # check if function calls are in the same function callee object
                        if callee_func_name == each_function_call.caller_object_name:

                            # check if assign target of copied_func_call is used other function calls

                            if set(assign_node_target_list).intersection(
                                    set(function_call_input_list)
                            ):

                                # check if line number for ordering -
                                if (
                                        call_obj.lineno
                                        < calling_obj_from_each_function_call.lineno
                                ):
                                    for each_keyword in call_obj.keywords:
                                        if (
                                                each_keyword.arg
                                                == "download_output_from_s3"
                                        ):
                                            logger.debug(each_keyword.arg)
                                            each_keyword.value.value = True

                    for each_keyword in call_obj.keywords:
                        if each_keyword.arg == "download_output_from_s3":
                            # logger.debug(each_keyword.arg)
                            each_keyword.value.value = False

                    logger.debug(astor.to_source(func_call_obj))
                    logger.debug(astor.to_source(whole_ast_info.lambda_invoke_function))
                    # logger.debug(astor.to_source(whole_ast_info.lambda_function_info))

        return

    #     each_func_call_info: FunctionCallInfo  # Iterate each func call
    #     for idx, each_func_call_info in enumerate(func_call_of_lambda):
    #
    #         # Copy function_call_info_class. Need original later for dependency
    #         copied_func_call = copy.deepcopy(each_func_call_info)
    #         func_call_obj: ast.Call = copied_func_call.callee_object
    #         func_call_obj_name = copied_func_call.callee_object_name
    #
    #         # Find out lambda group name
    #         lambda_group_name = "Default"
    #         for group_name, func_list in sort_by_lambda_group.items():
    #             if func_call_obj_name in func_list:
    #                 lambda_group_name = group_name
    #
    #         if lambda_group_name == "Default":
    #
    #             # Add it to whole_information
    #             whole_ast_info.func_call_using_lambda.append(
    #                 LambdaBasedFunctionCallInfoClass(
    #                     copied_func_call_info=copied_func_call,
    #                     original_func_call_info=each_func_call_info,
    #                 )
    #             )
    #
    #             change_func_call_for_default_lambda_group(
    #                 func_call_obj, func_call_obj_name, whole_ast_info
    #             )
    #             check_data_dependency(copied_func_call, whole_ast_info)
    #
    #         else:
    #
    #             func_name_to_combine = [func_call_obj_name]
    #
    #             func_list = sort_by_lambda_group.get(lambda_group_name)
    #             cur_index = func_list.index(func_call_obj_name)
    #
    #             for i in range(cur_index, len(func_list)):
    #                 next_function = func_list[i + 1]
    #                 next_f_call = func_call_of_lambda[idx + 1]
    #                 next_callee_object_name = next_f_call.callee_object_name
    #                 if next_f_call == next_function:
    #                     logger.debug("yes")
    #
    #             # 포함됬으면 다른 function call 넘어간다
    #
    #             # See if next func call belongs to lambda group with ordering:
    #
    #             next_callee_object_name = next_f_call.callee_object_name
    #
    #             func_list = sort_by_lambda_group.get(lambda_group_name)
    #
    #             if next_callee_object_name in func_list:
    #                 cur_index = func_list.index(func_call_obj_name)
    #                 next_index = func_list.index(next_callee_object_name)
    #                 logger.debug(cur_index)
    #                 logger.debug(next_index)
    #                 # if cur_index < next_index:
    #
    #             sys.exit(getframeinfo(currentframe()))
    #
    #             pass
    #
    # return


def make_function_orchestrator_func(whole_ast_info):
    # Make lambda invoke function depending on the flag
    lambda_invoke_func_obj = make_orchestrator_function()
    whole_ast_info.lambda_invoke_function = lambda_invoke_func_obj


def make_obj_for_uploading_return_obj_to_s3(return_object_list):
    """
    s3_client.upload("Return")
    """
    upload_obj_list = []
    # ast.If(test=ast.Name(id='input_to_s3', ctx=ast.Load()), body=[
    #     ast.Expr(value=ast.Call(
    #         func=ast.Attribute(value=ast.Name(id='s3_client', ctx=ast.Load()), attr='upload_file',
    #                            ctx=ast.Load()),
    #         args=[
    #             ast.BinOp(left=ast.Str(s='/tmp/'), op=ast.Add(),
    #                       right=ast.Name(id='each_input', ctx=ast.Load())),
    #             ast.Str(s='bucket-for-coco-compiler'),
    #             ast.Name(id='each_input', ctx=ast.Load()),
    #         ], keywords=[])),
    # ], orelse=[])
    for each_input_param in return_object_list:
        download_obj = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="s3_client", ctx=ast.Load()),
                    attr="upload_file",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.BinOp(
                        left=ast.Str(s="/tmp/"),
                        op=ast.Add(),
                        right=ast.Name(id=each_input_param, ctx=ast.Load()),
                    ),
                    ast.Str(s="bucket-for-coco-compiler"),
                    ast.Name(id=each_input_param, ctx=ast.Load()),
                ],
                keywords=[],
            )
        )
        upload_obj_list.append(download_obj)

    return upload_obj_list


def make_obj_for_downloading_from_s3(input_param_list):
    """
    s3_client.download("/tmp/")
    """
    download_obj_list = []

    for each_input_param in input_param_list:
        download_obj = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="s3_client", ctx=ast.Load()),
                    attr="download_file",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Str(s="input-output-coco-bucket"),
                    ast.Name(id=each_input_param, ctx=ast.Load()),
                    ast.BinOp(
                        left=ast.Str(s="/tmp/"),
                        op=ast.Add(),
                        right=ast.Name(id=each_input_param, ctx=ast.Load()),
                    ),
                ],
                keywords=[],
            )
        )
        download_obj_list.append(download_obj)

    return download_obj_list


def add_using_s3_in_lambda_handler(whole_ast_info: WholeASTInfoClass) -> None:
    """
    Add downloading input from s3 in lambda handler depending on input
    e.g., put s3_client.download()
    """

    logger.info("Add using s3 and s3 client in lambda handler")

    if whole_ast_info.offloading_whole_application:

        lambda_module_for_whole = whole_ast_info.module_info_for_offloading_whole_app
        lambda_func_object = lambda_module_for_whole.lambda_handler_func_object
        lambda_module = lambda_module_for_whole.lambda_module

        # put for example, a = event['a']
        add_event_input_assign_objs_in_lambda_handler(
            lambda_func_object, lambda_module_for_whole
        )

        add_upload_to_s3_for_return_object(lambda_func_object, lambda_module_for_whole)

        logger.info("Add s3_client and lambda_client if needed")

        if lambda_module_for_whole.lambda_event_input_objs:
            logger.info("Add s3_client")

            # Fetch import name list
            import_name_list = list(whole_ast_info.import_information.keys())

            logger.debug(import_name_list)

            # find if there is already boto3 library
            if "boto3" not in import_name_list:
                logger.info("Add import boto3")
                add_import_boto3_in_lambda_module(lambda_module, whole_ast_info)

                logger.info("Add S3 client")
                add_s3_client_in_lambda_module(lambda_module, whole_ast_info)

                # Add boto3 in import name list and save it to CompilerGeneratedLambda
                import_name_list.append("boto3")
                lambda_module_for_whole.import_name_list = import_name_list

        return

    else:
        func_name_to_function_info_class_dict = whole_ast_info.function_information
        lambda_function_info = whole_ast_info.lambda_function_info

        for _, each_compiler_generated_lambda in lambda_function_info.items():
            if isinstance(each_compiler_generated_lambda, CompilerGeneratedLambda):

                original_func_name = each_compiler_generated_lambda.original_func_name

                original_func_info: FunctionDefinition = (
                    func_name_to_function_info_class_dict.get(original_func_name)
                )

                # Fetch lambda handler function
                lambda_func_object = (
                    each_compiler_generated_lambda.lambda_handler_func_object
                )

                # Make object_list of input_parameters
                object_for_downloading_input = make_obj_for_downloading_from_s3(
                    original_func_info.function_parameters
                )

                # Find the index for last object of event_input_objs in function
                event_input_obj_list = (
                    each_compiler_generated_lambda.lambda_event_input_objs
                )

                last_event_input_obj_index = (
                        lambda_func_object.body.index(event_input_obj_list[-1]) + 1
                )

                # Add objects that download input from s3
                for idx, each_object_for_downloading_input in enumerate(
                        object_for_downloading_input
                ):
                    lambda_func_object.body.insert(
                        idx + last_event_input_obj_index,
                        each_object_for_downloading_input,
                    )

                return_objects = original_func_info.return_objects

                if return_objects:
                    put_return_objs_for_s3(lambda_func_object, return_objects)
            elif isinstance(
                    each_compiler_generated_lambda, MergedCompilerGeneratedLambda
            ):

                logger.debug(each_compiler_generated_lambda)
                lambda_func_object = (
                    each_compiler_generated_lambda.lambda_handler_func_object
                )
                logger.debug(astor.to_source(lambda_func_object))

                lambda_event_input_objs = (
                    each_compiler_generated_lambda.lambda_event_input_objs
                )

                lambda_input_per_if_statement = (
                    each_compiler_generated_lambda.lambda_input_per_if_statement
                )
                logger.debug(lambda_input_per_if_statement)

                for each_ast in lambda_func_object.body:
                    if isinstance(each_ast, ast.If):
                        input_arguments = lambda_input_per_if_statement.get(each_ast)
                        # for each_argument in input_arguments:

                        # Make object_list of input_parameters
                        object_for_downloading_input = make_obj_for_downloading_from_s3(
                            input_arguments
                        )

                        # Find the index for last object of event_input_objs in function
                        event_input_obj_list = each_compiler_generated_lambda.parse_input_per_if_statement.get(
                            each_ast
                        )
                        # logger.debug(each_ast.body)
                        # logger.debug(event_input_obj_list)
                        last_event_input_obj_index = (
                                each_ast.body.index(event_input_obj_list[-1]) + 1
                        )

                        for idx, each_object_for_downloading_input in enumerate(
                                object_for_downloading_input
                        ):
                            each_ast.body.insert(
                                idx + last_event_input_obj_index,
                                each_object_for_downloading_input,
                            )

                        logger.debug(each_compiler_generated_lambda)
                        # logger.debug(last_event_input_obj_index)
                        return_objects = each_compiler_generated_lambda.return_obj_per_if_statement.get(
                            each_ast
                        )
                        if return_objects:
                            put_return_objs_for_s3(each_ast, return_objects)

                        logger.debug(astor.to_source(each_ast))

                        # logger.debug(astor.to_source(each_ast))

                # sys.exit(getframeinfo(currentframe()))
                # logger.debug(astor.to_source(lambda_event_inp       ut_objs["gray_scale"][0]))
                # logger.debug(astor.to_source(lambda_event_input_objs["resize"][0]))

                # sys.exit(getframeinfo(currentframe()))


def add_upload_to_s3_for_return_object(lambda_func_object, lambda_module_for_whole):
    if lambda_module_for_whole.return_objects:
        logger.info("Handling return objects")
        put_return_objs_for_s3(
            lambda_func_object, lambda_module_for_whole.return_objects
        )


def add_s3_client_in_lambda_module(lambda_module, whole_ast_info):
    non_func_info = whole_ast_info.non_function_object_info
    sorted_non_func_info = sorted(
        non_func_info.items(), key=lambda k_v: k_v[1].line_number
    )
    # get the last import ast object
    last_non_func_info = list(sorted_non_func_info[-1])
    last_non_func_obj = last_non_func_info[1].ast_object
    index_for_last_non_func_obj = lambda_module.body.index(last_non_func_obj)
    s3_client_object = make_s3_client()
    lambda_module.body.insert(
        index_for_last_non_func_obj + 1, s3_client_object,
    )
    logger.debug(astor.to_source(lambda_module))


def add_import_boto3_in_lambda_module(lambda_module, whole_ast_info):
    # Fetch import information
    import_info = whole_ast_info.import_information
    # Sort by line number
    sorted_import_info = sorted(import_info.items(), key=lambda k_v: k_v[1].line_number)
    # get the last import ast object
    last_import_info = list(sorted_import_info[-1])
    last_import_obj = last_import_info[1].ast_object
    # Find the index for last import ast object
    index_for_last_import_obj = lambda_module.body.index(last_import_obj)
    # Put import boto3
    lambda_module.body.insert(
        index_for_last_import_obj + 1,
        whole_ast_info.boto3_and_json_imports.get("boto3").ast_object,
    )


def add_event_input_assign_objs_in_lambda_handler(
        lambda_func_object, lambda_module_for_whole
):
    logger.debug(astor.to_source(lambda_module_for_whole.lambda_event_input_objs[-1]))
    logger.debug(astor.to_source(lambda_module_for_whole.lambda_event_input_objs[0]))
    object_for_downloading_input = make_obj_for_downloading_from_s3(
        lambda_module_for_whole.input_parameter
    )
    logger.debug(object_for_downloading_input)
    lambda_event_input_objs = lambda_module_for_whole.lambda_event_input_objs
    logger.debug(astor.to_source(object_for_downloading_input[0]))
    last_event_input_obj_index = (
            lambda_func_object.body.index(lambda_event_input_objs[-1]) + 1
    )
    # Add objects that download input from s3
    for idx, each_object_for_downloading_input in enumerate(
            object_for_downloading_input
    ):
        lambda_func_object.body.insert(
            idx + last_event_input_obj_index, each_object_for_downloading_input
        )


def put_return_objs_for_s3(lambda_func_object, return_objects):
    obj_for_uploading_to_s3 = make_obj_for_uploading_return_obj_to_s3(return_objects)
    for idx, each_obj in enumerate(obj_for_uploading_to_s3):
        lambda_func_object.body.insert(len(lambda_func_object.body) - 1, each_obj)


def make_module_for_lambda_handler(whole_ast_info: WholeASTInfoClass) -> None:
    """
    Make module for each_lambda_handler, add s3 client
    """

    logger.info("Make ast.Module for each lambda function")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Already did in previous function")

        # Fetch import information
        # import_information = whole_ast_info.import_information
        # logging.debug(import_information)

        # Fetch module of offloading whole application
        # module_to_make = whole_ast_info.module_info_for_offloading_whole_app

        return
    else:
        import_info_dict_name_to_class = whole_ast_info.import_information
        non_func_obj_info = whole_ast_info.non_function_object_info
        func_name_to_function_info_class_dict = whole_ast_info.function_information
        lambda_handlers_info = whole_ast_info.lambda_function_info

        # Add import_ast_object and import name list from non-func object
        non_func_import_name_list, non_func_ast_list, = set(), []
        logger.debug(pformat(non_func_obj_info))
        non_func_info: NonFunctionInfoClass
        for non_func_ast, non_func_info in non_func_obj_info.items():
            # logger.debug(non_func_info.import_name_list)
            non_func_import_name_list.update(non_func_info.import_name_list)
            non_func_ast_list.append(non_func_ast)

        logger.debug(non_func_import_name_list)
        logger.debug(non_func_ast_list)
        # sys.exit(getframeinfo(currentframe()))

        s3_client_object = make_s3_client()

        # Iterate through lambda_handlers_info
        each_lambda_handler: [CompilerGeneratedLambda, MergedCompilerGeneratedLambda]
        for l_group_name, each_lambda_handler in lambda_handlers_info.items():
            if l_group_name == "Default":
                pass
            else:

                # import object list for putting in lambda_handler
                import_objects_list = []
                import_name_list = []
                # Make a dictionary (import_info_dict) :
                # import name -> import object and save to ImportInfoClass
                import_info_dict = defaultdict()

                function_name_list = each_lambda_handler.lambda_name_list
                for each_function in function_name_list:
                    original_func_name_info: FunctionDefinition = (
                        func_name_to_function_info_class_dict.get(each_function)
                    )
                    # Add non_func_import_name_list to func_import_set
                    import_name_list.extend(original_func_name_info.import_name_list)
                    # logger.debug(import_name_list)
                    # sys.exit(getframeinfo(currentframe()))

                    import_name_list.extend(non_func_import_name_list)

                    # logger.debug(import_name_list)
                    # sys.exit(getframeinfo(currentframe()))
                    # Add import s3 and s3_client
                    # if "boto3" not in import_name_list:
                    #     import_name_list.append("boto3")

                    logger.debug(import_name_list)

                    logger.debug(non_func_ast_list)
                    # for x in non_func_ast_list:
                    #     logger.debug(astor.to_source(x))
                    # sys.exit(getframeinfo(currentframe()))
                logger.debug(import_name_list)
                # import_name_list = list(set(import_name_list))
                # logger.debug(import_name_list)
                # import_name_list= import_name_list.append(
                #     import_name_list.pop(import_name_list.index('boto3')))

                logger.debug(import_name_list)

                logger.debug(non_func_ast_list)

                for each_import_name in list((import_name_list)):
                    logger.debug(each_import_name)
                    # Add boto3 import and s3_client if it doesn't exist
                    if each_import_name == "boto3":
                        pass
                        # boto3_info = whole_ast_info.boto3_and_json_imports["boto3"]
                        # boto3_ast = boto3_info.ast_object
                        #
                        # import_objects_list.append(boto3_ast)
                        #
                        # import_info_dict[each_import_name] = boto3_ast
                        # # logger.debug(boto3_ast)
                        # # sys.exit(getframeinfo(currentframe()))
                        #
                        # #  add import ast object to list to put in lambda_handler
                        #
                        # # for x in import_objects_list:
                        # #     logger.debug(astor.to_source(x))
                        # # logger.debug(import_objects_list)
                        # # sys.exit(getframeinfo(currentframe()))
                        # # add s3_client to non-function object
                        # non_func_ast_list.add(s3_client_object)
                        # logger.debug(non_func_ast_list)

                    else:
                        # get corresponding object for import
                        import_info: ImportInfoClass = import_info_dict_name_to_class.get(
                            each_import_name
                        )

                        import_ast_object = import_info.ast_object
                        import_info_dict[each_import_name] = import_ast_object

                        import_objects_list.append(import_ast_object)

                for x in non_func_ast_list:
                    logger.debug(astor.to_source(x))

                if "boto3" not in import_name_list:
                    boto3_info = whole_ast_info.boto3_and_json_imports["boto3"]
                    boto3_ast = boto3_info.ast_object
                    import_objects_list.append(boto3_ast)
                    non_func_ast_list.append(s3_client_object)

                new_import_objects_list = []
                for i in import_objects_list:
                    if i not in new_import_objects_list:
                        new_import_objects_list.append(i)

                logger.debug(new_import_objects_list)

                new_non_func_ast_list = []
                for i in non_func_ast_list:
                    if i not in new_non_func_ast_list:
                        new_non_func_ast_list.append(i)

                each_lambda_handler.import_info_dict = import_info_dict
                each_lambda_handler.lambda_module.body = (
                        new_import_objects_list
                        + new_non_func_ast_list
                        + each_lambda_handler.lambda_module.body
                )

                logger.info(astor.to_source(each_lambda_handler.lambda_module))

                logger.debug(each_lambda_handler.lambda_group_name)

                # Save to lambda_handler_module_dict
                each_lambda_handler.import_name_list = new_import_objects_list

                whole_ast_info.lambda_handler_module_dict[
                    each_lambda_handler.lambda_group_name
                ] = each_lambda_handler.lambda_module

                # sys.exit(getframeinfo(currentframe()))
                # logger.debug(pformat(lambda_handlers_info))

        return
    import_info_dict_name_to_class = whole_ast_info.import_information
    non_func_obj_info = whole_ast_info.non_function_object_info
    func_name_to_function_info_class_dict = whole_ast_info.function_information
    lambda_handlers_info = whole_ast_info.compiler_generated_lambda_handler_dict

    # Add import_ast_object and import name list from non-func object
    non_func_ast_list, non_func_import_name_list = [], []

    non_func_info: NonFunctionInfoClass
    for non_func_ast, non_func_info in non_func_obj_info.items():
        non_func_import_name_list.extend(non_func_info.import_name_list)
        non_func_ast_list.append(non_func_ast)

    # logging.debug(non_func_ast_list)
    # logging.debug(non_func_import_name_list)
    # sys.exit(getframeinfo(currentframe()))

    # Iterate through lambda_handlers_info
    each_lambda_handler: [CompilerGeneratedLambda, MergedCompilerGeneratedLambda]
    for _, each_lambda_handler in lambda_handlers_info.items():

        # Get original function information
        original_func_name = each_lambda_handler.original_func_name
        original_func_name_info: FunctionDefinition = (
            func_name_to_function_info_class_dict.get(original_func_name)
        )

        # Add non_func_import_name_list to func_import_set
        # TODO: Using set could change order of import modules
        import_name_list: set = original_func_name_info.import_name_list
        import_name_list.update(non_func_import_name_list)

        # Add import s3 and s3_client
        if "boto3" not in import_name_list:
            import_name_list.add("boto3")

        # Make a dictionary (import_info_dict) :
        # import name -> import object and save to ImportInfoClass
        import_info_dict = defaultdict()

        # import object list for putting in lambda_handler
        import_objects_list = []

        for each_import_name in list(import_name_list):

            # Add boto3 import and s3_client if it doesn't exist
            if each_import_name == "boto3":
                boto3_info = whole_ast_info.boto3_and_json_imports[0]
                boto3_ast = boto3_info.ast_object

                # mapping dictionary : import_name -> import object
                import_info_dict[each_import_name] = boto3_ast

                #  add import ast object to list to put in lambda_handler
                import_objects_list.append(boto3_ast)

                # add s3_client to non-function object
                s3_client_object = make_s3_client()
                non_func_ast_list.append(s3_client_object)

            else:
                # get corresponding object for import
                import_info: ImportInfoClass = import_info_dict_name_to_class.get(
                    each_import_name
                )
                import_ast_object = import_info.ast_object

                # mapping dictionary : import_name -> import object
                import_info_dict[each_import_name] = import_ast_object

                #  add import ast object to list to put in lambda_handler
                import_objects_list.append(import_ast_object)

        # save information to CompilerGeneratedLambda for each lambda_handler
        each_lambda_handler.import_info_dict = import_info_dict

        # Make a module comprising import, non_func_ast, and lambda_based_ast_object
        # generated_module = ast.Module(
        #     body=import_objects_list
        #     + non_func_ast_list
        #     + [each_lambda_handler.lambda_handler_func_object]
        # )

        each_lambda_handler.lambda_module.body = (
                import_objects_list
                + non_func_ast_list
                + each_lambda_handler.lambda_module.body
        )

        logger.info(astor.to_source(each_lambda_handler.lambda_module))

        # logging.debug(astor.to_source(generated_module))
        # sys.exit(getframeinfo(currentframe()))

        # Save to lambda_handler_module_dict
        whole_ast_info.lambda_handler_module_dict[
            each_lambda_handler.lambda_name
        ] = each_lambda_handler.lambda_module


def make_s3_client():
    # Add lambda client using boto3
    boto3_attribute_object = ast.Attribute(
        value=ast.Name(id="boto3", ctx=ast.Load()), attr="client", ctx=ast.Load(),
    )
    s3_client_name_object = ast.Name(id="s3_client", ctx=ast.Store())
    boto3_call_object = ast.Call(
        func=boto3_attribute_object,
        args=[ast.Str(s="s3")],
        keywords=[
            ast.keyword(arg="region_name", value=ast.Str(s="us-east-1")),
            ast.keyword(arg=None, value=ast.Name(id="CREDENTIALS", ctx=ast.Load())),
        ],
    )
    s3_client_object = ast.Assign(
        targets=[s3_client_name_object], value=boto3_call_object
    )
    s3_client_object = ast.fix_missing_locations(s3_client_object)
    return s3_client_object


def make_lambda_code_directory(whole_ast_info: WholeASTInfoClass) -> None:
    """
    each directory will have each lambda_handler
    """

    logger.info("Make directory for lambda functions")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Make only one directory")

        # Fetch lambda dir where each lambda handler is used
        lambda_code_path = compiler_module_config.lambda_code_dir_path

        # Make Folder for lambda codes
        if os.path.exists(lambda_code_path):
            logger.info(f"Empty {lambda_code_path}")
            os.system("rm -rf %s" % lambda_code_path)
            os.makedirs(lambda_code_path)
        else:
            os.makedirs(lambda_code_path)

        # Fetch module
        module_info = whole_ast_info.module_info_for_offloading_whole_app

        # Fetch lambda name
        lambda_name = module_info.lambda_name
        lambda_module_obj = module_info.lambda_module

        # logger.debug(astor.to_source(lambda_module_obj))

        # Combine lambda name with lambda code path and make subdirectory
        sub_dir = os.path.join(lambda_code_path, lambda_name)
        os.makedirs(sub_dir)

        # Make source code
        native_code = astor.to_source(lambda_module_obj)

        # Write code to sub_dir
        with open(os.path.join(sub_dir, lambda_name + ".py"), "w") as temp_file:
            temp_file.write(native_code)

        return

    else:
        lambda_code_path = compiler_module_config.lambda_code_dir_path

        # Make Folder for lambda codes
        if os.path.exists(lambda_code_path):
            logger.info(f"Empty {lambda_code_path}")
            os.system("rm -rf %s" % lambda_code_path)
            os.makedirs(lambda_code_path)
        else:
            os.makedirs(lambda_code_path)

        # Fetch module
        module_info = whole_ast_info.lambda_handler_module_dict
        lambda_info_dict = whole_ast_info.lambda_function_info

        for lambda_name, lambda_info in lambda_info_dict.items():

            if isinstance(lambda_info, MergedCompilerGeneratedLambda):
                # Fetch lambda name
                lambda_name = lambda_info.lambda_group_name
                lambda_module_obj = lambda_info.lambda_module

                # Combine lambda name with lambda code path and make subdirectory
                sub_dir = os.path.join(lambda_code_path, lambda_name)
                os.makedirs(sub_dir)

                # Make source code
                native_code = astor.to_source(lambda_module_obj)

                # Write code to sub_dir
                with open(os.path.join(sub_dir, lambda_name + ".py"), "w") as temp_file:
                    temp_file.write(native_code)

        # logger.debug(module_info)
        # logger.debug(lambda_info)

        # sys.exit(getframeinfo(currentframe()))

    # Make Folder for lambda codes
    # if os.path.exists(lambda_code_path):
    #     os.system("rm -rf %s" % lambda_code_path)
    #     os.makedirs(lambda_code_path)
    # else:
    #     os.makedirs(lambda_code_path)

    # Fetch module from making directory
    lambda_handler_module_dict: Dict[
        str, ast.Module
    ] = whole_ast_info.lambda_handler_module_dict

    if not lambda_handler_module_dict:
        if os.path.exists(lambda_code_path):
            os.system("rm -rf %s" % lambda_code_path)
        return

    # find if there output/lambda_codes. Remove if already exist or make
    # directory
    if os.path.exists(lambda_code_path):
        os.system("rm -rf %s" % lambda_code_path)
        os.makedirs(lambda_code_path)
    else:
        os.makedirs(lambda_code_path)

    lambda_handler_module: ast.Module
    for (
            lambda_handler_name,
            lambda_handler_module,
    ) in lambda_handler_module_dict.items():
        # Make sub_directory for each module e.g., lambda code/lambda_handler_1
        sub_dir = os.path.join(lambda_code_path, lambda_handler_name)
        os.makedirs(sub_dir)

        # Use astor.to_source() to make readable code
        native_code = astor.to_source(lambda_handler_module)

        # Write code to sub_dir
        with open(os.path.join(sub_dir, lambda_handler_name + ".py"), "w") as temp_file:
            temp_file.write(native_code)


def insert_imports_in_lambda_code_folder(whole_ast_info: WholeASTInfoClass) -> None:
    """
    Insert module(import) for each lambda handler in each directory
    """

    logger.info("Link library modules for lambda handlers")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Link library modules")

        # Fetch import modules in directory
        import_modules_dir, module_lists = bring_module_list_in_import_modules_folder()

        # Fetch module
        module_to_offload = whole_ast_info.module_info_for_offloading_whole_app

        # Combine lambda dir with lambda name
        lambda_dir = os.path.join(
            compiler_module_config.lambda_code_dir_path, module_to_offload.lambda_name
        )

        # Fetch all import modules used in this soure code
        import_list = module_to_offload.import_name_list

        # In case of library dependency e.g., mxnet, matplotlib
        consider_dependency_between_modules(import_list)

        # Group import name depending on python script or not
        import_group_by_python_script = group_import_by_from_script(whole_ast_info)

        module_list = list(import_group_by_python_script.values())[0]
        logger.info(f"Import modules : {module_list}")

        # Iterate each import name in source code
        iterate_and_put_import_modules(
            import_group_by_python_script, import_modules_dir, lambda_dir, module_lists
        )

        return

    else:
        # Fetch import modules in directory
        import_modules_dir, module_lists = bring_module_list_in_import_modules_folder()

        # Fetch module
        lambda_info_dict = whole_ast_info.lambda_function_info

        lambda_code_path = compiler_module_config.lambda_code_dir_path

        for lambda_name, lambda_info in lambda_info_dict.items():

            if isinstance(lambda_info, MergedCompilerGeneratedLambda):
                # Combine lambda dir with lambda name
                lambda_dir = os.path.join(
                    lambda_code_path, lambda_info.lambda_group_name
                )
                # Fetch all import modules used in this soure code
                import_list = lambda_info.import_name_list

                # In case of library dependency e.g., mxnet, matplotlib
                consider_dependency_between_modules(import_list)

                # Group import name depending on python script or not
                import_group_by_python_script = group_import_by_from_script(
                    whole_ast_info
                )

                module_list = list(import_group_by_python_script.values())[0]
                logger.info(f"Import modules : {module_list}")

                # Iterate each import name in source code
                iterate_and_put_import_modules(
                    import_group_by_python_script,
                    import_modules_dir,
                    lambda_dir,
                    module_lists,
                )
        return

    lambda_handler_module_dict: Dict[
        str, ast.Module
    ] = whole_ast_info.lambda_handler_module_dict

    if not lambda_handler_module_dict:
        return

    compiler_generated_lambda_handler_dict: Dict[
        str, CompilerGeneratedLambda
    ] = whole_ast_info.compiler_generated_lambda_handler_dict

    # get all import in modules directory
    module_lists = []
    for (_, dir_names, _) in os.walk(
            os.path.join(os.getcwd(), compiler_module_config.module_dir)
    ):
        module_lists.extend(dir_names)  # contains each module directory
        break

    #  iterate each lambda handler
    lambda_info: CompilerGeneratedLambda
    for (
            lambda_handler_name,
            lambda_info,
    ) in compiler_generated_lambda_handler_dict.items():

        # get import name list per lambda handler
        import_list: List[str] = list(lambda_info.import_info_dict.keys())

        for each_import_name in import_list:

            # fetch lambda handler directory
            lambda_dir = os.path.join(
                compiler_module_config.lambda_code_dir_path, lambda_handler_name
            )

            # if import is from python script
            if each_import_name in whole_ast_info.imports_from_python_script:
                python_script_dir = os.path.join(os.getcwd(), each_import_name + ".py")
                os.system("cp -r %s %s" % (python_script_dir, lambda_dir))

            # iterate each module  and put it inside lambda handler directory
            for each_module in module_lists:
                if each_module.lower().startswith(each_import_name.lower()):
                    module_dir = os.path.join(
                        compiler_module_config.module_dir, each_module
                    )
                    os.system("cp -r %s %s" % (module_dir, lambda_dir))


def iterate_and_put_import_modules(
        import_group_by_python_script, import_modules_dir, lambda_dir, module_lists
):
    for from_python_script, import_list in import_group_by_python_script.items():

        if from_python_script:  # If from python script
            for each_import_name in import_list:
                python_script_dir = os.path.join(os.getcwd(), each_import_name + ".py")
                os.system("cp -r %s %s" % (python_script_dir, lambda_dir))

        else:  # Default import modules
            for each_import_name in import_list:
                for each_module in module_lists:
                    if each_module.lower().startswith(each_import_name.lower()):
                        module_dir = os.path.join(import_modules_dir, each_module)
                        os.system("cp -r %s %s" % (module_dir, lambda_dir))


def group_import_by_from_script(whole_ast_info):
    import_info = list(whole_ast_info.import_information.values())
    lambda_dict_for_python_script = defaultdict(list)
    for x in import_info:
        lambda_dict_for_python_script[x.from_python_script].append(x.import_name)
    logger.debug(import_info)
    return lambda_dict_for_python_script


def consider_dependency_between_modules(import_list):
    # Matplotlib # TODO : Library Dependency Needs Thought
    if "matplotlib" in import_list:
        import_list.remove("matplotlib")
        import_list.remove("numpy")
    # MxNet
    if "mxnet" in import_list:
        import_list.append("requests")
        import_list.append("urllib3")
        import_list.append("chardet")


def bring_module_list_in_import_modules_folder():
    import_modules_dir = compiler_module_config.module_dir
    module_lists = []
    for (_, dir_names, _) in os.walk(os.path.join(os.getcwd(), import_modules_dir)):
        module_lists.extend(dir_names)
        break  # prevent from doing DFS
    return import_modules_dir, module_lists


def make_lambda_function(lambda_deploy_info, whole_info):
    """
    Use boto3 lambda_client to create or remove functions
    """

    lambda_client = boto3.client("lambda", **CREDENTIALS)
    lambda_name_to_make = lambda_deploy_info.lambda_name_to_make_on_aws

    # see if function already exists
    try:
        lambda_client.get_function(FunctionName=lambda_name_to_make)

    # if it doesn't exist, make new one
    except lambda_client.exceptions.ResourceNotFoundException:

        logger.info("Creating lambda function")

        create_lambda_function_by_cli(lambda_deploy_info, whole_info)

        logger.info(f"created {lambda_deploy_info.lambda_name_to_make_on_aws}")

    # if it exists, remove function and make new one
    else:

        logger.info("function already exists so removing current function")

        lambda_client.delete_function(FunctionName=lambda_name_to_make)

        logger.info(f"deleted lambda function named - {lambda_name_to_make}")

        create_lambda_function_by_cli(lambda_deploy_info, whole_info)

        logger.info(f"created lambda function named - {lambda_name_to_make}")


# noinspection PyUnusedLocal
def create_lambda_function_by_cli(lambda_deploy_info, whole_info):
    lambda_client = boto3.client("lambda", region_name="us-east-1", **CREDENTIALS)

    if whole_info.offloading_whole_application:

        object_in_s3 = whole_info.deployment_name_for_offloading_whole_app
        function_name = lambda_deploy_info.lambda_name_to_make_on_aws
        handler_name = lambda_deploy_info.handler_name
        logger.info(f"using zip named - {object_in_s3}")
        lambda_client.create_function(
            # Code={"ZipFile": open(lambda_zip_name, "rb").read()},
            Code={
                "S3Bucket": compiler_module_config.bucket_for_lambda_handler_zip,
                "S3Key": object_in_s3,
                # how can i create or fetch this S3Key
            },
            FunctionName=function_name,
            Handler=f"{handler_name}_{function_name}.{handler_name}_{function_name}",
            MemorySize=lambda_deploy_info.memory_size,
            Publish=True,
            Role=lambda_deploy_info.aws_role,
            Runtime=lambda_deploy_info.runtime,
            Timeout=lambda_deploy_info.time_out,
        )

    else:
        zip_object = lambda_deploy_info.zip_file_name_in_s3
        function_name = lambda_deploy_info.lambda_name_to_make_on_aws
        handler_name = lambda_deploy_info.handler_name
        lambda_client.create_function(
            Code={
                "S3Bucket": compiler_module_config.bucket_for_lambda_handler_zip,
                "S3Key": zip_object,
                # how can i create or fetch this S3Key
            },
            FunctionName=function_name,
            Handler=f"{handler_name}.{handler_name}",
            MemorySize=lambda_deploy_info.memory_size,
            Publish=True,
            Role=lambda_deploy_info.aws_role,
            Runtime=lambda_deploy_info.runtime,
            Timeout=lambda_deploy_info.time_out,
        )


def map_func_to_func_arn(whole_ast_info: WholeASTInfoClass) -> None:
    """
    make assign object that contains mapping function name to function name arn
    e.g., {"resize" :"image_processing_resize"}
    """
    logger.info("make assign object that maps function name to function name arn")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Skip since no func call orchestrator")
        return
    else:
        lambda_info_dict = whole_ast_info.lambda_function_info
        lambda_deployment_zip_info = whole_ast_info.lambda_deployment_zip_info

        if not lambda_deployment_zip_info:
            return

        logger.debug(lambda_deployment_zip_info)

        annotated_code_module = whole_ast_info.copied_module_for_analysis
        non_func_info = whole_ast_info.non_function_object_info

        original_func_list = []
        lambda_func_name_in_aws = []

        # save function name and function arn information
        deployment_info: LambdaDeployInfo
        for _, deployment_info in lambda_deployment_zip_info.items():
            original_func_list.append(ast.Str(s=deployment_info.original_func_name))
            logger.debug(deployment_info.original_func_name)
            lambda_func_name_in_aws.append(
                ast.Str(s=deployment_info.lambda_name_to_make_on_aws)
            )
            logger.debug(deployment_info.lambda_name_to_make_on_aws)
        # logger.debug(original_func_list)
        # logger.debug(lambda_func_name_in_aws)
        # sys.exit(getframeinfo(currentframe()))
        # find last non_func_info and add above assign object to the last one
        last_non_func_obj_info: NonFunctionInfoClass = list(
            whole_ast_info.non_function_object_info.values()
        )[-1]
        last_non_func_obj = last_non_func_obj_info.ast_object
        index_for_last_non_func_object = (
                annotated_code_module.body.index(last_non_func_obj) + 1
        )

        # make assign object that contains mapping function
        map_func_to_func_arn_object = ast.Assign(
            targets=[ast.Name(id="map_func_to_func_arn_dict", ctx=ast.Store())],
            value=ast.Dict(keys=original_func_list, values=lambda_func_name_in_aws),
            lineno=last_non_func_obj.lineno + 1,
            col_offset=0,
        )
        logger.debug(astor.to_source(map_func_to_func_arn_object))

        # annotated_code_module.body = (
        #         annotated_code_module.body[:index_for_last_non_func_object]
        #         + [map_func_to_func_arn_object]
        #         + (annotated_code_module.body[index_for_last_non_func_object:])
        # )

        whole_ast_info.map_func_to_func_arn_object = map_func_to_func_arn_object
        logger.debug(astor.to_source(annotated_code_module))
        # sys.exit(getframeinfo(currentframe()))
        return

    lambda_deployment_info = whole_ast_info.lambda_function_info
    annotated_code_module = whole_ast_info.copied_module_for_analysis
    non_func_info = whole_ast_info.non_function_object_info

    original_func_list = []
    lambda_func_name_in_aws = []

    # save function name and function arn information
    deployment_info: LambdaDeployInfo
    for _, deployment_info in lambda_deployment_info.items():
        original_func_list.append(ast.Str(s=deployment_info.original_func_name))
        lambda_func_name_in_aws.append(
            ast.Str(s=deployment_info.lambda_name_to_make_on_aws)
        )

    # find last non_func_info and add above assign object to the last one
    last_non_func_obj_info: NonFunctionInfoClass = list(
        whole_ast_info.non_function_object_info.values()
    )[-1]
    last_non_func_obj = last_non_func_obj_info.ast_object
    index_for_last_non_func_object = (
            annotated_code_module.body.index(last_non_func_obj) + 1
    )

    # make assign object that contains mapping function
    map_func_to_func_arn_object = ast.Assign(
        targets=[ast.Name(id="map_func_to_func_arn_dict", ctx=ast.Store())],
        value=ast.Dict(keys=original_func_list, values=lambda_func_name_in_aws),
        lineno=last_non_func_obj.lineno + 1,
        col_offset=0,
    )

    # add this object right after last non_func_obj
    annotated_code_module.body = (
            annotated_code_module.body[:index_for_last_non_func_object]
            + [map_func_to_func_arn_object]
            + (annotated_code_module.body[index_for_last_non_func_object:])
    )

    # add this assign object to non_func_info
    non_func_info[map_func_to_func_arn_object] = NonFunctionInfoClass(
        last_non_func_obj_info.line_number + 1,
        ast_object=map_func_to_func_arn_object,
        non_func_object_type="Assign",
    )

    # logger.info(astor.to_source(annotated_code_module))


def write_hybrid_code(whole_ast_info: WholeASTInfoClass):
    """
    Make a code that is hybrid-case
    1. Make hybrid code using copy
    2. Put Function of Invoke Call
    3. Change Function Call to Function Call of Invoke Call
    4. Add boto3, json import and (lambda and s3) client
    """

    logger.info("Making VM Hybrid")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Skip Making VM Hybrid")
        return

    annotated_code_module: ast.Module = whole_ast_info.copied_module_for_analysis
    non_func_info = whole_ast_info.non_function_object_info
    invoke_func_object = whole_ast_info.lambda_invoke_function
    lambda_based_func_call_info_list = whole_ast_info.func_call_using_lambda
    combined_func_call_using_lambda = whole_ast_info.combined_func_call_using_lambda
    # logger.info(invoke_func_object)
    # sys.exit(getframeinfo(currentframe()))

    # Make copy of annotated code since copied_module_for_analysis will be  modified
    annotated_code_module_for_user = copy.deepcopy(annotated_code_module)
    whole_ast_info.annotated_code_module_for_user = annotated_code_module_for_user

    # Fetch map_func_to_func_arn_object
    map_func_to_func_arn_object = whole_ast_info.map_func_to_func_arn_object
    # if not map_func_to_func_arn_object:
    # map_func_to_func_arn_object = []

    # Find the index of last non-fun and put invoke function after that index
    last_non_func_object_info: NonFunctionInfoClass = list(non_func_info.values())[-1]
    last_non_func_obj = last_non_func_object_info.ast_object
    last_non_func_obj_index = annotated_code_module.body.index(last_non_func_obj) + 1
    if map_func_to_func_arn_object:
        annotated_code_module.body = (
                annotated_code_module.body[:last_non_func_obj_index]
                + [map_func_to_func_arn_object]
                + [invoke_func_object]
                + annotated_code_module.body[last_non_func_obj_index:]
        )
        # last_non_func_obj_index += 2
    else:
        annotated_code_module.body = (
                annotated_code_module.body[:last_non_func_obj_index]
                + [invoke_func_object]
                + annotated_code_module.body[last_non_func_obj_index:]
        )
        # last_non_func_obj_index += 1

    # increment index since we added one
    # logger.debug(astor.to_source(annotated_code_module))
    # sys.exit(getframeinfo(currentframe()))
    # Change function call to function call of invoke call
    each_func_call: LambdaBasedFunctionCallInfoClass

    # logger.info(lambda_based_func_call_info_list)
    # sys.exit(getframeinfo(currentframe()))
    # Fetch function call that uses lambda-based function call
    for each_func_call in lambda_based_func_call_info_list:
        logger.debug(each_func_call)
        # Bring original and lambda_based func call  -> replace them
        origin_func_call: FunctionCallInfo = each_func_call.original_func_call_info
        copied_func_call = each_func_call.copied_func_call_info
        origin_func_call_object = origin_func_call.ast_object
        copied_func_call_object = copied_func_call.ast_object
        # sys.exit(getframeinfo(currentframe()))
        # Use transformer to replace assign or expr object with newly made
        # object
        change_func_call = ChangeFunctionCallTransformer(
            origin_func_call_object, copied_func_call_object
        )
        annotated_code_module = change_func_call.visit(annotated_code_module)
        annotated_code_module = ast.fix_missing_locations(annotated_code_module)

    # logger.debug(pformat(combined_func_call_using_lambda))
    for _, function_call_list in combined_func_call_using_lambda.items():

        first_func_call = function_call_list[0]
        origin_func_call: FunctionCallInfo = first_func_call.original_func_call_info
        copied_func_call = first_func_call.copied_func_call_info
        origin_func_call_object = origin_func_call.ast_object
        copied_func_call_object = copied_func_call.ast_object

        change_func_call = ChangeFunctionCallTransformer(
            origin_func_call_object, copied_func_call_object
        )
        annotated_code_module = change_func_call.visit(annotated_code_module)
        annotated_code_module = ast.fix_missing_locations(annotated_code_module)

        remaining_func_call = function_call_list[1:]
        for each_func_call in remaining_func_call:
            origin_func_call: FunctionCallInfo = each_func_call.original_func_call_info
            # copied_func_call = last_func_call.copied_func_call_info
            origin_func_call_object = origin_func_call.ast_object
            # copied_func_call_object = copied_func_call.ast_object
            logger.debug(copied_func_call_object)

            logger.debug(astor.to_source(origin_func_call_object))

            change_func_call = RemoveNodeTransformer(origin_func_call_object)
            annotated_code_module = change_func_call.visit(annotated_code_module)
            annotated_code_module = ast.fix_missing_locations(annotated_code_module)

        import_info_dict = whole_ast_info.import_information
        import_name_list_in_hybrid = list(import_info_dict.keys())
        last_import_info_in_hybrid = list(import_info_dict.values())[-1].ast_object

        logger.debug(astor.to_source(last_import_info_in_hybrid))

        import_name_to_add = [
            x for x in ["boto3", "json"] if x not in import_name_list_in_hybrid
        ]
        for each_import in import_name_to_add:
            module_to_add = ast.fix_missing_locations(
                ast.Import(names=[ast.alias(name=each_import, asname=None)])
            )
            last_import_index = (
                    annotated_code_module.body.index(last_import_info_in_hybrid) + 1
            )
            annotated_code_module.body = (
                    annotated_code_module.body[:last_import_index]
                    + [module_to_add]
                    + annotated_code_module.body[last_import_index:]
            )
            # last_non_func_obj_index += 1
            annotated_code_module = ast.fix_missing_locations(annotated_code_module)

        lambda_client_object = make_lambda_client()
        s3_client_object = make_s3_client()

        last_non_func_obj_index = (
                annotated_code_module.body.index(map_func_to_func_arn_object) + 1
        )
        # Append lambda client to last non function object
        annotated_code_module.body = (
                annotated_code_module.body[:last_non_func_obj_index]
                + [lambda_client_object]
                + [s3_client_object]
                + annotated_code_module.body[last_non_func_obj_index:]
        )

        # logger.debug(astor.to_source(annotated_code_module))
        # sys.exit(getframeinfo(currentframe()))
        # logger.debug(astor.to_source(annotated_code_module))

    # logger.info(astor.to_source(annotated_code_module))

    # Add lambda or s3 client with import if doesn't exist
    if lambda_based_func_call_info_list:

        # Fetch import list information, import_name_list, last_import_object
        import_info_dict = whole_ast_info.import_information
        import_name_list_in_hybrid = list(import_info_dict.keys())
        last_import_info_in_hybrid = list(import_info_dict.values())[-1].ast_object

        # json or boto3 when hybrid code doesn't have one
        import_name_to_add = [
            x for x in ["boto3", "json"] if x not in import_name_list_in_hybrid
        ]

        # Add import boto3 or json
        for each_import in import_name_to_add:
            module_to_add = ast.fix_missing_locations(
                ast.Import(names=[ast.alias(name=each_import, asname=None)])
            )
            last_import_index = (
                    annotated_code_module.body.index(last_import_info_in_hybrid) + 1
            )
            annotated_code_module.body = (
                    annotated_code_module.body[:last_import_index]
                    + [module_to_add]
                    + annotated_code_module.body[last_import_index:]
            )
            annotated_code_module = ast.fix_missing_locations(annotated_code_module)

        # Add lambda and s3 client using boto3
        # TODO: What if they already exist?
        lambda_client_object = make_lambda_client()
        s3_client_object = make_s3_client()

        # Append lambda client to last non function object
        annotated_code_module.body = (
                annotated_code_module.body[:last_non_func_obj_index]
                + [lambda_client_object]
                + [s3_client_object]
                + annotated_code_module.body[last_non_func_obj_index:]
        )

        # Add lambda client object to non_func_info class
        non_func_info[lambda_client_object] = NonFunctionInfoClass(
            last_non_func_obj.lineno + 1,
            ast_object=lambda_client_object,
            non_func_object_type="Assign",
            description="lambda_client object",
        )

        non_func_info[s3_client_object] = NonFunctionInfoClass(
            last_non_func_obj.lineno + 1,
            ast_object=s3_client_object,
            non_func_object_type="Assign",
            description="s3_client_object",
        )
    logger.info(astor.to_source(annotated_code_module_for_user))


def make_lambda_client():
    boto3_attribute_object = ast.Attribute(
        value=ast.Name(id="boto3", ctx=ast.Load()), attr="client", ctx=ast.Load()
    )
    lambda_client_name_object = ast.Name(id="lambda_client", ctx=ast.Store())
    boto3_call_object = ast.Call(
        func=boto3_attribute_object,
        args=[ast.Str(s="lambda")],
        keywords=[
            ast.keyword(arg="region_name", value=ast.Str(s="us-east-1")),
            ast.keyword(arg=None, value=ast.Name(id="CREDENTIALS", ctx=ast.Load())),
        ],
    )
    lambda_client_object = ast.Assign(
        targets=[lambda_client_name_object], value=boto3_call_object
    )
    lambda_client_object = ast.fix_missing_locations(lambda_client_object)
    return lambda_client_object


class ChangeFunctionCallTransformer(ast.NodeTransformer):
    def __init__(self, original_ast, copied_ast):
        self.original_ast = original_ast
        self.copied_ast = copied_ast

    def visit_Assign(self, node):
        if node == self.original_ast:
            node = self.copied_ast

        self.generic_visit(node)
        return node

    def visit_Expr(self, node):
        if node == self.original_ast:
            node = self.copied_ast

        self.generic_visit(node)
        return node


class RemoveNodeTransformer(ast.NodeTransformer):
    def __init__(self, original_ast):
        self.original_ast = original_ast
        # self.copied_ast = copied_ast

    def visit_Assign(self, node):
        if node == self.original_ast:
            return None
        return node

        #     node = self.copied_ast

        # return node

    def visit_Expr(self, node):
        if node == self.original_ast:
            self.generic_visit(node)
            return None
            # node = self.copied_ast
        return node
        # self.generic_visit(node)
        # return node


def save_hybrid_code_in_output_directory(whole_ast_info: WholeASTInfoClass) -> None:
    """
    Write copied_module_for_analysis which is hybrid code to hybrid_code directory
    """

    logger.info("Save hybrid code to hybrid_code directory")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Skipping since offloading whole app")
        return

    hybrid_code_to_write = whole_ast_info.copied_module_for_analysis
    hybrid_code_dir = compiler_module_config.hybrid_code_dir
    hybrid_code_file_name = compiler_module_config.hybrid_code_file_name

    # remove directory if already exists
    if os.path.exists(hybrid_code_dir):
        os.system("rm -rf %s" % hybrid_code_dir)
        os.makedirs(hybrid_code_dir)
    else:
        os.makedirs(hybrid_code_dir)

    # write code to directory
    hybrid_code = astor.to_source(hybrid_code_to_write)
    with open(
            os.path.join(hybrid_code_dir, hybrid_code_file_name + ".py"), "w"
    ) as temp_file:
        temp_file.write(hybrid_code)


def empty_output():
    output_dir = compiler_module_config.output_path_dir
    if os.path.exists("output"):
        os.system("rm -rf %s" % output_dir)
        os.makedirs(output_dir)
    else:
        os.makedirs(output_dir)


def make_zip_file_for_lambda_handler(whole_ast_info: WholeASTInfoClass) -> None:
    """
    Add directory of "deployment_zip_dir"
    """
    logger.info("Zip library modules and code for deployment")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Making only one zip")

        # delete if exists and make directory
        deployment_zip_dir = compiler_module_config.deployment_zip_dir
        if os.path.exists(deployment_zip_dir):
            os.system("rm -rf %s" % deployment_zip_dir)
            os.makedirs(deployment_zip_dir)
        else:
            os.makedirs(deployment_zip_dir)

        # Fetch module and lambda name
        module_info = whole_ast_info.module_info_for_offloading_whole_app
        lambda_dir = compiler_module_config.lambda_code_dir_path
        lambda_name = module_info.lambda_name

        # Zip code with modules
        shutil.make_archive(
            "lambda_handler", "zip", os.path.join(lambda_dir, lambda_name)
        )
        # Move zip file to deployment_zip_dir
        shutil.move(
            "lambda_handler" + ".zip", os.path.join(os.getcwd(), deployment_zip_dir)
        )
        logger.info("Zipped Module")
        return
    else:
        lambda_handler_module_dict: Dict[
            str, ast.Module
        ] = whole_ast_info.lambda_handler_module_dict

        # delete if exists and make directory
        deployment_zip_dir = compiler_module_config.deployment_zip_dir
        if os.path.exists(deployment_zip_dir):
            os.system("rm -rf %s" % deployment_zip_dir)
            os.makedirs(deployment_zip_dir)
        else:
            os.makedirs(deployment_zip_dir)

        lambda_code_dir_path = compiler_module_config.lambda_code_dir_path

        logger.debug(lambda_code_dir_path)

        # find lambda handler list in lambda_code_dir_path
        lambda_dir_list = [
            dI
            for dI in os.listdir(lambda_code_dir_path)
            if os.path.isdir(os.path.join(lambda_code_dir_path, dI))
        ]
        logger.debug(os.getcwd())
        logger.debug(lambda_dir_list)
        # zip it and move that to deployment_zip_dir
        for each_lambda_dir in lambda_dir_list:
            shutil.make_archive(
                str(each_lambda_dir),
                "zip",
                os.path.join(lambda_code_dir_path, each_lambda_dir),
            )
            shutil.move(
                str(each_lambda_dir) + ".zip",
                os.path.join(os.getcwd(), deployment_zip_dir),
            )

        return
    lambda_handler_module_dict: Dict[
        str, ast.Module
    ] = whole_ast_info.lambda_handler_module_dict

    # Exception handling
    if not lambda_handler_module_dict:
        if os.path.exists(compiler_module_config.deployment_zip_dir):
            os.system("rm -rf %s" % compiler_module_config.deployment_zip_dir)
        return

    # delete if exists and make directory
    deployment_zip_dir = compiler_module_config.deployment_zip_dir
    if os.path.exists(deployment_zip_dir):
        os.system("rm -rf %s" % deployment_zip_dir)
        os.makedirs(deployment_zip_dir)
    else:
        os.makedirs(deployment_zip_dir)

    lambda_code_dir_path = compiler_module_config.lambda_code_dir_path

    # find lambda handler list in lambda_code_dir_path
    lambda_dir_list = [
        dI
        for dI in os.listdir(lambda_code_dir_path)
        if os.path.isdir(os.path.join(lambda_code_dir_path, dI))
    ]

    # zip it and move that to deployment_zip_dir
    for each_lambda_dir in lambda_dir_list:
        shutil.make_archive(
            str(each_lambda_dir),
            "zip",
            os.path.join(lambda_code_dir_path, each_lambda_dir),
        )
        shutil.move(
            str(each_lambda_dir) + ".zip", os.path.join(os.getcwd(), deployment_zip_dir)
        )


def make_lambda_function_using_aws_cli(whole_ast_info: WholeASTInfoClass):
    """
    use boto3 to make lambda for each compiler generated lambda handler
    """
    logger.info("Create lambda function using aws cli")

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Create only one lambda")

        # move to deployments zip folder for deploying zip file
        os.chdir(compiler_module_config.deployment_zip_dir)

        # Source code name
        original_file_name = whole_ast_info.file_name
        original_file_name_without_extension = original_file_name.split(".")[0]

        logger.debug(original_file_name)

        # Unless specified, use lambda function name from original_file_name
        try:
            lambda_name = (
                whole_ast_info.lambda_config_for_whole_application.function_name
            )
        except AttributeError:
            lambda_name = original_file_name_without_extension
            logger.info(f"Using file name to {lambda_name}")

        # logger.info(lambda_name)
        # sys.exit(getframeinfo(currentframe()))
        lambda_handler_name = "lambda_handler"

        lambda_zip_name = lambda_handler_name + ".zip"
        lambda_arn = "arn:aws:lambda:us-east-1:206135129663:function:" + lambda_name
        # handler_name_in_lambda_console = ".".join(
        #     [lambda_handler_name, lambda_handler_name]
        # )

        lambda_deploy_info = LambdaDeployInfo(
            # lambda_name="lambda_handler",
            original_func_name=original_file_name,
            lambda_zip_name=lambda_zip_name,
            lambda_name_to_make_on_aws=lambda_name,
            lambda_arn=lambda_arn,
            handler_name=lambda_handler_name,
            # handler_name_in_lambda_console=handler_name_in_lambda_console,
            zip_file_name_in_s3=whole_ast_info.deployment_name_for_offloading_whole_app,
        )

        whole_ast_info.lambda_deployment_zip_info[
            lambda_handler_name
        ] = lambda_deploy_info

        # TODO : remember to uncomment
        make_lambda_function(lambda_deploy_info, whole_ast_info)

        os.chdir("../../..")

        return

    else:

        lambda_info_dict = whole_ast_info.lambda_function_info

        # Exception handling
        if not lambda_info_dict:
            if os.path.exists(compiler_module_config.deployment_zip_dir):
                os.system("rm -rf %s" % compiler_module_config.deployment_zip_dir)
            return

        for lambda_name, lambda_info in lambda_info_dict.items():

            # move to deployments zip folder for deploying zip file
            os.chdir(compiler_module_config.deployment_zip_dir)

            if isinstance(lambda_info, MergedCompilerGeneratedLambda):
                logger.debug(whole_ast_info.lambda_deployment_zip_info)

                zip_file_name_in_s3_bucket = whole_ast_info.lambda_deployment_zip_info[
                    lambda_info.lambda_group_name
                ]

                original_file_name = lambda_info.lambda_name_list
                logger.debug(original_file_name)
                lambda_name_for_creation = "_and_".join(original_file_name)
                lambda_name_to_make = (
                        "coco_image_processing_" + lambda_name_for_creation
                )
                lambda_zip_name = lambda_info.lambda_group_name + ".zip"
                lambda_arn = (
                        "arn:aws:lambda:us-east-1:206135129663:function:"
                        + lambda_name_to_make
                )
                logger.debug(lambda_name_to_make)

                lambda_deploy_info = LambdaDeployInfo(
                    # lambda_name="lambda_handler",
                    original_func_name=lambda_name_for_creation,
                    lambda_zip_name=lambda_zip_name,
                    lambda_name_to_make_on_aws=lambda_name_to_make,
                    lambda_arn=lambda_arn,
                    handler_name=lambda_info.lambda_group_name,
                    # handler_name_in_lambda_console=handler_name_in_lambda_console,
                    zip_file_name_in_s3=zip_file_name_in_s3_bucket,
                )
                whole_ast_info.lambda_deployment_zip_info[
                    lambda_info.lambda_group_name
                ] = lambda_deploy_info

                # make_lambda_function(lambda_deploy_info, whole_ast_info)

                os.chdir("../../..")
                # logger.debug(zip_file_name_in_s3_bucket)
                # Fetch module and lambda name
                # lambda_dir = compiler_module_config.lambda_code_dir_path
                # lambda_name = lambda_info.lambda_group_name
                # logger.debug(lambda_name)
                # sys.exit(getframeinfo(currentframe()))
                return

        lambda_handler_module_dict: Dict[
            str, ast.Module
        ] = whole_ast_info.lambda_handler_module_dict

        # If there is module to make lambda based
        if lambda_handler_module_dict:

            # move to deployments zip folder for deploying zip file
            os.chdir(compiler_module_config.deployment_zip_dir)

            # lambda_handler_deploy_dict = defaultdict()
            lambda_handler_info: CompilerGeneratedLambda
            for (
                    lambda_handler_func_name,
                    lambda_handler_info,
            ) in whole_ast_info.compiler_generated_lambda_handler_dict.items():
                # generate information
                # logger.info(lambda_handler_func_name)
                zip_file_name_in_s3_bucket = whole_ast_info.lambda_deployment_zip_info[
                    lambda_handler_func_name
                ]
                # logger.info(zip_file_name_in_s3_bucket)
                # sys.exit(getframeinfo(currentframe()))
                original_file_name = lambda_handler_info.original_func_name
                lambda_name_to_make = "coco_image_processing_" + original_file_name
                lambda_zip_name = lambda_handler_func_name + ".zip"
                handler_name_in_lambda_console = ".".join(
                    [lambda_handler_func_name, lambda_handler_func_name]
                )
                lambda_arn = (
                        "arn:aws:lambda:us-east-1:206135129663:function:"
                        + lambda_name_to_make
                )

                # save it to LambdaDeploymentInfo
                lambda_deploy_info = LambdaDeployInfo(
                    # lambda_name=lambda_handler_func_name,
                    original_func_name=original_file_name,
                    lambda_zip_name=lambda_zip_name,
                    lambda_name_to_make_on_aws=lambda_name_to_make,
                    lambda_arn=lambda_arn,
                    handler_name_in_lambda_console=handler_name_in_lambda_console,
                    zip_file_name_in_s3=zip_file_name_in_s3_bucket,
                )

                # save it to whole_ast_info for keeping track
                whole_ast_info.lambda_deployment_zip_info[
                    lambda_handler_func_name
                ] = lambda_deploy_info

                # make_lambda_function(
                #     lambda_deploy_info,
                #     lambda_handler_func_name,
                #     lambda_name_to_make,
                #     lambda_zip_name,
                #     whole_ast_info,
                # )

            # move back to compiler_main directory
            os.chdir("../../..")


def upload_upload_hybrid_code_to_s3hybrid_code_to_s3(whole_ast_info: WholeASTInfoClass):
    logger.info("Uploading hybrid code to s3")
    logger.info("Skipping since we aren't in dynamic phase")
    return

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Skipping since not dynamic phase")
        return

    hybrid_code_dir = compiler_module_config.hybrid_code_dir
    hybrid_code_file_name = compiler_module_config.hybrid_code_file_name
    bucket_name = compiler_module_config.bucket_for_hybrid_code

    # TODO : comment code in code
    s3_client.upload_file(
        os.path.join(hybrid_code_dir, hybrid_code_file_name + ".py"),
        bucket_name,
        f"{uuid.uuid4()}-{hybrid_code_file_name}.py",
    )

    logger.info("Uploading hybrid code to s3")


def upload_hybrid_code_to_s3(whole_ast_info: WholeASTInfoClass):
    logger.info("Uploading hybrid code to s3")
    logger.info("Skipping since we aren't in dynamic phase")
    return

    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Skipping since not dynamic phase")
        return

    hybrid_code_dir = compiler_module_config.hybrid_code_dir
    hybrid_code_file_name = compiler_module_config.hybrid_code_file_name
    bucket_name = compiler_module_config.bucket_for_hybrid_code

    # TODO : comment code in code
    # s3_client.upload_file(
    #     os.path.join(hybrid_code_dir, hybrid_code_file_name + ".py"),
    #     bucket_name,
    #     f"{uuid.uuid4()}-{hybrid_code_file_name}.py",
    # )

    logger.info("Uploading hybrid code to s3")


def upload_lambda_deployment_to_s3(whole_ast_info: WholeASTInfoClass):
    logger.info("Uploading deployment to s3")
    if whole_ast_info.offloading_whole_application:
        logger.info("[Offloading whole app] : Uploading one zip file")

    # Fetch deployment directory
    deployment_dir = compiler_module_config.deployment_zip_dir
    bucket_name = compiler_module_config.bucket_for_lambda_handler_zip

    # Remove all objects in bucket beforehand
    # TODO : comment this for improving performance
    # bucket = s3.Bucket(bucket_name)
    # bucket.objects.all().delete()
    # logger.info(f"Deleting all objects in {bucket_name} beforehand")

    # find all zip files in directory
    deploy_dir_list = []
    for dI in os.listdir(deployment_dir):
        deploy_dir_list.append(dI)

    # logger.debug(deploy_dir_list)
    # sys.exit(getframeinfo(currentframe()))

    for each_deploy_zip in deploy_dir_list:
        upload_deploy_zip_to_s3(
            bucket_name, deployment_dir, each_deploy_zip, whole_ast_info
        )


def upload_deploy_zip_to_s3(bucket_name, deploy_directory, deploy_zip, whole_ast_info):
    # Randomize file name for consistency
    random_named_lambda_deploy_zip = f"{uuid.uuid4()}-{deploy_zip}"

    # Upload
    # TODO: Uncomment
    # s3_client.upload_file(
    #     os.path.join(deploy_directory, deploy_zip),
    #     bucket_name,
    #     random_named_lambda_deploy_zip,
    # )

    logger.info(f"Uploaded {random_named_lambda_deploy_zip}")

    # Save zip file name
    if whole_ast_info.offloading_whole_application:
        whole_ast_info.deployment_name_for_offloading_whole_app = (
            random_named_lambda_deploy_zip
        )

    else:

        whole_ast_info.lambda_deployment_zip_info[
            deploy_zip.split(".")[0]
        ] = random_named_lambda_deploy_zip


def group_by_lambda_group_name(whole_info: WholeASTInfoClass):
    logger.info("Grouping by lambda group name")

    if whole_info.offloading_whole_application:
        logger.info("\tSkip Since offloading whole app")
    else:
        # Fetch function information
        fun_info = list(whole_info.function_information.values())

        # Group func info based on lambda group name
        group_lambda_dict = defaultdict(list)

        for x in fun_info:
            # Functions isn't main and has FaaS -> Group by Lambda Group
            if x.func_name is not "main" and x.initial_pragma == "FaaS":
                group_lambda_dict[("".join(x.lambda_group_name))].append(x.func_name)

        # Save it to whole_info
        whole_info.sort_by_lambda_group = dict(group_lambda_dict)

        if group_lambda_dict:
            logger.info(f"\tGroup_by_lambda : {dict(group_lambda_dict)}")

        else:
            logger.info("\tThere is no lambda group")


def process_before_deploy(f_name, bench_dir):
    logger.info("Compiler")
    logger.info("User annotation before deployment")
    logger.info(f"Input file is {f_name}")

    with open(os.path.join(bench_dir, f_name), "r") as original_code_script:
        whole_information = make_dataclass_that_contains_whole_info(
            original_code_script, f_name
        )
        # Find pragma in code
        find_user_annotation_in_code(whole_information)

        # From user annotation, make information for functions
        # parse_info_for_functions(whole_information)

        # Put User-Annotation pragma in functions
        # put_pragma_in_functions(whole_information, copy_module)

        # Sort and group by lambda group for checking combine pragma
        group_by_lambda_group_name(whole_information)

    logger.info("End of Compiler before deployment")
    return whole_information


def process_while_deployment(whole_info):
    logger.info("Start offloading to Lambda")

    # import and finding function (Decomposition)
    copied_module_for_analysis = whole_info.copied_module_for_analysis
    code_analyzer = ImportAndFunctionAnalyzer(whole_info, compiler_module_config)
    code_analyzer.visit(copied_module_for_analysis)
    code_analyzer.start_analyzing()

    make_lambda_based_function(whole_info)  # change function definition
    function_call_orchestrator(whole_info)  # function call and orchestrator
    add_using_s3_in_lambda_handler(whole_info)  # add some modules in lambda handler
    make_module_for_lambda_handler(whole_info)  # add s3 import and s3 client
    make_lambda_code_directory(whole_info)  # make directory for each lambda handler
    insert_imports_in_lambda_code_folder(whole_info)  # Put library modules
    make_zip_file_for_lambda_handler(whole_info)
    upload_lambda_deployment_to_s3(whole_info)
    make_lambda_function_using_aws_cli(whole_info)  # TODO : comment code in code
    map_func_to_func_arn(whole_info)
    write_hybrid_code(whole_info)
    save_hybrid_code_in_output_directory(whole_info)
    upload_hybrid_code_to_s3(whole_info)  # TODO : comment code in code

    logger.info("Finish offloading to Lambda")
    pass


def main():
    benchmark_dir = "../BenchmarkApplication"
    file_name: str = "image_processing_test.py"
    logger.info("File is {}".format(file_name))
    with open(os.path.join(benchmark_dir, file_name), "r") as original_code:
        # Make whole info dataclass
        whole_info = make_dataclass_that_contains_whole_info(original_code, file_name)
        copied_module: ast.Module = whole_info.copied_module_for_analysis

        # Provide users with functions and let users choose rules for scaling policy
        find_user_annotation_in_code(whole_info)

        # Sort and group by lambda group for checking combine pragma
        group_by_lambda_group_name(whole_info)

        # From user annotation, make information for functions
        # parse_info_for_functions(whole_info)

        # Put User-Annotation pragma in functions
        # put_pragma_in_functions(whole_info, copied_module)

        # import and finding function (Decomposition)
        code_analyzer = ImportAndFunctionAnalyzer(whole_info, compiler_module_config)
        code_analyzer.visit(copied_module)
        code_analyzer.start_analyzing()

        # change function definition
        make_lambda_based_function(whole_info)

        # logger.debug(
        #     astor.to_source(whole_info.lambda_function_info["L1"].lambda_module)
        # )

        # function call orchestrator and change function call
        function_call_orchestrator(whole_info)

        # add some modules in lambda handler
        add_using_s3_in_lambda_handler(whole_info)

        # show_result(whole_info)
        # sys.exit(getframeinfo(currentframe()))

        # show_result(whole_info)
        # sys.exit(getframeinfo(currentframe()))

        # Add using
        make_module_for_lambda_handler(whole_info)

        # make directory for each lambda handler
        make_lambda_code_directory(whole_info)

        # Put library modules in each lambda handler
        insert_imports_in_lambda_code_folder(whole_info)

        # show_result(whole_info)
        # sys.exit(getframeinfo(currentframe()))

        # Zip library modules and code for deployment
        make_zip_file_for_lambda_handler(whole_info)

        # show_result(whole_info)
        # sys.exit(getframeinfo(currentframe()))

        # Upload deployment list to s3
        upload_lambda_deployment_to_s3(whole_info)

        # Create lambda function using aws cli
        make_lambda_function_using_aws_cli(whole_info)

        # sys.exit(getframeinfo(currentframe()))

        # Make object that contains mapping func_name to lambda_func_arn
        map_func_to_func_arn(whole_info)

        # Making VM Hybrid
        write_hybrid_code(whole_info)

        # Write hybrid code to output directory
        save_hybrid_code_in_output_directory(whole_info)

        # Upload Hybrid to S3
        upload_hybrid_code_to_s3(whole_info)

        logger.info("End of Compiler")


if __name__ == "__main__":
    main()
