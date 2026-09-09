"""Model Definition"""

# REVIEW (template cleanup, 2026-08-25): retained pending a decision -- confirm with the
# team whether this is a supported extension point for app authors or leftover.
# It was proposed for deletion, then kept because "no importers" does not prove much
# in a template: files here exist to be used by apps built FROM it.
# Evidence at the time:
#   A second copy lives at core/api/validation/models/multipart_form_data_model.py. Neither is
#   imported; apps that use this model define their own in model/ (tcve-sentinel,
#   tcvf-mandiant-advantage-intel). core/api/validation/util.py matches on the JSON-schema
#   $ref NAME, not on an import, so it works off the app copy.

from pydantic import BaseModel, Extra, Field


class MultipartFormDataModel(BaseModel):
    """Model Definition"""

    content: bytes = Field(..., description='The content of the file.')
    content_type: str = Field(..., description='The Content-Type for the file.')
    filename: str = Field(..., description='The filename for the file.')
    name: str = Field(..., description='The name for the part.')

    class Config:
        """Model Config"""

        arbitrary_types_allowed = True
        extra = Extra.forbid
