import copy
from copy import deepcopy
from os.path import join
from time import sleep

import pytest
import requests
from requests.adapters import HTTPAdapter
from typer.testing import CliRunner
from urllib3 import Retry

from demisto_sdk.__main__ import app
from demisto_sdk.commands.common import tools
from demisto_sdk.commands.common.constants import (
    DEFAULT_IMAGE_BASE64,
)
from demisto_sdk.commands.common.content.content import Content
from demisto_sdk.commands.common.git_util import GitUtil
from demisto_sdk.commands.common.hook_validations.base_validator import BaseValidator
from demisto_sdk.commands.common.hook_validations.classifier import ClassifierValidator
from demisto_sdk.commands.common.hook_validations.content_entity_validator import (
    ContentEntityValidator,
)
from demisto_sdk.commands.common.hook_validations.image import ImageValidator
from demisto_sdk.commands.common.hook_validations.integration import (
    IntegrationValidator,
)
from demisto_sdk.commands.common.hook_validations.mapper import MapperValidator
from demisto_sdk.commands.common.hook_validations.pack_unique_files import (
    PackUniqueFilesValidator,
)
from demisto_sdk.commands.common.hook_validations.playbook import PlaybookValidator
from demisto_sdk.commands.common.hook_validations.readme import (
    ReadMeValidator,
    mdx_server_is_up,
)
from demisto_sdk.commands.common.legacy_git_tools import git_path
from demisto_sdk.commands.common.MDXServer import start_local_MDX_server
from demisto_sdk.commands.common.tools import get_yaml
from demisto_sdk.commands.find_dependencies.find_dependencies import PackDependencies
from demisto_sdk.commands.validate.old_validate_manager import OldValidateManager
from demisto_sdk.tests.constants_test import (
    CONTENT_REPO_EXAMPLE_ROOT,
    NOT_VALID_IMAGE_PATH,
)
from demisto_sdk.tests.test_files.validate_integration_test_valid_types import (
    DASHBOARD,
    EMPTY_ID_SET,
    GENERIC_DEFINITION,
    GENERIC_FIELD,
    GENERIC_MODULE,
    GENERIC_TYPE,
    INCIDENT_FIELD,
    INCIDENT_TYPE,
    INDICATOR_FIELD,
    LAYOUT,
    LAYOUTS_CONTAINER,
    MAPPER,
    NEW_CLASSIFIER,
    OLD_CLASSIFIER,
    REPORT,
    REPUTATION,
    WIDGET,
)
from TestSuite.test_tools import ChangeCWD

mp = pytest.MonkeyPatch()
mp.setenv("COLUMNS", "1000")

VALIDATE_CMD = "validate"
TEST_FILES_PATH = join(git_path(), "demisto_sdk", "tests", "test_files")
AZURE_FEED_PACK_PATH = join(
    TEST_FILES_PATH, "content_repo_example", "Packs", "FeedAzure"
)
AZURE_FEED_INVALID_PACK_PATH = join(
    TEST_FILES_PATH, "content_repo_example", "Packs", "FeedAzureab"
)
VALID_PACK_PATH = join(
    TEST_FILES_PATH, "content_repo_example", "Packs", "FeedAzureValid"
)
VALID_PLAYBOOK_FILE_PATH = join(
    TEST_FILES_PATH,
    "Packs",
    "CortexXDR",
    "Playbooks",
    "Cortex_XDR_Incident_Handling.yml",
)
INVALID_PLAYBOOK_FILE_PATH = join(
    TEST_FILES_PATH,
    "Packs",
    "CortexXDR",
    "Playbooks",
    "Cortex_XDR_Incident_Handling_invalid.yml",
)
VALID_DEPRECATED_PLAYBOOK_FILE_PATH = join(
    TEST_FILES_PATH, "Packs", "CortexXDR", "Playbooks", "Valid_Deprecated_Playbook.yml"
)
INVALID_DEPRECATED_PLAYBOOK_FILE_PATH = join(
    TEST_FILES_PATH,
    "Packs",
    "CortexXDR",
    "Playbooks",
    "Invalid_Deprecated_Playbook.yml",
)
VALID_SCRIPT_PATH = join(
    TEST_FILES_PATH,
    "Packs",
    "CortexXDR",
    "Scripts",
    "EntryWidgetNumberHostsXDR",
    "EntryWidgetNumberHostsXDR.yml",
)

CONF_JSON_MOCK = {
    "tests": [{"integrations": "AzureFeed", "playbookID": "AzureFeed - Test"}]
}


@pytest.fixture(autouse=True)
def set_git_test_env(mocker):
    mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
    mocker.patch.object(Content, "git_util", return_value=GitUtil())
    mocker.patch.object(
        OldValidateManager, "setup_prev_ver", return_value="origin/master"
    )
    mocker.patch.object(GitUtil, "_is_file_git_ignored", return_value=False)
    mocker.patch.object(
        OldValidateManager, "get_all_files_edited_in_pack_ignore", return_value=set()
    )


class TestGenericFieldValidation:
    def test_valid_generic_field(self, mocker, repo):
        """
        Given
        - Valid generic field.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack.create_generic_field("generic-field", GENERIC_FIELD)
        generic_field_path = pack.generic_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    generic_field_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert f"Validating {generic_field_path} as genericfield" in result.output
        assert "The files are valid" in result.output

    def test_invalid_schema_generic_field(self, mocker, repo):
        """
        Given
        - invalid generic field - adding a new field named 'test' which doesn't exist in scheme.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on ST108 - a field which doesn't defined in the scheme.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_field_copy = GENERIC_FIELD.copy()
        generic_field_copy["test"] = True
        pack.create_generic_field("generic-field", generic_field_copy)
        generic_field_path = pack.generic_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    generic_field_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_field_path} as genericfield",
                    "ST108",
                    "The files were found as invalid",
                ]
            ]
        )

    @pytest.mark.parametrize(
        "field_to_test, invalid_value, expected_error_code",
        [
            ("fromVersion", "6.0.0", "BA106"),
            ("group", 0, "GF100"),
            ("id", "asset_operatingsystem", "GF101"),
        ],
    )
    def test_invalid_generic_field(
        self, mocker, repo, field_to_test, invalid_value, expected_error_code
    ):
        """
        Given
        - invalid generic field.

        When
        - Running validation on it.

        Then
        - Ensure validation fails with the right error code.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_field_copy = GENERIC_FIELD.copy()
        generic_field_copy[field_to_test] = invalid_value
        pack.create_generic_field("generic-field", generic_field_copy)
        generic_field_path = pack.generic_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    generic_field_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1

        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_field_path} as genericfield",
                    expected_error_code,
                    "The files were found as invalid",
                ]
            ]
        )


class TestGenericTypeValidation:
    def test_valid_generic_type(self, mocker, repo):
        """
        Given
        - Valid generic type.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack.create_generic_type("generic-type", GENERIC_TYPE)
        generic_type_path = pack.generic_types[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    generic_type_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_type_path} as generictype",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_schema_generic_type(self, mocker, repo):
        """
        Given
        - invalid generic type - adding a new field named 'test' which doesn't exist in scheme.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on ST108 - a field which doesn't defined in the scheme.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_type_copy = GENERIC_TYPE.copy()
        generic_type_copy["test"] = True
        pack.create_generic_type("generic-type", generic_type_copy)
        generic_type_path = pack.generic_types[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    generic_type_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_type_path} as generictype",
                    "ST108",
                    "The files were found as invalid",
                ]
            ]
        )

    def test_invalid_from_version_generic_type(self, mocker, repo):
        """
        Given
        - invalid generic type - 'fromVersion' field is below 6.5.0.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on BA106 - no minimal fromversion in file.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_type_copy = GENERIC_TYPE.copy()
        generic_type_copy["fromVersion"] = "6.0.0"
        pack.create_generic_type("generic-type", generic_type_copy)
        generic_type_path = pack.generic_types[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    generic_type_path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_type_path} as generictype",
                    "BA106",
                    "The files were found as invalid",
                ]
            ]
        )


class TestGenericModuleValidation:
    def test_valid_generic_module(self, mocker, repo):
        """
        Given
        - Valid generic module.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack.create_generic_module("generic-module", GENERIC_MODULE)
        generic_module_path = pack.generic_modules[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    generic_module_path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_module_path} as genericmodule",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_schema_generic_module(self, mocker, repo):
        """
        Given
        - invalid generic module - adding a new field named 'test' which doesn't exist in scheme.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on ST108 - a field which doesn't defined in the scheme.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_module_copy = GENERIC_MODULE.copy()
        generic_module_copy["test"] = True
        pack.create_generic_module("generic-module", generic_module_copy)
        generic_module_path = pack.generic_modules[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    generic_module_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_module_path} as genericmodule",
                    "ST108",
                    "The files were found as invalid",
                ]
            ]
        )

    def test_invalid_fromversion_generic_module(self, mocker, repo):
        """
        Given
        - invalid generic module - 'fromVersion' field is below 6.5.0.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on BA106 - no minimal fromversion in file.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_module_copy = GENERIC_MODULE.copy()
        generic_module_copy["fromVersion"] = "6.0.0"
        pack.create_generic_module("generic-module", generic_module_copy)
        generic_module_path = pack.generic_modules[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    generic_module_path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {generic_module_path} as genericmodule",
                    "BA106",
                    "The files were found as invalid",
                ]
            ]
        )


class TestGenericDefinitionValidation:
    def test_valid_generic_definition(self, mocker, repo):
        """
        Given
        - Valid generic definition.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_def_copy = GENERIC_DEFINITION.copy()
        genefic_def = pack.create_generic_definition(
            "generic-definition", generic_def_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    genefic_def.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {genefic_def.path} as genericdefinition",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_schema_generic_definition(self, mocker, repo):
        """
        Given
        - Invalid generic definition.

        When
        - Running validation on it.

        Then
        - Ensure validation fails.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_def_copy = GENERIC_DEFINITION.copy()
        generic_def_copy["anotherField"] = False
        genefic_def = pack.create_generic_definition(
            "generic-definition", generic_def_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    genefic_def.path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {genefic_def.path} as genericdefinition",
                    "ST108",
                    "The files were found as invalid",
                ]
            ]
        )

    def test_invalid_fromversion_generic_definition(self, mocker, repo):
        """
        Given
        - invalid generic definition - 'fromVersion' field is below 6.5.0.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on BA106 - no minimal fromversion in file.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        generic_def_copy = GENERIC_DEFINITION.copy()
        generic_def_copy["fromVersion"] = "6.0.0"
        genefic_def = pack.create_generic_definition(
            "generic-definition", generic_def_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    genefic_def.path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {genefic_def.path} as genericdefinition",
                    "BA106",
                    "The files were found as invalid",
                ]
            ]
        )


