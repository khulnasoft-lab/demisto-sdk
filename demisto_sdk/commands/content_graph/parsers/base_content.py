from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Optional

from demisto_sdk.commands.common.constants import MarketplaceVersions
from demisto_sdk.commands.common.content_constant_paths import (
    CONTENT_PATH,
)
from demisto_sdk.commands.content_graph.common import ContentType


class BaseContentParser(ABC):
    """An abstract class for all content types.

    Attributes:
        object_id (str): The content object ID.
        content_type (ContentType): The content object type.
        node_id (str): The content object node ID.
    """

    content_type: ContentType

    def __init__(self, path: Path) -> None:
        self.path: Path = path

    @cached_property
    def field_mapping(self):
        return {}

    @property
    @abstractmethod
    def object_id(self) -> Optional[str]:
        pass

    @property
    def node_id(self) -> str:
        return f"{self.content_type}:{self.object_id}"

    @property
    def source_repo(self) -> Optional[str]:
        return CONTENT_PATH.name

    @staticmethod
    def update_marketplaces_set_with_xsoar_values(marketplaces_set: set) -> set:
        if MarketplaceVersions.XSOAR in marketplaces_set:
            marketplaces_set.add(MarketplaceVersions.XSOAR_SAAS)

        if MarketplaceVersions.XSOAR_ON_PREM in marketplaces_set:
            marketplaces_set.add(MarketplaceVersions.XSOAR)
            marketplaces_set.remove(MarketplaceVersions.XSOAR_ON_PREM)

        return marketplaces_set
