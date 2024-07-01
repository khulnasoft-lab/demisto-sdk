from collections import defaultdict
import os
from pathlib import Path
from typing import DefaultDict, List, Optional, Set

from demisto_sdk.commands.common.files.json_file import JsonFile
from demisto_sdk.commands.common.handlers import DEFAULT_JSON_HANDLER as json
from demisto_sdk.commands.common.logger import logger
from demisto_sdk.commands.content_graph.objects.base_content import BaseContent
from demisto_sdk.commands.validate.validators.base_validator import (
    FixResult,
    InvalidContentItemResult,
    ValidationCaughtExceptionResult,
    ValidationResult,
)


class ResultWriter:
    """
    Handle all the results, this class save all the results during run time and post the results when the whole execution is over.
    The class can either log the results to the terminal or write the results to a json file in a given path.
    The class also calculate the final result for the validations executions based on the validation results and list of errors that need to only the warnings.
    """

    def __init__(
        self,
        json_path: Optional[Path] = None,
        junit_path: Optional[Path] = None,
    ):
        """
            The ResultWriter init method.
        Args:
            json_file_path Optional[str]: The json path to write the outputs into.
        """
        self.validation_results: List[ValidationResult] = []
        self.fixing_results: List[FixResult] = []
        self.invalid_content_item_results: List[InvalidContentItemResult] = []
        self.validation_caught_exception_results: List[
            ValidationCaughtExceptionResult
        ] = []

        if json_path and json_path.is_dir():
            json_path = json_path / "validate_outputs.json"
        self.json_path = json_path

        self.junit_path = junit_path

    def write_junit(self):
        from junitparser.junitparser import (
            Error,
            Failure,
            JUnitXml,
            TestCase,
            TestSuite,
        )

        errors: DefaultDict[BaseContent, list] = defaultdict(list)

        for failure in self.validation_results + self.fixing_results:
            errors[failure.content_object].append(
                Failure(message=failure.format_readable_message)
            )

        for error in self.validation_caught_exception_results:
            if not error.content_object:
                logger.warning(
                    f"no content item for error {error!s}, not writing it to Junit file"
                )
                continue

            errors[error.content_object].append(
                Error(message=f"{error.format_readable_message}")
            )
        xml = JUnitXml()

        for content_item, results in errors.items():
            suite = TestSuite(f"{content_item.content_type} {content_item.object_id}")
            suite.add_testcases(results)
            xml.add_testsuite(suite)
            
        # Create cases
        case1 = TestCase("case1", "class.name", 0.5)  # params are optional
        case1.classname = "modified.class.name"  # specify or change case attrs
        case1.result = [Skipped()]  # You can have a list of results
        case2 = TestCase("case2")
        case2.result = [Error("Example error message", "the_error_type")]

        # Create suite and add cases
        suite = TestSuite("suite1")
        suite.add_property("build", "55")
        suite.add_testcase(case1)
        suite.add_testcase(case2)
        suite.remove_testcase(case2)

        # Bulk add cases to suite
        case3 = TestCase("case3")
        case4 = TestCase("case4")
        suite.add_testcases([case3, case4])

        # Add suite to JunitXml
        xml = JUnitXml()
        xml.add_testsuite(suite)
        xml.write("junit.xml")
        suite = TestSuite()

    def post_results(
        self,
        only_throw_warning: Optional[List[str]] = None,
    ) -> int:
        """
            Go through the validation results list,
            posting the warnings / failure message for failed validation,
            and calculates the exit_code.

        Returns:
            int: The exit code number - 1 if the validations failed, otherwise return 0
        """
        fixed_objects_set: Set[BaseContent] = set()
        exit_code = 0
        if self.json_path:
            self.write_json()
        if self.junit_path:
            self.write_junit()

        for result in self.validation_results:
            if only_throw_warning and result.validator.error_code in only_throw_warning:
                logger.warning(f"[yellow]{result.format_readable_message}[/yellow]")
            else:
                logger.error(f"[red]{result.format_readable_message}[/red]")
                exit_code = 1
        for fixing_result in self.fixing_results:
            fixed_objects_set.add(fixing_result.content_object)
            if (
                not only_throw_warning
                or fixing_result.validator.error_code not in only_throw_warning
            ):
                exit_code = 1
            logger.warning(f"[yellow]{fixing_result.format_readable_message}[/yellow]")
        for result in self.invalid_content_item_results:
            logger.error(f"[red]{result.format_readable_message}[/red]")
            exit_code = 1
        for result in self.validation_caught_exception_results:
            logger.error(f"[red]{result.format_readable_message}[/red]")
            exit_code = 1
        if not exit_code:
            logger.info("[green]All validations passed.[/green]")
        for fixed_object in fixed_objects_set:
            fixed_object.save()
        return exit_code

    def write_json(self):
        """
        If the json path argument is given,
        Writing all the results into a json file located in the given path.
        """
        if self.json_path is None:
            raise ValueError("Validate JSON output path was not supplied")

        json_validations_list = [
            result.format_json_message for result in self.validation_results
        ]
        json_fixing_list = [
            fixing_result.format_json_message for fixing_result in self.fixing_results
        ]
        json_invalid_content_item_list = [
            result.format_json_message for result in self.invalid_content_item_results
        ]
        json_validation_caught_exception_list = [
            result.format_json_message
            for result in self.validation_caught_exception_results
        ]
        results = {
            "validations": json_validations_list,
            "fixed validations": json_fixing_list,
            "invalid content items": json_invalid_content_item_list,
            "Validations that caught exceptions": json_validation_caught_exception_list,
        }

        JsonFile.write(results, self.json_path, indent=4)

    def append_validation_results(self, validation_result: ValidationResult):
        """Append an item to the validation results list.

        Args:
            validation_result (ValidationResult): the validation result to append.
        """
        self.validation_results.append(validation_result)

    def append_fix_results(self, fixing_result: FixResult):
        """Append an item to the fixing results list.

        Args:
            fixing_result (FixResult): the fixing result to append.
        """
        self.fixing_results.append(fixing_result)

    def append_validation_caught_exception_results(
        self, validation_caught_exception_results: ValidationCaughtExceptionResult
    ):
        """Append an item to the validation_caught_exception_results list.

        Args:
            validation_caught_exception_results (ValidationCaughtExceptionResult): the validation_caught_exception result to append.
        """
        self.validation_caught_exception_results.append(
            validation_caught_exception_results
        )

    def extend_validation_results(self, validation_results: List[ValidationResult]):
        """Extending the list of ValidationResult objects with a given list of validation results.

        Args:
            validation_results (List[ValidationResult]): The list of ValidationResult objects to add to the existing list.
        """
        self.validation_results.extend(validation_results)

    def extend_fix_results(self, fixing_results: List[FixResult]):
        """Extending the list of FixResult objects with a given list of FixResult objects.

        Args:
            fixing_results (List[FixResult]): The list of FixResult objects to add to the existing list.
        """
        self.fixing_results.extend(fixing_results)

    def extend_invalid_content_item_results(
        self, invalid_content_item_results: List[InvalidContentItemResult]
    ):
        """Extending the list of InvalidContentItemResult objects with a given list of InvalidContentItemResult objects.

        Args:
            non_content_item_results (List[InvalidContentItemResult]): The List of InvalidContentItemResult objects to add to the existing list.
        """
        self.invalid_content_item_results.extend(invalid_content_item_results)

    def extend_validation_caught_exception_results(
        self, validation_caught_exception_results: List[ValidationCaughtExceptionResult]
    ):
        """Extending the list of ValidationCaughtExceptionResult objects with a given list of ValidationCaughtExceptionResult objects.

        Args:
            non_content_item_results (List[ValidationCaughtExceptionResult]): The List of ValidationCaughtExceptionResult objects to add to the existing list.
        """
        self.validation_caught_exception_results.extend(
            validation_caught_exception_results
        )