class TestIncidentFieldValidation:
    def test_valid_incident_field(self, mocker, repo):
        """
        Given
        - Valid `city` incident field.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack.create_incident_field("incident-field", INCIDENT_FIELD)
        incident_field_path = pack.incident_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_field_path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {incident_field_path} as incidentfield",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_incident_field(self, mocker, repo):
        """
        Given
        - invalid incident field - system field set to true.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on IF102 - wrong system field value.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_field_copy = INCIDENT_FIELD.copy()
        incident_field_copy["system"] = True
        pack.create_incident_field("incident-field", incident_field_copy)
        incident_field_path = pack.incident_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_field_path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert f"Validating {incident_field_path} as incidentfield" in result.output
        assert "IF102" in result.output
        assert "The system key must be set to False" in result.output

    def test_valid_scripts_in_incident_field(self, mocker, repo):
        """
        Given
        - Valid incident field - with scripts that exist in the id_set json.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_field_copy = INCIDENT_FIELD.copy()
        incident_field_copy["script"] = "test_script"
        incident_field_copy["fieldCalcScript"] = "test_calc_script"
        pack.create_incident_field("incident-field", incident_field_copy)
        incident_field_path = pack.incident_fields[0].path

        id_set = copy.deepcopy(EMPTY_ID_SET)
        id_set["scripts"].extend(
            [
                {
                    "test_script": {
                        "name": "test_script",
                        "file_path": "Packs/DeveloperTools/TestPlaybooks/test_script.yml",
                        "fromversion": "5.0.0",
                        "pack": "DeveloperTools",
                    }
                },
                {
                    "test_calc_script": {
                        "name": "test_calc_script",
                        "file_path": "Packs/DeveloperTools/TestPlaybooks/test_calc_script.yml",
                        "fromversion": "5.0.0",
                        "pack": "DeveloperTools",
                    }
                },
            ]
        )
        repo.id_set.write_json(id_set)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_field_path,
                    "-s",
                    "-idp",
                    repo.id_set.path,
                    "-pc",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {incident_field_path} as incidentfield",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_scripts_in_incident_field(self, mocker, repo):
        """
        Given
        - An incident field with script that isn't exist in the id_set json.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on IF114 - incident field with non existent script id
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_field_copy = INCIDENT_FIELD.copy()
        incident_field_copy["script"] = "test_script"
        incident_field_copy["fieldCalcScript"] = "test_calc_script"
        pack.create_incident_field("incident-field", incident_field_copy)
        incident_field_path = pack.incident_fields[0].path

        id_set = copy.deepcopy(EMPTY_ID_SET)
        id_set["scripts"].append(
            {
                "test_calc_script": {
                    "name": "test_calc_script",
                    "file_path": "Packs/DeveloperTools/TestPlaybooks/test_calc_script.yml",
                    "fromversion": "5.0.0",
                    "pack": "DeveloperTools",
                }
            }
        )
        repo.id_set.write_json(id_set)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_field_path,
                    "-s",
                    "-idp",
                    repo.id_set.path,
                    "-pc",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {incident_field_path} as incidentfield",
                    "IF114",
                ]
            ]
        )
        assert (
            "the following scripts were not found in the id_set.json" in result.output
        )
        assert result.exit_code == 1


class TestDeprecatedIntegration:
    def test_valid_deprecated_integration(self, mocker, repo):
        """
        Given
        - Valid deprecated integration.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")

        valid_integration_yml = deepcopy(
            get_yaml(join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"))
        )
        valid_integration_yml["deprecated"] = True
        valid_integration_yml["display"] = "ServiceNow (Deprecated)"
        valid_integration_yml["description"] = (
            "Deprecated. Use the ServiceNow v2 integration instead."
        )
        integration = pack.create_integration(yml=valid_integration_yml)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{integration.yml.rel_path} as integration",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_deprecated_integration_display_name(self, mocker, repo):
        """
        Given
        - invalid deprecated integration - The fields of deprecated are missing.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on - invalid_deprecated_integration.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        invalid_integration_yml = deepcopy(
            get_yaml(join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"))
        )
        invalid_integration_yml["deprecated"] = True
        invalid_integration_yml["description"] = "Deprecated."
        integration = pack.create_integration(yml=invalid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [current_str in result.output for current_str in ["IN127", "Deprecated"]]
        )
        assert result.exit_code == 1

    def test_invalid_integration_deprecation__only_display_name_suffix(
        self, mocker, repo
    ):
        """
        Given
                an integration where the display name declares deprecation but the deprecation flag is False.
        When
                Running validation on it.
        Then
                Ensure validation fails
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")

        yml = deepcopy(
            get_yaml(join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"))
        )
        yml["display"] += " (Deprecated)"
        yml["deprecated"] = False  # redefining the default, for explicitness and sanity
        integration = pack.create_integration(yml=yml)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert "IN160" in result.output
        assert result.exit_code == 1

    @pytest.mark.parametrize(
        "description",
        (
            "Deprecated. Use the ServiceNow v2 integration instead.",
            "Deprecated. No available replacement.",
        ),
    )
    def test_invalid_deprecation__only_description_deprecated(
        self, mocker, repo, description: str
    ):
        """
        Given
                an integration where the description declares deprecation but the deprecation flag is False.
        When
                Running validation on it.
        Then
                Ensure validation fails
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")

        yml = deepcopy(
            get_yaml(join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"))
        )
        yml["description"] = description
        yml["deprecated"] = False  # redefining the default, for explicitness and sanity
        integration = pack.create_integration(yml=yml)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert "IN158" in result.output
        assert result.exit_code == 1

    def test_invalid_deprecated_integration_description(self, mocker, repo):
        """
        Given
        - invalid deprecated integration - The fields of deprecated are missing.

        When
        - Running validation on it.

        Then
        - Ensure validation fails on - invalid_deprecated_integration.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        invalid_integration_yml = get_yaml(pack_integration_path)
        invalid_integration_yml = deepcopy(invalid_integration_yml)
        invalid_integration_yml["deprecated"] = True
        invalid_integration_yml["display"] = "(Deprecated)"
        integration = pack.create_integration(yml=invalid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert f"{integration.yml.rel_path} as integration" in result.output
        assert all(
            current_str in result.output
            for current_str in [
                "IN128",
                "Deprecated",
            ]
        )
        assert result.exit_code == 1

    def test_invalid_bc_deprecated_integration(self, mocker, repo):
        """
        Given
        - invalid but backwards compatible deprecated integration with valid deprecated fields.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path)
        valid_integration_yml = deepcopy(valid_integration_yml)
        valid_integration_yml["deprecated"] = True
        valid_integration_yml["display"] = "ServiceNow (Deprecated)"
        valid_integration_yml["description"] = (
            "Deprecated. Use the ServiceNow v2 integration instead."
        )
        valid_integration_yml["commonfields"]["version"] = -2
        integration = pack.create_integration(yml=valid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                    "--print-ignored-files",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{integration.yml.rel_path} as integration",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_modified_bc_deprecated_integration(self, mocker, repo):
        """
        Given
        - invalid modified but backwards compatible deprecated integration with valid deprecated fields.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path)
        valid_integration_yml = deepcopy(valid_integration_yml)
        valid_integration_yml["deprecated"] = True
        valid_integration_yml["display"] = "ServiceNow (Deprecated)"
        valid_integration_yml["description"] = (
            "Deprecated. Use the ServiceNow v2 integration instead."
        )
        valid_integration_yml["commonfields"]["version"] = -2
        integration = pack.create_integration(yml=valid_integration_yml)
        modified_files = {integration.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--print-ignored-files",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )

        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {integration.yml.rel_path} as integration",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_bc_unsupported_toversion_integration(self, mocker, repo):
        """
        Given
        - invalid but backwards compatible integration with toversion < OLDEST_SUPPORTED_VERSION

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path)
        valid_integration_yml = deepcopy(valid_integration_yml)
        valid_integration_yml["toversion"] = "4.4.4"
        valid_integration_yml["commonfields"]["version"] = -2
        integration = pack.create_integration(yml=valid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                    "--print-ignored-files",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{integration.yml.rel_path} as integration",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_modified_invalid_bc_unsupported_toversion_integration(self, mocker, repo):
        """
        Given
        - A modified invalid but backwards compatible integration with toversion < OLDEST_SUPPORTED_VERSION

        When
        - Running validate -g on it.

        Then
        - Ensure validation passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )

        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path)
        valid_integration_yml = deepcopy(valid_integration_yml)
        valid_integration_yml["toversion"] = "4.4.4"
        valid_integration_yml["commonfields"]["version"] = -2
        integration = pack.create_integration(yml=valid_integration_yml)

        modified_files = {integration.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--print-ignored-files",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {integration.yml.rel_path} as integration",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0


class TestIntegrationValidation:
    def test_valid_integration(self, mocker, repo):
        """
        Given
        - a valid Integration.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as an integration.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.integration.tools.get_current_categories",
            return_value=[valid_integration_yml.get("category")],
        )
        integration = pack.create_integration("integration0", yml=valid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{integration.yml.rel_path} as integration",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_changed_integration_param_to_required(self, mocker, repo):
        """
        Given
        - an invalid Integration - an integration parameter changed to be required

        When
        - Running validate on it.

        Then
        - Ensure validate fails on wrong required value
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )

        pack = repo.create_pack("Pack1")
        new_integration = pack.create_integration()
        new_integration.create_default_integration()
        new_integration.yml.update(
            {
                "configuration": [
                    {
                        "defaultvalue": "",
                        "display": "test",
                        "name": "test",
                        "required": True,
                        "type": 8,
                    }
                ]
            }
        )
        old_integration = pack.create_integration()
        old_integration.create_default_integration()
        old_integration.yml.update(
            {
                "configuration": [
                    {
                        "defaultvalue": "",
                        "display": "test",
                        "name": "test",
                        "required": False,
                        "type": 8,
                    }
                ]
            }
        )

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    new_integration.yml.rel_path,
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )

        assert all(
            [
                current_str in result.output
                for current_str in [
                    "The required field of the test parameter should be False",
                    "IN102",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_invalid_integration(self, mocker, repo):
        """
        Given
        - an invalid Integration - no fromversion though it is a feed.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on IN119 - wrong fromversion in feed integration.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        invalid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        del invalid_integration_yml["fromversion"]
        integration = pack.create_integration(yml=invalid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{integration.yml.rel_path} as integration",
                    "IN119",
                ]
            ]
        )
        assert "This is a feed and has wrong fromversion." in result.output
        assert result.exit_code == 1

    def test_negative__non_latest_docker_image(self, mocker):
        """
        Given
        - FeedAzure integration with non-latest docker image.

        When
        - Running validation on it.

        Then
        - Ensure validation fails.
        - Ensure failure message on non-latest docker image.
        """

        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.integration.tools.get_current_categories",
            return_value=[valid_integration_yml.get("category")],
        )
        with ChangeCWD(CONTENT_REPO_EXAMPLE_ROOT):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    pack_integration_path,
                    "--no-conf-json",
                    "--allow-skipped",
                ],
            )

        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {pack_integration_path} as integration",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_negative__hidden_param(self, mocker):
        """
        Given
        - Integration with not allowed hidden params: ["server", "credentials"].

        When
        - Running validation on it.

        Then
        - Ensure validation fails.
        - Ensure failure message on hidden params.
        """

        mocker.patch.object(
            IntegrationValidator,
            "has_no_fromlicense_key_in_contributions_integration",
            return_value=True,
        )
        mocker.patch.object(
            IntegrationValidator, "is_api_token_in_credential_type", return_value=True
        )

        integration_path = join(
            TEST_FILES_PATH, "integration-invalid-no-hidden-params.yml"
        )
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.integration.tools.get_current_categories",
            return_value=["Network Security"],
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                integration_path,
                "--no-conf-json",
                "--allow-skipped",
            ],
        )
        assert result.exit_code == 1
        assert f"Validating {integration_path} as integration" in result.output

    def test_positive_hidden_param(self, mocker):
        """
        Given
        - Integration with allowed hidden param: "longRunning".

        When
        - Running validation on it.

        Then
        - Ensure validation succeeds.
        """

        integration_path = join(
            TEST_FILES_PATH, "integration-valid-no-unallowed-hidden-params.yml"
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                integration_path,
                "--no-conf-json",
                "--allow-skipped",
            ],
        )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {integration_path} as integration",
                ]
            ]
        )
        assert "can't be hidden. Please remove this field" not in result.output

    def test_duplicate_param_and_argument_invalid(self, mocker, repo):
        """
        Given
        - An invalid Integration - duplicate argument in a command, and duplicate param.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on IN113 - Duplicate argument in a command in the integration.
        - Ensure validate fails on IN114 - Duplicate parameter in integration.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        invalid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        first_command_args = invalid_integration_yml["script"]["commands"][0][
            "arguments"
        ]
        first_command_args.append(first_command_args[0])
        invalid_integration_yml["configuration"].append(
            {
                "additionalinfo": "Supports CSV values",
                "display": "Tags",
                "name": "feedTags",
                "required": False,
                "type": 0,
            }
        )
        integration = pack.create_integration(yml=invalid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert f"{integration.yml.rel_path} as integration" in result.output
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "IN113",
                    "IN114",
                    """The parameter 'feedTags' of the file is duplicated""",
                    f"""The argument '{first_command_args[0]['name']}' is duplicated""",
                ]
            ]
        )

    def test_missing_mandatory_field_in_yml(self, mocker, repo):
        """
        Given
        - An invalid Integration - argument description is missing

        When
        - Running validate on it.

        Then
        - Ensure validate fails on ST107 - pykwalify_missing_parameter.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        invalid_integration_yml = get_yaml(pack_integration_path)
        first_argument = invalid_integration_yml["script"]["commands"][0]["arguments"][
            0
        ]
        first_argument.pop("description")
        integration = pack.create_integration(yml=invalid_integration_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert "ST107" in result.output
        assert 'Please add the field "description" to the path'

    @pytest.mark.parametrize(
        "field,description,should_pass",
        (
            ("DBotScore.Score", "my custom description", True),
            ("DBotScore.Score", "", False),
        ),
    )
    def test_empty_default_descriptions(
        self, mocker, repo, field: str, description: str, should_pass: bool
    ):
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )
        pack = repo.create_pack(f"{field}-{description}")
        integration = pack.create_integration()
        integration.create_default_integration()
        integration.yml.update(
            {
                "script": {
                    "script": "-",
                    "type": "python",
                    "commands": [
                        {
                            "name": "foo",
                            "description": "bar",
                            "outputs": [
                                {"contextPath": field, "description": description},
                                {"contextPath": "same", "description": ""},
                            ],
                        }
                    ],
                }
            }
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    integration.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
            assert should_pass != ("IN149" in result.output)


class TestPackValidation:
    def test_integration_validate_pack_positive(self, mocker):
        """
        Given
        - FeedAzure integration valid Pack.

        When
        - Running validation on the pack.

        Then
        - See that the validation succeed.
        """

        mocker.patch.object(
            ContentEntityValidator, "_load_conf_file", return_value=CONF_JSON_MOCK
        )
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            IntegrationValidator, "is_there_separators_in_names", return_value=True
        )
        mocker.patch.object(
            IntegrationValidator, "is_docker_image_valid", return_value=True
        )
        mocker.patch.object(
            IntegrationValidator, "is_valid_py_file_names", return_value=True
        )
        mocker.patch.object(
            ContentEntityValidator, "validate_readme_exists", return_value=True
        )
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.pack_unique_files.get_current_usecases",
            return_value=[],
        )
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.integration.tools.get_current_categories",
            return_value=["Data Enrichment & Threat Intelligence", "Analytics & SIEM"],
        )
        mocker.patch(
            "demisto_sdk.commands.validate.tools.get_approved_tags_from_branch",
            return_value={},
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                VALID_PACK_PATH,
                "--no-conf-json",
                "--allow-skipped",
            ],
        )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{VALID_PACK_PATH} unique pack files",
                    f"Validating pack {VALID_PACK_PATH}",
                    f"{VALID_PACK_PATH}/Integrations/FeedAzureValid/FeedAzureValid.yml",
                    f"{VALID_PACK_PATH}/IncidentFields/incidentfield-city.json",
                    "The files are valid",
                ]
            ]
        )

    def test_integration_validate_pack_negative(self, mocker):
        """
        Given
        - FeedAzure integration invalid Pack with invalid playbook that has unhandled conditional task.

        When
        - Running validation on the pack.

        Then
        - Ensure validation fails.
        - Ensure error message regarding unhandled conditional task in playbook.
        """

        mocker.patch.object(
            ContentEntityValidator, "_load_conf_file", return_value=CONF_JSON_MOCK
        )
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.pack_unique_files.get_current_usecases",
            return_value=[],
        )
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.integration.tools.get_current_categories",
            return_value=[],
        )
        mocker.patch(
            "demisto_sdk.commands.validate.tools.get_approved_tags_from_branch",
            return_value={},
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                AZURE_FEED_PACK_PATH,
                "--no-conf-json",
                "--allow-skipped",
            ],
        )
        assert all(
            current_str in result.output
            for current_str in [
                f"{AZURE_FEED_PACK_PATH}/IncidentFields/incidentfield-city.json",
                "The files were found as invalid, the exact error message can be located above",
            ]
        )
        assert all(
            current_str in result.output
            for current_str in [
                f"{AZURE_FEED_PACK_PATH}",
                f"{AZURE_FEED_PACK_PATH}/Integrations/FeedAzure/FeedAzure.yml",
                "Playbook conditional task with id:15 has an unhandled condition: MAYBE",
            ]
        )

    def test_integration_validate_invalid_pack_path(self):
        """
        Given
        - FeedAzure integration invalid Pack path.

        When
        - Running validation on the pack.

        Then
        - See that the validation failed.
        """
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                AZURE_FEED_INVALID_PACK_PATH,
                "--no-conf-json",
            ],
        )
        assert "does not exist" in result.stderr
        assert result.exit_code == 2


