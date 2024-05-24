
from __future__ import annotations
from typing import Iterable, List
from demisto_sdk.commands.content_graph.objects.integration import Integration
from demisto_sdk.commands.content_graph.parsers.related_files import (
    RelatedFileType,
)
from demisto_sdk.commands.validate.validators.base_validator import (
    BaseValidator,
    ValidationResult,
)

from demisto_sdk.commands.common.constants import (
    IMAGE_WIDTH,
    IMAGE_HEIGHT,
)

ContentTypes = Integration


class IsValidImageDimensionsValidator(BaseValidator[ContentTypes]):
    error_code = "IM111"
    description = ("Checks that the image file size are matching the requirements:"
                   "120x50 px PNG, transparent background, <10kB in Size")
    rationale = ("Image needs to fit its place in the UI. For more information"
                 " see: https://xsoar.pan.dev/docs/integrations/integration-logo")
    error_message = ("You've created/modified a author image with invalid dimensions."
                     ". Please make sure to change the image dimensions to fit the criteria:"
                     " 120x50 px PNG, transparent background, <10kB in Size.")
    related_field = "image"
    is_auto_fixable = False
    expected_git_statuses = [GitStatuses.ADDED, GitStatuses.MODIFIED]
    related_file_type = [RelatedFileType.IMAGE]

    def is_valid(self, content_items: Iterable[ContentTypes]) -> List[ValidationResult]:
        return [
            ValidationResult(
                validator=self,
                message=f"{self.error_message} {content_item.name}_image.png.",
                content_object=content_item,
            )
            for content_item in content_items
            if content_item.image.get_file_dimensions() == (IMAGE_WIDTH, IMAGE_HEIGHT)
        ]
