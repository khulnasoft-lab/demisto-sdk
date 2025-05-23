from functools import cached_property
from pathlib import Path
from typing import List, Optional, Set

from demisto_sdk.commands.common.constants import MarketplaceVersions
from demisto_sdk.commands.content_graph.common import ContentType
from demisto_sdk.commands.content_graph.parsers.json_content_item import (
    JSONContentItemParser,
)
from demisto_sdk.commands.content_graph.strict_objects.incident_type import (
    StrictIncidentType,
)


class IncidentTypeParser(JSONContentItemParser, content_type=ContentType.INCIDENT_TYPE):
    def __init__(
        self,
        path: Path,
        pack_marketplaces: List[MarketplaceVersions],
        pack_supported_modules: List[str],
        git_sha: Optional[str] = None,
    ) -> None:
        super().__init__(
            path, pack_marketplaces, pack_supported_modules, git_sha=git_sha
        )
        self.playbook = self.json_data.get("playbookId") or ""
        self.hours = self.json_data.get("hours")
        self.days = self.json_data.get("days")
        self.weeks = self.json_data.get("weeks")
        self.closure_script = self.json_data.get("closureScript", "")

        self.connect_to_dependencies()

    @property
    def supported_marketplaces(self) -> Set[MarketplaceVersions]:
        return {
            MarketplaceVersions.XSOAR,
            MarketplaceVersions.MarketplaceV2,
            MarketplaceVersions.XPANSE,
            MarketplaceVersions.XSOAR_SAAS,
            MarketplaceVersions.XSOAR_ON_PREM,
            MarketplaceVersions.PLATFORM,
        }

    def connect_to_dependencies(self) -> None:
        """Collects the script, playbook and layout used by the incident type as mandatory dependencies."""
        if pre_processing_script := self.json_data.get("preProcessingScript"):
            self.add_dependency_by_id(pre_processing_script, ContentType.SCRIPT)

        if playbook := self.json_data.get("playbookId"):
            self.add_dependency_by_id(playbook, ContentType.PLAYBOOK)

        if layout := self.json_data.get("layout"):
            self.add_dependency_by_id(layout, ContentType.LAYOUT, is_mandatory=False)

    @cached_property
    def field_mapping(self):
        super().field_mapping.update({"extractSettings": "extractSettings"})
        return super().field_mapping

    @property
    def data_dict(self) -> dict:
        return self.json_data

    @property
    def extract_settings(self) -> dict:
        return self.json_data.get("extractSettings", {})

    @property
    def strict_object(self):
        return StrictIncidentType