class TestClassifierValidation:
    def test_valid_new_classifier(self, mocker, repo):
        """
        Given
        - Valid new classifier

        When
        - Running validate on it.

        Then
        - Ensure validate passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        classifier = pack.create_classifier("new_classifier", NEW_CLASSIFIER)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    classifier.path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_from_version_in_new_classifiers(self, mocker, repo):
        """
        Given
        - New classifier with invalid from version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        new_classifier_copy = NEW_CLASSIFIER.copy()
        new_classifier_copy["fromVersion"] = "5.0.0"

        classifier = pack.create_classifier("new_classifier", new_classifier_copy)
        with ChangeCWD(pack.repo_path):
            result = CliRunner(mix_stderr=False).invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier",
                    "fromVersion field in new classifiers needs to be higher or equal to 6.0.0",
                ]
            ]
        )

    def test_invalid_to_version_in_new_classifiers(self, mocker, repo):
        """
        Given
        - New classifier with invalid to version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        new_classifier_copy = NEW_CLASSIFIER.copy()
        new_classifier_copy["toVersion"] = "5.0.0"
        classifier = pack.create_classifier("new_classifier", new_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {classifier.path} as classifier" in result.output
        assert (
            "toVersion field in new classifiers needs to be higher than 6.0.0"
            in result.output
        )
        assert result.exit_code == 1

    def test_classifier_from_version_higher_to_version(self, mocker, repo):
        """
        Given
        - New classifier with from version field higher than to version field.

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        new_classifier_copy = NEW_CLASSIFIER.copy()
        new_classifier_copy["toVersion"] = "6.0.2"
        new_classifier_copy["fromVersion"] = "6.0.5"
        classifier = pack.create_classifier("new_classifier", new_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {classifier.path} as classifier" in result.output
        assert (
            "The `fromVersion` field cannot be higher or equal to the `toVersion` field."
            in result.output
        )
        assert result.exit_code == 1

    def test_missing_mandatory_field_in_new_classifier(self, mocker, repo):
        """
        Given
        - New classifier with missing mandatory field (id).

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        new_classifier_copy = NEW_CLASSIFIER.copy()
        del new_classifier_copy["id"]
        classifier = pack.create_classifier("new_classifier", new_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier",
                ]
            ]
        )
        assert 'Missing the field "id" in root' in result.output
        assert result.exit_code == 1

    def test_missing_fromversion_field_in_new_classifier(self, mocker, repo):
        """
        Given
        - New classifier with missing from version field.

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        new_classifier_copy = NEW_CLASSIFIER.copy()
        del new_classifier_copy["fromVersion"]
        classifier = pack.create_classifier("new_classifier", new_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier",
                ]
            ]
        )
        assert "Must have fromVersion field in new classifiers" in result.output

    def test_invalid_type_in_new_classifier(self, mocker, repo):
        """
        Given
        - New classifier with invalid type field.

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        new_classifier_copy = NEW_CLASSIFIER.copy()
        new_classifier_copy["type"] = "test"
        classifier = pack.create_classifier("new_classifier", new_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert (
            "[BA102] - File PackName/Classifiers/classifier-new_classifier.json"
            in result.output
        )
        assert result.exit_code == 1

    def test_valid_old_classifier(self, mocker, repo):
        """
        Given
        - Valid old classifier

        When
        - Running validate on it.

        Then
        - Ensure validate passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(
            ClassifierValidator, "is_incident_field_exist", return_value=True
        )
        pack = repo.create_pack("PackName")
        classifier = pack.create_classifier("old_classifier", OLD_CLASSIFIER)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier_5_9_9",
                    "The files are valid",
                ]
            ]
        )

    def test_invalid_from_version_in_old_classifiers(self, mocker, repo):
        """
        Given
        - Old classifier with invalid from version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        old_classifier_copy = OLD_CLASSIFIER.copy()
        old_classifier_copy["fromVersion"] = "6.0.0"
        classifier = pack.create_classifier("old_classifier", old_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier_5_9_9",
                ]
            ]
        )
        assert (
            "fromVersion field in old classifiers needs to be lower than 6.0.0"
        ) in result.output

    def test_invalid_to_version_in_old_classifiers(self, mocker, repo):
        """
        Given
        - Old classifier with invalid to version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        old_classifier_copy = OLD_CLASSIFIER.copy()
        old_classifier_copy["toVersion"] = "6.0.0"
        classifier = pack.create_classifier("old_classifier", old_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier_5_9_9",
                    f"Validating {classifier.path} as classifier_5_9_9",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_missing_mandatory_field_in_old_classifier(self, mocker, repo):
        """
        Given
        - Old classifier with missing mandatory field (id).

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        old_classifier_copy = OLD_CLASSIFIER.copy()
        del old_classifier_copy["id"]
        classifier = pack.create_classifier("old_classifier", old_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier_5_9_9",
                ]
            ]
        )
        assert ('Missing the field "id" in root') in result.output
        assert result.exit_code == 1

    def test_missing_toversion_field_in_old_classifier(self, mocker, repo):
        """
        Given
        - Old classifier with missing from version field.

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        old_classifier_copy = OLD_CLASSIFIER.copy()
        del old_classifier_copy["toVersion"]
        classifier = pack.create_classifier("old_classifier", old_classifier_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    classifier.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {classifier.path} as classifier_5_9_9",
                ]
            ]
        )
        assert ("Must have toVersion field in old classifiers") in result.output
        assert result.exit_code == 1


