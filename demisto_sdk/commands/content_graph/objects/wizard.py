from pathlib import Path
from typing import List, Optional, Set

from pydantic import DirectoryPath

from demisto_sdk.commands.common.constants import MarketplaceVersions
from demisto_sdk.commands.common.handlers import JSON_Handler
from demisto_sdk.commands.common.logger import logger
from demisto_sdk.commands.content_graph.common import ContentType
from demisto_sdk.commands.content_graph.objects.content_item import ContentItem

json = JSON_Handler()


class Wizard(ContentItem, content_type=ContentType.WIZARD):  # type: ignore[call-arg]
    dependency_packs: str
    packs: List[str]
    integrations: List[str]
    playbooks: List[str]
    version: Optional[int] = 0

    def metadata_fields(self) -> Set[str]:
        return (
            super()
            .metadata_fields()
            .union(
                {
                    "dependency_packs",
                }
            )
        )

    def summary(
        self,
        marketplace: Optional[MarketplaceVersions] = None,
        incident_to_alert: bool = False,
    ) -> dict:
        summary_res = super().summary(marketplace, incident_to_alert)
        summary_res["dependency_packs"] = json.loads(summary_res["dependency_packs"])
        return summary_res

    @staticmethod
    def match(_dict: dict, path: Path) -> bool:
        if isinstance(_dict, dict) and "wizard" in _dict and path.suffix == ".json":
            return True
        return False

    def dump(
        self,
        dir: DirectoryPath,
        marketplace: MarketplaceVersions,
    ) -> None:
        if not self.path.exists():
            logger.warning(f"Could not find file {self.path}, skipping dump")
            return
        if (
            marketplace == MarketplaceVersions.MarketplaceV2
            or marketplace == MarketplaceVersions.PLATFORM
        ):
            logger.info(
                f"The wizard {dir} current marketplace is {marketplace} skipping dump."
            )
            return
        return super().dump(dir, marketplace)