class TestMapperValidation:
    def test_valid_mapper(self, mocker, repo):
        """
        Given
        - Valid mapper

        When
        - Running validate on it.

        Then
        - Ensure validate passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(
            MapperValidator, "is_incident_field_exist", return_value=True
        )
        pack = repo.create_pack("PackName")
        mapper = pack.create_mapper("mapper", MAPPER)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    mapper.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {mapper.path} as mapper",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_from_version_in_mapper(self, mocker, repo):
        """
        Given
        - Mapper with invalid from version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        mapper_copy = MAPPER.copy()
        mapper_copy["fromVersion"] = "5.0.0"
        mapper = pack.create_mapper("mapper", mapper_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    mapper.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {mapper.path} as mapper",
                ]
            ]
        )
        assert (
            "fromVersion field in mapper needs to be higher or equal to 6.0.0"
        ) in result.output
        assert result.exit_code == 1

    def test_invalid_to_version_in_mapper(self, mocker, repo):
        """
        Given
        - Mapper with invalid to version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        mapper_copy = MAPPER.copy()
        mapper_copy["toVersion"] = "5.0.0"
        mapper = pack.create_mapper("mapper", mapper_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    mapper.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {mapper.path} as mapper" in result.output
        assert (
            "toVersion field in mapper needs to be higher than 6.0.0" in result.output
        )
        assert result.exit_code == 1

    def test_missing_mandatory_field_in_mapper(self, mocker, repo):
        """
        Given
        - Mapper with missing mandatory field (id).

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        mapper_copy = MAPPER.copy()
        del mapper_copy["id"]
        mapper = pack.create_mapper("mapper", mapper_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    mapper.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {mapper.path} as mapper",
                ]
            ]
        )
        assert ('Missing the field "id" in root') in result.output
        assert result.exit_code == 1

    def test_mapper_from_version_higher_to_version(self, mocker, repo):
        """
        Given
        - Mapper with from version field higher than to version field.

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        mapper_copy = MAPPER.copy()
        mapper_copy["toVersion"] = "6.0.2"
        mapper_copy["fromVersion"] = "6.0.5"
        mapper = pack.create_mapper("mapper", mapper_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    mapper.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {mapper.path} as mapper" in result.output
        assert (
            "The `fromVersion` field cannot be higher or equal to the `toVersion` field."
            in result.output
        )
        assert result.exit_code == 1

    def test_invalid_mapper_type(self, mocker, repo):
        """
        Given
        - Mapper with invalid type.

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        mapper_copy = MAPPER.copy()
        mapper_copy["type"] = "test"
        mapper = pack.create_mapper("mapper", mapper_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    mapper.path,
                ],
                catch_exceptions=False,
            )
        assert (
            "[BA102] - File PackName/Classifiers/classifier-mapper-mapper.json is not supported"
            in result.output
        )
        assert result.exit_code == 1


class TestDashboardValidation:
    def test_valid_dashboard(self, mocker, repo):
        """
        Given
        - a valid Dashboard.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a dashboard.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        dashboard = pack.create_dashboard("dashboard", DASHBOARD)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    dashboard.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {dashboard.path} as dashboard",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_dashboard(self, mocker, repo):
        """
        Given
        - an invalid dashboard (wrong version).

        When
        - Running validate on it.

        Then
        - Ensure validate fails on - BA100 wrong version error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        dashboard_copy = DASHBOARD.copy()
        dashboard_copy["version"] = 1
        dashboard = pack.create_dashboard("dashboard", dashboard_copy)
        with ChangeCWD(pack.repo_path):
            result = CliRunner(mix_stderr=False).invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    dashboard.path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert f"Validating {dashboard.path} as dashboard" in result.output
        assert "BA100" in result.output
        assert (
            "The version for our files should always be -1, please update the file."
        ) in result.output


class TestIndicatorFieldValidation:
    def test_valid_indicator_field(self, mocker, repo):
        """
        Given
        - a valid Indicator Field.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as an indicator field.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack.create_indicator_field("indicator-field", INDICATOR_FIELD)
        indicator_field_path = pack.indicator_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    indicator_field_path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {indicator_field_path} as indicatorfield",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_indicator_field(self, mocker, repo):
        """
        Given
        - an invalid Indicator Field - content key set to False.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on IF101 wrong content key value error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        indicator_field_copy = INDICATOR_FIELD.copy()
        indicator_field_copy["content"] = False
        pack.create_indicator_field("indicator-field", indicator_field_copy)
        indicator_field_path = pack.indicator_fields[0].path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    indicator_field_path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {indicator_field_path} as indicatorfield",
                    "IF101",
                ]
            ]
        )
        assert ("The content key must be set to True.") in result.output
        assert result.exit_code == 1


class TestIncidentTypeValidation:
    def test_valid_incident_type(self, mocker, repo):
        """
        Given
        - a valid Incident Type.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as an incident type.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_type = pack.create_incident_type("incident_type", INCIDENT_TYPE)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_type.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {incident_type.path} as incidenttype",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_incident_type(self, mocker, repo):
        """
        Given
        - an invalid Incident Type - days field has a negative number in it.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on IT100 wrong integer value in field.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_type_copy = INCIDENT_TYPE.copy()
        incident_type_copy["days"] = -1
        incident_type = pack.create_incident_type("incident_type", incident_type_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_type.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {incident_type.path} as incidenttype" in result.output
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "IT100",
                    "The field days needs to be a positive integer",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_valid_incident_type_with_extract_fields(self, mocker, repo):
        """
        Given
        - a valid Incident Type with auto-extract fields.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as an incident type.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_type_data = INCIDENT_TYPE.copy()
        incident_type_data["extractSettings"] = {
            "mode": "Specific",
            "fieldCliNameToExtractSettings": {
                "attachment": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": [],
                },
                "category": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": True,
                    "extractIndicatorTypesIDs": [],
                },
                "closenotes": {
                    "extractAsIsIndicatorTypeId": "IP",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": [],
                },
                "closinguserid": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": ["IP", "CIDR"],
                },
            },
        }
        incident_type = pack.create_incident_type("incident_type", incident_type_data)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_type.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {incident_type.path} as incidenttype",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_incident_type_with_extract_fields_wrong_field_formats(
        self, mocker, repo
    ):
        """
        Given
        - an invalid Incident Type with auto-extract fields.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on IT102.
        - Ensure all wrongly formatted extraction incident fields are listed in the output.
        - Ensure all valid extraction fields are not listed
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_type_data = INCIDENT_TYPE.copy()
        incident_type_data["extractSettings"] = {
            "mode": "Specific",
            "fieldCliNameToExtractSettings": {
                "attachment": {
                    "extractAsIsIndicatorTypeId": "Data1",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": ["Data2"],
                },
                "category": {
                    "extractAsIsIndicatorTypeId": "Data",
                    "isExtractingAllIndicatorTypes": True,
                    "extractIndicatorTypesIDs": [],
                },
                "closenotes": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": True,
                    "extractIndicatorTypesIDs": ["Data"],
                },
                "closinguserid": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": ["IP", "CIDR"],
                },
            },
        }
        incident_type = pack.create_incident_type("incident_type", incident_type_data)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_type.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "IT102",
                    "attachment",
                    "category",
                    "closenotes",
                    f"Validating {incident_type.path} as incidenttype",
                ]
            ]
        )
        # sanity check
        assert "closinguserid" not in result.output
        assert result.exit_code == 1

    def test_invalid_incident_type_with_extract_fields_invalid_mode(self, mocker, repo):
        """
        Given
        - an invalid Incident Type with auto-extract fields which have an invalid mode field.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on IT103.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        incident_type_data = INCIDENT_TYPE.copy()
        incident_type_data["extractSettings"] = {
            "mode": "Invalid",
            "fieldCliNameToExtractSettings": {
                "attachment": {
                    "extractAsIsIndicatorTypeId": "Data1",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": ["Data2"],
                },
                "category": {
                    "extractAsIsIndicatorTypeId": "Data",
                    "isExtractingAllIndicatorTypes": True,
                    "extractIndicatorTypesIDs": [],
                },
                "closenotes": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": True,
                    "extractIndicatorTypesIDs": ["Data"],
                },
                "closinguserid": {
                    "extractAsIsIndicatorTypeId": "",
                    "isExtractingAllIndicatorTypes": False,
                    "extractIndicatorTypesIDs": ["IP", "CIDR"],
                },
            },
        }
        incident_type = pack.create_incident_type("incident_type", incident_type_data)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    incident_type.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "IT103",
                    "The `mode` field under `extractSettings` should be one of the following:",
                    ' - "All" - To extract all indicator types regardless of auto-extraction settings.',
                    ' - "Specific" - To extract only the specific indicator types ',
                    "set in the auto-extraction settings.",
                    f"Validating {incident_type.path} as incidenttype",
                ]
            ]
        )
        assert result.exit_code == 1


class TestLayoutValidation:
    DYNAMIC_SECTION_WITH_SCRIPT = {
        "description": "",
        "h": 1,
        "i": "tjlpilelnw-978b0c1e-6739-432d-82d1-3b6641eed99f-tjlpilelnw-978b0c1e-6739-432d-82d1-",
        "items": [],
        "maxW": 3,
        "minH": 1,
        "minW": 1,
        "moved": False,
        "name": "Employment Status",
        "query": "test_script",
        "queryType": "script",
        "static": False,
        "w": 1,
        "x": 0,
        "y": 0,
    }
    BUTTON_ITEM_SECTION_WITH_SCRIPT = {
        "description": "",
        "displayType": "CARD",
        "h": 2,
        "hideItemTitleOnlyOne": False,
        "hideName": False,
        "i": "xvcv8dtmxx-74334ff1-32a3-11eb-8468-67c152ca7f29",
        "items": [
            {
                "args": {"add_or_remove": {"simple": "remove"}},
                "buttonClass": "error",
                "dropEffect": "move",
                "endCol": 2,
                "fieldId": "",
                "height": 44,
                "id": "74334ff0-32a3-11eb-8468-67c152ca7f29",
                "index": 2,
                "listId": "zfkg6snvly-07513a70-3021-11eb-ba8d-510056356597",
                "name": "Disconnect",
                "scriptId": "test_script",
                "sectionItemType": "button",
                "startCol": 0,
            }
        ],
        "maxH": None,
        "maxW": 1,
        "minH": 1,
        "minW": 1,
        "moved": False,
        "name": "Disconnect XSOAR integration from Okta application",
        "static": False,
        "w": 1,
        "x": 0,
        "y": 4,
    }

    def test_valid_layout(self, mocker, repo):
        """
        Given
        - a valid Layout.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a layout.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout = pack._create_json_based(name="layout-name", prefix="", content=LAYOUT)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layout.path} as layout",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_layout__version(self, mocker, repo):
        """
        Given
        - an invalid layout (wrong version).

        When
        - Running validate on it.

        Then
        - Ensure validate fails on - BA100 wrong version error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout_copy = LAYOUT.copy()
        layout_copy["version"] = 2
        layout = pack._create_json_based(
            name="layout-name", prefix="", content=layout_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layout.path} as layout",
                    "BA100",
                    "The version for our files should always be -1, please update the file.",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_invalid_layout__path(self, mocker, repo):
        """
        Given
        - an invalid layout (wrong path).

        When
        - Running validate on it.

        Then
        - Ensure validate fails on - BA100 wrong version error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout_copy = LAYOUT.copy()
        layout_copy["version"] = 2
        layout = pack._create_json_based(
            name="wrongpath", prefix="", content=layout_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "LO102",
                    'layout file name should start with "layout-" prefix.',
                    f"Validating {layout.path} as layout",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_valid_layoutscontainer(self, mocker, repo):
        """
        Given
        - a valid Layout_Container.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a layout.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout = pack._create_json_based(
            name="layoutscontainer-test", prefix="", content=LAYOUTS_CONTAINER
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layout.path} as layoutscontainer",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_layoutscontainer__version(self, mocker, repo):
        """
        Given
        - an invalid Layout_Container (wrong version).

        When
        - Running validate on it.

        Then
        - Ensure validate fails on - BA100 wrong version error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout_copy = LAYOUTS_CONTAINER.copy()
        layout_copy["version"] = 2
        layout = pack._create_json_based(
            name="layoutscontainer", prefix="", content=layout_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layout.path} as layoutscontainer",
                    "BA100",
                    "The version for our files should always be -1, please update the file.",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_invalid_layoutscontainer__path(self, mocker, repo):
        """
        Given
        - an invalid Layout_Container (wrong path).

        When
        - Running validate on it.

        Then
        - Ensure validate fails on - LO103 wrong file path.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout = pack._create_json_based(
            name="wrongname", prefix="", content=LAYOUTS_CONTAINER
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "LO103",
                    'layoutscontainer file name should start with "layoutscontainer-" prefix.',
                    f"Validating {layout.path} as layoutscontainer",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_invalid_from_version_in_layoutscontaier(self, mocker, repo):
        """
        Given
        - Layout_container with invalid from version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layoutscontainer_copy = LAYOUTS_CONTAINER.copy()
        layoutscontainer_copy["fromVersion"] = "5.0.0"

        layoutscontainer = pack._create_json_based(
            name="layoutscontainer", prefix="", content=layoutscontainer_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layoutscontainer.path,
                ],
                catch_exceptions=False,
            )
        assert (
            f"Validating {layoutscontainer.path} as layoutscontainer" in result.output
        )
        assert (
            "fromVersion field in layoutscontainer needs to be higher or equal to 6.0.0"
        ) in result.output

        assert result.exit_code == 1

    def test_invalid_to_version_in_layout(self, mocker, repo):
        """
        Given
        - Layout_container with invalid to version

        When
        - Running validate on it.

        Then
        - Ensure validate found errors.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout_copy = LAYOUT.copy()
        layout_copy["toVersion"] = "6.0.0"

        layout = pack._create_json_based(name="layout", prefix="", content=layout_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {layout.path} as layout" in result.output
        assert "toVersion field in layout needs to be lower than 6.0.0" in result.output
        assert result.exit_code == 1

    @pytest.mark.parametrize(
        "tab_section_to_test",
        [DYNAMIC_SECTION_WITH_SCRIPT, BUTTON_ITEM_SECTION_WITH_SCRIPT],
    )
    def test_valid_scripts_in_layoutscontainer(self, mocker, repo, tab_section_to_test):
        """
        Given
            1. Valid layoutcontainer - with a dynamic section which include a script that exist in the id_set json.
            2. Valid layoutcontainer - with a section which include a button item with a script that exist in the
               id_set json.
        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layoutscontainer_copy = LAYOUTS_CONTAINER.copy()
        layoutscontainer_copy["detailsV2"]["tabs"][0]["sections"] = [
            tab_section_to_test
        ]
        layoutscontainer = pack._create_json_based(
            name="layoutscontainer-test", prefix="", content=layoutscontainer_copy
        )

        id_set = copy.deepcopy(EMPTY_ID_SET)
        id_set["scripts"].append(
            {
                "test_script": {
                    "name": "test_script",
                    "file_path": "Packs/DeveloperTools/TestPlaybooks/test_script.yml",
                    "fromversion": "5.0.0",
                    "pack": "DeveloperTools",
                }
            }
        )
        repo.id_set.write_json(id_set)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layoutscontainer.path,
                    "-s",
                    "-idp",
                    repo.id_set.path,
                    "-pc",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layoutscontainer.path} as layoutscontainer",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        "tab_section_to_test",
        [DYNAMIC_SECTION_WITH_SCRIPT, BUTTON_ITEM_SECTION_WITH_SCRIPT],
    )
    def test_invalid_scripts_in_layoutscontainer(
        self, mocker, repo, tab_section_to_test
    ):
        """
        Given
            1. inValid layoutcontainer - with a dynamic section which include a script that doesn't exist in the
               id_set json.
            2. Valid layoutcontainer - with a section which include a button item with a script that doesn't exist in
               the id_set json.
        When
        - Running validation on it.

        Then
        - Ensure validation fails on LO105 - layouts container non existent script id
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layoutscontainer_copy = LAYOUTS_CONTAINER.copy()
        layoutscontainer_copy["detailsV2"]["tabs"][0]["sections"] = [
            tab_section_to_test
        ]
        layoutscontainer = pack._create_json_based(
            name="layoutscontainer-test", prefix="", content=layoutscontainer_copy
        )

        id_set = copy.deepcopy(EMPTY_ID_SET)
        id_set["scripts"].append(
            {
                "not_test_script": {
                    "name": "test_script",
                    "file_path": "Packs/DeveloperTools/TestPlaybooks/test_script.yml",
                    "fromversion": "5.0.0",
                    "pack": "DeveloperTools",
                }
            }
        )
        repo.id_set.write_json(id_set)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layoutscontainer.path,
                    "-s",
                    "-idp",
                    repo.id_set.path,
                    "-pc",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layoutscontainer.path} as layoutscontainer",
                    "LO105",
                    "the following scripts were not found in the id_set.json",
                ]
            ]
        )
        assert result.exit_code == 1

    @pytest.mark.parametrize(
        "tab_section_to_test",
        [DYNAMIC_SECTION_WITH_SCRIPT, BUTTON_ITEM_SECTION_WITH_SCRIPT],
    )
    def test_valid_scripts_in_layout(self, mocker, repo, tab_section_to_test):
        """
        Given
            1. Valid layout - with a dynamic section which include a script that exist in the id_set json.
            2. Valid layout - with a section which include a button item with a script that exist in the id_set json.

        When
        - Running validation on it.

        Then
        - Ensure validation passes.
        - Ensure success validation message is printed.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout_copy = LAYOUT.copy()
        layout_copy["layout"]["tabs"][0]["sections"] = [tab_section_to_test]
        layout = pack._create_json_based(
            name="layout-test", prefix="", content=layout_copy
        )

        id_set = copy.deepcopy(EMPTY_ID_SET)
        id_set["scripts"].append(
            {
                "test_script": {
                    "name": "test_script",
                    "file_path": "Packs/DeveloperTools/TestPlaybooks/test_script.yml",
                    "fromversion": "5.0.0",
                    "pack": "DeveloperTools",
                }
            }
        )
        repo.id_set.write_json(id_set)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                    "-s",
                    "-idp",
                    repo.id_set.path,
                    "-pc",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layout.path} as layout",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        "tab_section_to_test",
        [DYNAMIC_SECTION_WITH_SCRIPT, BUTTON_ITEM_SECTION_WITH_SCRIPT],
    )
    def test_invalid_scripts_in_layout(self, mocker, repo, tab_section_to_test):
        """
        Given
            1. inValid layout - with a dynamic section which include a script that doesn't exist in the id_set json.
            2. Valid layout - with a section which include a button item with a script that doesn't exist in the id_set
               json.
        When
        - Running validation on it.

        Then
        - Ensure validation fails on LO106 - layout non existent script id
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        layout_copy = LAYOUT.copy()
        layout_copy["layout"]["tabs"][0]["sections"] = [tab_section_to_test]
        layout = pack._create_json_based(
            name="layout-test", prefix="", content=layout_copy
        )

        id_set = copy.deepcopy(EMPTY_ID_SET)
        id_set["scripts"].append(
            {
                "not_test_script": {
                    "name": "test_script",
                    "file_path": "Packs/DeveloperTools/TestPlaybooks/test_script.yml",
                    "fromversion": "5.0.0",
                    "pack": "DeveloperTools",
                }
            }
        )
        repo.id_set.write_json(id_set)

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    layout.path,
                    "-s",
                    "-idp",
                    repo.id_set.path,
                    "-pc",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {layout.path} as layout",
                    "LO106",
                    "the following scripts were not found in the id_set.json",
                ]
            ]
        )
        assert result.exit_code == 1


class TestPlaybookValidation:
    def test_valid_playbook(self, mocker):
        """
        Given
        - a valid Playbook.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a playbook.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(PlaybookValidator, "is_script_id_valid", return_value=True)
        mocker.patch.object(
            ContentEntityValidator, "validate_readme_exists", return_value=True
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                VALID_PLAYBOOK_FILE_PATH,
                "--allow-skipped",
                "--no-conf-json",
            ],
            catch_exceptions=False,
        )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {VALID_PLAYBOOK_FILE_PATH} as playbook",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_playbook(self, mocker):
        """
        Given
        - an invalid Playbook - root task is disconnected from next task.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on PB103 - unconnected tasks error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        with ChangeCWD(TEST_FILES_PATH):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    INVALID_PLAYBOOK_FILE_PATH,
                    "--allow-skipped",
                    "--no-conf-json",
                ],
                catch_exceptions=False,
            )

        assert all(
            current_str in result.output
            for current_str in [
                "PB103",
                "The following tasks ids have no previous tasks: {'5'}",
                f"Validating {INVALID_PLAYBOOK_FILE_PATH} as playbook",
            ]
        )
        assert result.exit_code == 1


class TestPlaybookValidateDeprecated:
    def test_valid_deprecated_playbook(self, mocker, repo):
        """
        Given
        - a valid Playbook Deprecated.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a playbook deprecated.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(PlaybookValidator, "is_script_id_valid", return_value=True)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                VALID_DEPRECATED_PLAYBOOK_FILE_PATH,
                "--no-conf-json",
                "--allow-skipped",
            ],
            catch_exceptions=False,
        )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {VALID_DEPRECATED_PLAYBOOK_FILE_PATH} as playbook",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_deprecated_playbook(self, mocker):
        """
        Given
        - an invalid Playbook - there is no Deprecated. in the description.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on PB104 - deprecated tasks error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        with ChangeCWD(TEST_FILES_PATH):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    INVALID_DEPRECATED_PLAYBOOK_FILE_PATH,
                    "--no-conf-json",
                    "--allow-skipped",
                ],
                catch_exceptions=False,
            )
        assert all(
            current_str in result.output
            for current_str in [
                "PB104",
                "Deprecated.",
                f"Validating {INVALID_DEPRECATED_PLAYBOOK_FILE_PATH} as playbook",
            ]
        )
        assert result.exit_code == 1

    def test_invalid_bc_deprecated_playbook(self, mocker, repo):
        """
        Given
        - an invalid, backwards compatible Playbook Deprecated. All deprecated fields are set correctly.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a playbook deprecated.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(PlaybookValidator, "is_script_id_valid", return_value=True)
        pack = repo.create_pack("PackName")
        valid_playbook_yml = get_yaml(VALID_DEPRECATED_PLAYBOOK_FILE_PATH)
        valid_playbook_yml["hidden"] = True
        valid_playbook_yml["version"] = -2
        playbook = pack.create_playbook(yml=valid_playbook_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    playbook.yml.rel_path,
                    "--print-ignored-files",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{playbook.yml.rel_path} as playbook",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_modified_invalid_bc_deprecated_playbook(self, mocker, repo):
        """
        Given
        - A modified invalid, backwards compatible Playbook Deprecated. All deprecated fields are set correctly.

        When
        - Running validate -g on it.

        Then
        - Ensure validate passes and identifies the file as a playbook deprecated.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(PlaybookValidator, "is_script_id_valid", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        pack = repo.create_pack("PackName")
        valid_playbook_yml = get_yaml(VALID_DEPRECATED_PLAYBOOK_FILE_PATH)
        valid_playbook_yml["hidden"] = True
        valid_playbook_yml["version"] = -2
        playbook = pack.create_playbook(yml=valid_playbook_yml)
        modified_files = {playbook.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, {}, set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--print-ignored-files",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {playbook.yml.rel_path} as playbook",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_bc_unsupported_toversion_playbook(self, mocker, repo):
        """
        Given
        - an invalid, backwards compatible deprecated playbook with toversion < OLDEST_SUPPORTED_VERSION.
        - All deprecated fields are set correctly.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a playbook deprecated.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(PlaybookValidator, "is_script_id_valid", return_value=True)
        pack = repo.create_pack("PackName")
        valid_playbook_yml = get_yaml(VALID_DEPRECATED_PLAYBOOK_FILE_PATH)
        valid_playbook_yml["toversion"] = "4.4.4"
        valid_playbook_yml["version"] = -2
        playbook = pack.create_playbook(yml=valid_playbook_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    playbook.yml.rel_path,
                    "--print-ignored-files",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{playbook.yml.rel_path} as playbook",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_modified_invalid_bc_unsupported_toversion_playbook(self, mocker, repo):
        """
        Given
        - A modified invalid, backwards compatible deprecated playbook with toversion < OLDEST_SUPPORTED_VERSION.
        - All deprecated fields are set correctly.

        When
        - Running validate -g on it.

        Then
        - Ensure validate passes and identifies the file as a playbook deprecated.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(PlaybookValidator, "is_script_id_valid", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        pack = repo.create_pack("PackName")
        valid_playbook_yml = get_yaml(VALID_DEPRECATED_PLAYBOOK_FILE_PATH)
        valid_playbook_yml["toversion"] = "4.4.4"
        valid_playbook_yml["version"] = -2
        playbook = pack.create_playbook(yml=valid_playbook_yml)
        modified_files = {playbook.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, {}, set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--print-ignored-files",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {playbook.yml.rel_path} as playbook",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0


class TestReportValidation:
    def test_valid_report(self, mocker, repo):
        """
        Given
        - a valid Report.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a report.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        report = pack._create_json_based(name="report", prefix="", content=REPORT)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    report.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {report.path} as report",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_report(self, mocker, repo):
        """
        Given
        - an invalid Report - illegal value in orientation field.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on wrong orientation value.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        report_copy = REPORT.copy()
        report_copy["orientation"] = "bla"
        report = pack._create_json_based(name="report", prefix="", content=report_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    report.path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {report.path} as report" in result.output
        assert "The value \"bla\" in 'orientation' is invalid" in result.output
        assert result.exit_code == 1


class TestReputationValidation:
    def test_valid_reputation(self, mocker, repo):
        """
        Given
        - a valid Reputation.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a reputation.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        reputation = pack._create_json_based(
            name="reputation", prefix="", content=REPUTATION
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    reputation.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {reputation.path} as reputation",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_reputation(self, mocker, repo):
        """
        Given
        - an invalid Reputation - negative integer in expiration field.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on RP101 - wrong value in expiration field.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        reputation_copy = REPUTATION.copy()
        reputation_copy["expiration"] = -1
        reputation = pack._create_json_based(
            name="reputation", prefix="", content=reputation_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    reputation.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            current_str in result.output
            for current_str in [
                "RP101",
                "Expiration field should have a positive numeric value.",
                f"Validating {reputation.path} as reputation",
            ]
        )
        assert result.exit_code == 1


class TestScriptValidation:
    def test_valid_script(self, mocker, repo):
        """
        Given
        - a valid Script.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        valid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        script = pack.create_script(yml=valid_script_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{script.yml.rel_path} as script",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_script(self, mocker, repo):
        """
        Given
        - an invalid Script - v2 in name instead  of V2.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on SC100 wrong v2 format in name.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        invalid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        invalid_script_yml["name"] = invalid_script_yml["name"] + "_v2"
        script = pack.create_script(yml=invalid_script_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "SC100",
                    "The name of this v2 script is incorrect",
                    f"{script.yml.rel_path} as script",
                ]
            ]
        )
        assert result.exit_code == 1


class TestScriptDeprecatedValidation:
    def test_valid_deprecated_script(self, mocker, repo):
        """
        Given
        - a valid deprecated Script.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a deprecated script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        valid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        valid_script_yml["deprecated"] = True
        valid_script_yml["comment"] = (
            "Deprecated. Use the EntryWidgetNumberHostsXDR v2 script instead."
        )
        script = pack.create_script(yml=valid_script_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{script.yml.rel_path} as script",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_deprecated_script(self, mocker, repo):
        """
        Given
        - an invalid deprecated Script without Deprecated. in the description.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on SC101 wrong deprecated script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        invalid_script_yml = get_yaml(VALID_SCRIPT_PATH, cache_clear=True)
        invalid_script_yml["deprecated"] = True
        script = pack.create_script(yml=invalid_script_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            current_str in result.output
            for current_str in [
                "SC101",
                "Deprecated.",
                f"{script.yml.rel_path} as script",
            ]
        )
        assert result.exit_code == 1

    def test_invalid_bc_deprecated_script(self, mocker, repo):
        """
        Given
        - an invalid but backwards compatible deprecated Script. All deprecated fields are set correctly.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a deprecated script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        valid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        valid_script_yml["deprecated"] = True
        valid_script_yml["commonfields"]["version"] = -2
        valid_script_yml["comment"] = (
            "Deprecated. Use the EntryWidgetNumberHostsXDR v2 script instead."
        )
        script = pack.create_script(yml=valid_script_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                    "--print-ignored-files",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{script.yml.rel_path} as script",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_modified_invalid_bc_deprecated_script(self, mocker, repo):
        """
        Given
        - A modified invalid but backwards compatible deprecated Script. All deprecated fields are set correctly.

        When
        - Running validate -g on it.

        Then
        - Ensure validate passes and identifies the file as a deprecated script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        pack = repo.create_pack("PackName")
        valid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        valid_script_yml["deprecated"] = True
        valid_script_yml["commonfields"]["version"] = -2
        valid_script_yml["comment"] = (
            "Deprecated. Use the EntryWidgetNumberHostsXDR v2 script instead."
        )
        script = pack.create_script(yml=valid_script_yml)
        modified_files = {script.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, {}, set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                    "--print-ignored-files",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {script.yml.rel_path} as script",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_bc_unsupported_toversion_script(self, mocker, repo):
        """
        Given
        - An invalid but backwards compatible Script with field toversion < OLDEST_SUPPORTED_VERSION.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        valid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        valid_script_yml["toversion"] = "4.4.4"
        valid_script_yml["commonfields"]["version"] = -2
        script = pack.create_script(yml=valid_script_yml)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    script.yml.rel_path,
                    "--no-docker-checks",
                    "--print-ignored-files",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"{script.yml.rel_path} as script",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_modified_invalid_bc_unsupported_toversion_script(self, mocker, repo):
        """
        Given
        - A modified invalid but backwards compatible Script with field toversion < OLDEST_SUPPORTED_VERSION.

        When
        - Running validate -g on it.

        Then
        - Ensure validate passes and identifies the file as a script.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        pack = repo.create_pack("PackName")
        valid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        valid_script_yml["toversion"] = "4.4.4"
        valid_script_yml["commonfields"]["version"] = -2
        script = pack.create_script(yml=valid_script_yml)
        modified_files = {script.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, {}, set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-g",
                    "--no-docker-checks",
                    "--print-ignored-files",
                    "--skip-pack-release-notes",
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {script.yml.rel_path} as script",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0


class TestWidgetValidation:
    def test_valid_widget(self, mocker, repo):
        """
        Given
        - a valid Widget.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as a widget.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        widget = pack._create_json_based(name="widget", prefix="", content=WIDGET)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    widget.path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {widget.path} as widget",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_widget(self, mocker, repo):
        """
        Given
        - an invalid widget (wrong version).

        When
        - Running validate on it.

        Then
        - Ensure validate fails on - BA100 wrong version error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        widget_copy = WIDGET.copy()
        widget_copy["version"] = 1
        widget = pack._create_json_based(name="widget", prefix="", content=widget_copy)
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    widget.path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {widget.path} as widget",
                    "BA100",
                ]
            ]
        )
        assert (
            "The version for our files should always be -1, please update the file."
            in result.output
        )
        assert result.exit_code == 1


class TestImageValidation:
    def test_valid_image(self, mocker, repo):
        """
        Given
        - a valid Image.

        When
        - Running validate on it.

        Then
        - Ensure validate passes and identifies the file as an image.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        integration = pack.create_integration()
        image_path = integration.image.path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    image_path,
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {image_path} as image",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_invalid_image(self, mocker, repo):
        """
        Given
        - The default image.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on error IM106 - default image error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        integration = pack.create_integration()
        image_path = integration.image.path
        mocker.patch.object(
            ImageValidator, "load_image", return_value=DEFAULT_IMAGE_BASE64
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    image_path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {image_path} as image" in result.output

        assert all(
            [
                current_str in result.output
                for current_str in [
                    "IM106",
                    "This is the default image, please change to the integration image.",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_image_should_not_be_validated(self, mocker, repo):
        """
        Given
        - The image file which path does not end with _image.

        When
        - Running validate on it.

        Then
        - Ensure validate does not validates it as an image.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack = repo.create_pack("PackName")
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    NOT_VALID_IMAGE_PATH,
                ],
                catch_exceptions=False,
            )
        assert "The image file name or location is invalid" in result.output
        assert result.exit_code == 1

    def test_invalid_image_size(self, repo, mocker):
        """
        Given
        - An image with bad dimensions and bad size.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on dimensions error and asks to change the image.
        """

        pack = repo.create_pack("PackName")
        with open(
            f"{git_path()}/demisto_sdk/tests/integration_tests/Tests/invalid_integration_image.png",
            "rb",
        ) as f:
            image = f.read()
        integration = pack.create_integration(image=image)
        image_path = integration.image.path
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    image_path,
                ],
                catch_exceptions=False,
            )
        assert f"Validating {image_path} as image" in result.output
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "IM111",
                    "IM101",
                    "120x50",
                    "10kB",
                ]
            ]
        )
        assert result.exit_code == 1


class TestAuthorImageValidation:
    def test_author_image_valid(self, repo, mocker):
        """
        Given
        - A valid author image image.

        When
        - Running validate on it.

        Then
        - Ensure validate passes.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        pack.pack_metadata.write_json(
            {
                "name": "PackName",
                "description": "This pack.",
                "support": "xsoar",
                "currentVersion": "1.0.1",
                "author": "Cortex XSOAR",
                "url": "https://www.paloaltonetworks.com/cortex",
                "email": "",
                "created": "2021-06-07T07:45:21Z",
                "categories": [],
                "tags": [],
                "useCases": [],
                "keywords": [],
            }
        )
        pack.author_image.write(DEFAULT_IMAGE_BASE64)

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    pack.author_image.path,
                ],
                catch_exceptions=False,
            )

        assert f"Validating {pack.author_image.path} as author_image" in result.output
        assert result.exit_code == 0

    def test_author_image_invalid(self, repo, mocker):
        """
        Given
        - An empty author image.

        When
        - Running validate on it.

        Then
        - Ensure validate fails on error IM108 - empty author image error.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(ImageValidator, "load_image", return_value="")
        pack = repo.create_pack("PackName")
        pack.pack_metadata.write_json(
            {
                "name": "PackName",
                "description": "This pack.",
                "support": "partner",
                "currentVersion": "1.0.1",
                "author": "Cortex XSOAR",
                "url": "https://www.paloaltonetworks.com/cortex",
                "email": "",
                "created": "2021-06-07T07:45:21Z",
                "categories": [],
                "tags": [],
                "useCases": [],
                "keywords": [],
            }
        )
        pack.author_image.write("")
        author_image_path = pack.author_image.path
        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    author_image_path,
                ],
                catch_exceptions=False,
            )

        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {author_image_path} as author_image",
                    "IM108",
                ]
            ]
        )
        assert result.exit_code == 1


class TestAllFilesValidator:
    def test_all_files_valid(self, mocker, repo):
        """
        Given
        - A valid repo.

        When
        - Running validate on it.

        Then
        - Ensure validate passes on all files.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "validate_readme", return_value=True)
        mocker.patch.object(ImageValidator, "validate_size", return_value=True)
        mocker.patch.object(OldValidateManager, "is_node_exist", return_value=True)
        mocker.patch(
            "demisto_sdk.commands.common.hook_validations.integration.tools.get_current_categories",
            return_value=["Data Enrichment & Threat Intelligence"],
        )
        pack1 = repo.create_pack("PackName1")
        pack1.author_image.write(DEFAULT_IMAGE_BASE64)
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        integration = pack1.create_integration(
            "integration0", yml=valid_integration_yml
        )
        incident_field = pack1.create_incident_field(
            "incident-field", content=INCIDENT_FIELD
        )
        dashboard = pack1.create_dashboard("dashboard", content=DASHBOARD)

        valid_script_yml = get_yaml(VALID_SCRIPT_PATH, cache_clear=True)
        pack2 = repo.create_pack("PackName2")
        pack2.author_image.write(DEFAULT_IMAGE_BASE64)
        script = pack2.create_script(yml=valid_script_yml)

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-a",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--no-multiprocessing",
                ],
                catch_exceptions=False,
            )
            print(result.stdout)  # noqa: T201

        assert all(
            [
                current_str in result.output
                for current_str in [
                    "Validating all files",
                    "Validating Packs/PackName1 unique pack files",
                    "Validating Packs/PackName2 unique pack files",
                    f"Validating {integration.yml.rel_path} as integration",
                    f"Validating {incident_field.get_path_from_pack()} as incidentfield",
                    f"Validating {dashboard.get_path_from_pack()} as dashboard",
                    f"Validating {script.yml.rel_path} as script",
                    "Validating pack author image",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_not_all_files_valid(self, mocker, repo):
        """
        Given
        - An invalid repo.

        When
        - Running validate on it.

        Then
        - Ensure validate fails.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "validate_readme", return_value=True)
        mocker.patch.object(OldValidateManager, "is_node_exist", return_value=False)
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack1 = repo.create_pack("PackName1")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        integration = pack1.create_integration(yml=valid_integration_yml)
        incident_field_copy = INCIDENT_FIELD.copy()
        incident_field_copy["content"] = False
        incident_field = pack1.create_incident_field(
            "incident-field", content=incident_field_copy
        )
        dashboard = pack1.create_dashboard("dashboard", content=DASHBOARD)

        invalid_script_yml = get_yaml(VALID_SCRIPT_PATH, cache_clear=True)
        invalid_script_yml["name"] = invalid_script_yml["name"] + "_v2"
        pack2 = repo.create_pack("PackName2")
        script = pack2.create_script(yml=invalid_script_yml)
        mocker.patch.object(ReadMeValidator, "is_docker_available", return_value=False)

        with ChangeCWD(repo.path):
            result = CliRunner(mix_stderr=False).invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-a",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--no-multiprocessing",
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert all(
            current_str in result.output
            for current_str in [
                "Validating all files",
                "Validating Packs/PackName1 unique pack files",
                "Validating Packs/PackName2 unique pack files",
                f"Validating {integration.yml.rel_path} as integration",
                f"Validating {incident_field.get_path_from_pack()} as incidentfield",
                f"Validating {dashboard.get_path_from_pack()} as dashboard",
                f"Validating {script.yml.rel_path} as script",
                "Validating pack author image",
                "IF101",
                "SC100",
                "RM111",
                "The content key must be set to True.",
                "The name of this v2 script is incorrect",
            ]
        )


class TestValidationUsingGit:
    def test_passing_validation_using_git(self, mocker, repo):
        """
        Given
        - A valid repo.

        When
        - Running validate using git on it.

        Then
        - Ensure validate passes on all files.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        pack1 = repo.create_pack("PackName1")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path, cache_clear=True)
        integration = pack1.create_integration(
            "integration0", yml=valid_integration_yml
        )
        integration.readme.write("azure-get-indicators\nazure-hidden-command")
        incident_field = pack1.create_incident_field(
            "incident-field", content=INCIDENT_FIELD
        )
        dashboard = pack1.create_dashboard("dashboard", content=DASHBOARD)

        valid_script_yml = get_yaml(VALID_SCRIPT_PATH, cache_clear=True)
        pack2 = repo.create_pack("PackName2")
        script = pack2.create_script(yml=valid_script_yml)

        old_integration = pack2.create_integration(
            name="OldIntegration", description="Deprecated. No available replacement."
        )
        old_integration.yml.update(
            {
                "display": "OldIntegration (Deprecated)",
                "toversion": "5.0.0",
                "deprecated": True,
            }
        )

        modified_files = {integration.yml.rel_path, incident_field.get_path_from_pack()}
        added_files = {dashboard.get_path_from_pack(), script.yml.rel_path}
        old_files = {old_integration.yml.rel_path}
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, added_files, set(), old_files, True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "Running validation on branch",
                    "Running validation on modified files",
                    "Running validation on newly added files",
                    "Running validation on changed pack unique files",
                    "Validating ./Packs/PackName1 unique pack files",
                    "Validating ./Packs/PackName2 unique pack files",
                    f"Validating {integration.yml.rel_path} as integration",
                    f"Validating {incident_field.get_path_from_pack()} as incidentfield",
                    f"Validating {dashboard.get_path_from_pack()} as dashboard",
                    f"Validating {script.yml.rel_path} as script",
                    f"Validating old-format file {old_integration.yml.rel_path}",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_failing_validation_using_git(self, mocker, repo):
        """
        Given
        - An invalid repo.

        When
        - Running validate using git on it.

        Then
        - Ensure validate fails.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        pack1 = repo.create_pack("PackName1")
        pack_integration_path = join(
            AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml"
        )
        valid_integration_yml = get_yaml(pack_integration_path)
        integration = pack1.create_integration(yml=valid_integration_yml)
        incident_field_copy = INCIDENT_FIELD.copy()
        incident_field_copy["content"] = False
        incident_field = pack1.create_incident_field(
            "incident-field", content=incident_field_copy
        )
        dashboard = pack1.create_dashboard("dashboard", content=DASHBOARD)

        invalid_script_yml = get_yaml(VALID_SCRIPT_PATH)
        invalid_script_yml["name"] = invalid_script_yml["name"] + "_v2"
        pack2 = repo.create_pack("PackName2")
        script = pack2.create_script(yml=invalid_script_yml)

        modified_files = {integration.yml.rel_path, incident_field.get_path_from_pack()}
        added_files = {dashboard.get_path_from_pack(), script.yml.rel_path}
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, added_files, set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )

        assert all(
            current_str in result.output
            for current_str in [
                "Running validation on branch",
                "Running validation on modified files",
                "Running validation on newly added files",
                "Running validation on changed pack unique files",
                "Validating ./Packs/PackName1 unique pack files",
                "Validating ./Packs/PackName2 unique pack files",
                f"Validating {integration.yml.rel_path} as integration",
                f"Validating {incident_field.get_path_from_pack()} as incidentfield",
                f"Validating {dashboard.get_path_from_pack()} as dashboard",
                f"Validating {script.yml.rel_path} as script",
                "IF101",
                "SC100",
            ]
        )
        assert all(
            err_msg in result.output
            for err_msg in [
                "The name of this v2 script is incorrect",
                "The content key must be set to True.",
            ]
        )
        assert result.exit_code == 1

    def test_validation_using_git_without_pack_dependencies(self, mocker, repo):
        """
        Given
        - An invalid repo.

        When
        - Running validate using git on it with --skip-pack-dependencies flag.

        Then
        - Ensure validate fails.
        - Ensure pack dependencies check doesnt happen.
        """

        pack = repo.create_pack("FeedAzure")
        integration = pack.create_integration(
            name="FeedAzure",
            yml=get_yaml(
                join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml")
            ),
        )
        modified_files = {integration.yml.rel_path}
        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(
            BaseValidator, "update_checked_flags_by_support_level", return_value=None
        )
        mocker.patch.object(
            PackUniqueFilesValidator, "validate_pack_meta_file", return_value=True
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                    "--skip-pack-dependencies",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "Running validation on branch",
                    "Running validation on modified files",
                    "Running validation on newly added files",
                    "Running validation on changed pack unique files",
                    "Validating ./Packs/FeedAzure unique pack files",
                ]
            ]
        )
        assert "Running pack dependencies validation on" not in result.output
        assert result.exit_code == 1

    def test_validation_using_git_with_pack_dependencies(self, mocker, repo):
        """
        Given
        - An invalid repo.

        When
        - Running validate using git on it with --skip-pack-dependencies flag.

        Then
        - Ensure validate fails.
        - Ensure pack dependencies check happens.
        """

        pack = repo.create_pack("FeedAzure")
        integration = pack.create_integration(
            name="FeedAzure",
            yml=get_yaml(
                join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml")
            ),
        )
        modified_files = {integration.yml.rel_path}
        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        mocker.patch.object(PackDependencies, "find_dependencies", return_value={})
        mocker.patch.object(
            PackUniqueFilesValidator, "validate_pack_meta_file", return_value=True
        )
        mocker.patch.object(
            BaseValidator, "update_checked_flags_by_support_level", return_value=None
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "Running pack dependencies validation on",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_validation_non_content_path(self):
        """
        Given
        - non-content pack path file, file not existing.

        When
        - Running demisto-sdk validate command.

        Then
        - Ensure an error is raised on the non found file
        """
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                VALIDATE_CMD,
                "--run-old-validate",
                "--skip-new-validate",
                "-i",
                join("Users", "MyPacks", "VMware"),
                "--no-docker-checks",
                "--no-conf-json",
                "--skip-pack-release-notes",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 2
        assert result.exception
        assert "does not exist" in result.stderr  # check error str is in stdout

    def test_validation_non_content_path_mocked_repo(self, mocker, repo):
        """
        Given
        - non-content pack path file, file existing.

        When
        - Running demisto-sdk validate command.
        - mocking the 'get_modified_and_added_files' for a FileNotFoundError error

        Then
        - Ensure an error is raised on the non found file
        """

        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(PackDependencies, "find_dependencies", return_value={})
        mocker.patch.object(
            PackUniqueFilesValidator, "validate_pack_meta_file", return_value=True
        )
        mocker.patch.object(
            BaseValidator, "update_checked_flags_by_support_level", return_value=None
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            side_effect=FileNotFoundError,
        )
        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 1
        assert "You may not be running" in result.output

    def test_validation_using_git_on_specific_file(self, mocker, repo):
        """
        Given
        - A repo with a pack with a modified integration and script.

        When
        - Running validate using git on it with -i flag aiming at the integration yml path specifically.

        Then
        - Ensure the integration is validated.
        - Ensure the script is not validated.
        """

        pack = repo.create_pack("FeedAzure")
        integration = pack.create_integration()
        integration.create_default_integration()
        script = pack.create_script()
        script.create_default_script()

        modified_files = {integration.yml.rel_path, script.yml.rel_path}
        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        mocker.patch.object(PackDependencies, "find_dependencies", return_value={})
        mocker.patch.object(
            PackUniqueFilesValidator, "validate_pack_meta_file", return_value=True
        )
        mocker.patch.object(
            BaseValidator, "update_checked_flags_by_support_level", return_value=None
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                    "-i",
                    integration.yml.rel_path,
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    "Running on committed and staged files",
                    f"Validating {integration.yml.rel_path}",
                ]
            ]
        )
        assert f"Validating {script.yml.rel_path}" not in result.output

    def test_validation_using_git_on_specific_file_renamed(self, mocker, repo):
        """
        Given
        - A repo with a pack with a renamed integration and modified script.

        When
        - Running validate using git on it with -i flag aiming at the integration yml path specifically.

        Then
        - Ensure the integration is validated.
        - Ensure the script is not validated.
        """

        pack = repo.create_pack("FeedAzure")
        integration = pack.create_integration()
        integration.create_default_integration()
        script = pack.create_script()
        script.create_default_script()

        modified_files = {
            (integration.yml.rel_path, integration.yml.rel_path),
            script.yml.rel_path,
        }
        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        mocker.patch.object(PackDependencies, "find_dependencies", return_value={})
        mocker.patch.object(
            PackUniqueFilesValidator, "validate_pack_meta_file", return_value=True
        )
        mocker.patch.object(
            BaseValidator, "update_checked_flags_by_support_level", return_value=None
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                    "-i",
                    integration.yml.rel_path,
                ],
                catch_exceptions=False,
            )
        assert "Running on committed and staged files" in result.output
        assert f"Validating {integration.yml.rel_path}" in result.output
        assert f"Validating {script.yml.rel_path}" not in result.output

    def test_validation_using_git_on_specific_pack(self, mocker, repo):
        """
        Given
        - A repo with two packs.

        When
        - Running validate using git on it with -i flag aiming at the pack_1 path specifically.

        Then
        - Ensure the entities in pack 1 are validated
        - Ensure the entities in pack 2 are not validated.
        """

        pack_1 = repo.create_pack("Pack1")
        integration = pack_1.create_integration()
        integration.create_default_integration()
        script = pack_1.create_script()
        script.create_default_script()

        pack_2 = repo.create_pack("Pack2")
        integration_2 = pack_2.create_integration()
        integration_2.create_default_integration()
        script_2 = pack_2.create_script()
        script_2.create_default_script()

        modified_files = {
            (integration.yml.rel_path, integration.yml.rel_path),
            script.yml.rel_path,
            integration_2.yml.rel_path,
            script_2.yml.rel_path,
        }
        mocker.patch.object(tools, "is_external_repository", return_value=False)
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )
        mocker.patch.object(
            IntegrationValidator, "is_valid_category", return_value=True
        )

        mocker.patch.object(PackDependencies, "find_dependencies", return_value={})
        mocker.patch.object(
            PackUniqueFilesValidator, "validate_pack_meta_file", return_value=True
        )
        mocker.patch.object(
            BaseValidator, "update_checked_flags_by_support_level", return_value=None
        )
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(repo.path):
            result = CliRunner(mix_stderr=False).invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--no-docker-checks",
                    "--no-conf-json",
                    "--skip-pack-release-notes",
                    "-i",
                    str(pack_1.path),
                ],
                catch_exceptions=False,
            )
        assert "Running on committed and staged files" in result.output
        assert f"Validating {integration.yml.rel_path}" in result.output
        assert f"Validating {script.yml.rel_path}" in result.output
        assert f"Validating {integration_2.yml.rel_path}" not in result.output
        assert f"Validating {script_2.yml.rel_path}" not in result.output


class TestSpecificValidations:
    def test_validate_with_different_specific_validation(self, mocker, repo):
        """
        Given
        - an invalid Reputation - negative integer in expiration field.

        When
        - Running validate on it with flag --run-specific-validations BA101.

        Then
        - Ensure validate doesn't fail on RP101 - wrong value in expiration field
        due to the flag.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        reputation_copy = REPUTATION.copy()
        reputation_copy["expiration"] = -1
        reputation = pack._create_json_based(
            name="reputation", prefix="", content=reputation_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    reputation.path,
                    "--run-specific-validations",
                    "BA101",
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {reputation.path} as reputation",
                    "The files are valid",
                ]
            ]
        )
        assert result.exit_code == 0

    def test_validate_with_flag_specific_validation(self, mocker, repo):
        """
        Given
        - an invalid Reputation - negative integer in expiration field and a 'details' that does not match its id.

        When
        - Running validate on it with flag --run-specific-validations RP101.

        Then
        - Ensure validate fails on RP101 - wrong value in expiration field and not on RP102 - id and details fields are not equal.
        """
        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        reputation_copy = REPUTATION.copy()
        reputation_copy["expiration"] = -1
        reputation_copy["details"] = "reputationn"
        reputation = pack._create_json_based(
            name="reputation", prefix="", content=reputation_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "-i",
                    reputation.path,
                    "--run-specific-validations",
                    "RP101",
                    "--run-old-validate",
                    "--skip-new-validate",
                ],
                catch_exceptions=False,
            )
        assert all(
            [
                current_str in result.output
                for current_str in [
                    f"Validating {reputation.path} as reputation",
                    "RP101",
                    "Expiration field should have a positive numeric value.",
                ]
            ]
        )
        assert result.exit_code == 1

    def test_validate_with_flag_specific_validation_entire_code_section(
        self, mocker, repo
    ):
        """
        Given
        - an invalid Reputation - negative integer in expiration field and a 'details' that does not match its id.

        When
        - Running validate on it with flag --run-specific-validations RP.

        Then
        - Ensure validate fails on RP101 - wrong value in expiration field and on RP102 - id and details fields are not equal.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        pack = repo.create_pack("PackName")
        reputation_copy = REPUTATION.copy()
        reputation_copy["expiration"] = -1
        reputation_copy["details"] = "reputationn"
        reputation = pack._create_json_based(
            name="reputation", prefix="", content=reputation_copy
        )
        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-i",
                    reputation.path,
                    "--run-specific-validations",
                    "RP",
                ],
                catch_exceptions=False,
            )
            assert f"Validating {reputation.path} as reputation" in result.output
            assert "RP101" in result.output
            assert (
                "Expiration field should have a positive numeric value."
                in result.output
            )
            assert "RP102" in result.output
            assert "id and details fields are not equal." in result.output
            assert result.exit_code == 1


class TestBasicValidation:
    def test_modified_pack_files_with_ignored_validations(self, mocker, repo):
        """
        Given
        - .pack-ignore which ignores IN122 and RM110
        - integration yml which validations above fail.
        - detected modified files that the pack name was changed.

        When
        - running validations with -g flag

        Then
        - make sure the files are valid and that the errors can be ignored successfully.
        """

        mocker.patch.object(tools, "is_external_repository", return_value=True)
        mocker.patch.object(BaseValidator, "check_file_flags", return_value="")
        mocker.patch.object(
            PackUniqueFilesValidator, "are_valid_files", return_value=""
        )
        mocker.patch.object(OldValidateManager, "setup_git_params", return_value=True)
        mocker.patch.object(
            OldValidateManager, "setup_prev_ver", return_value="origin/master"
        )

        pack = repo.create_pack("PackName")

        integration = pack.create_integration(
            "IntegrationTest",
            yml=get_yaml(
                join(AZURE_FEED_PACK_PATH, "Integrations/FeedAzure/FeedAzure.yml")
            ),
        )
        # add ignored validations to .pack-ignore
        pack.pack_ignore.write_list(
            [
                "[file:IntegrationTest.yml]\nignore=IN122,RM110",
            ]
        )

        modified_files = {integration.yml.rel_path}
        mocker.patch.object(
            OldValidateManager,
            "get_changed_files_from_git",
            return_value=(modified_files, set(), set(), set(), True),
        )
        mocker.patch.object(
            GitUtil, "get_current_working_branch", return_value="MyBranch"
        )

        mocker.patch.object(GitUtil, "deleted_files", return_value={})

        with ChangeCWD(pack.repo_path):
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                app,
                [
                    VALIDATE_CMD,
                    "--run-old-validate",
                    "--skip-new-validate",
                    "-g",
                    "--post-commit",
                    "--skip-pack-release-notes",
                    "--no-docker-checks",
                    "--no-conf-json",
                ],
            )
        assert "The files are valid" in result.output
        assert result.exit_code == 0


def test_local_node_server_up_and_down():
    """
    Given:
        - node dependencies installed
        - a valid file for mdx
    When:
        starting a local server with an mdx server
    Then:
        - The server is started successfully.
        - The call is successful.
    """

    assert not mdx_server_is_up()
    with start_local_MDX_server():
        assert mdx_server_is_up()
        assert_successful_mdx_call()
    sleep(1)
    assert not mdx_server_is_up()


def assert_successful_mdx_call():
    session = requests.Session()
    retry = Retry(total=2)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    response = session.request(
        "POST", "http://localhost:6161", data="## Hello", timeout=20
    )
    assert response.status_code == 200
