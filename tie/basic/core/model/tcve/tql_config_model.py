"""Models for the Configure page's saved TQL export configurations.

A TQL config is a user-authored, saved query (owners + indicator types + free-text
TQL + sort) that the egress Download task executes in full on every scheduled run.
`TqlConfigModel` represents a persisted record as returned to the UI (GET
/api/tql-config); `TqlConfigPostModel` validates incoming config definitions on
save/test (POST /api/tql-config, POST /api/tql-config/test).
"""

import re

from pydantic import BaseModel, field_validator

from core.json_db import Index
from core.model.model_base import ModelBase


class TqlConfigModel(ModelBase):
    """A persisted TQL export configuration, as returned to the UI."""

    id: str = Index()
    owners: list[str]
    rank: int
    sort_direction: str
    sort_field: str
    tql: str
    types: list[str]
    version: str

    @field_validator('owners', 'types', mode='before')
    @classmethod
    def _split_csv(cls, v):
        return v.split(',') if isinstance(v, str) else v


class TqlConfigPostModel(BaseModel):
    """Validates an incoming TQL export configuration on save/test."""

    rank: int
    owners: list[str]
    sort_direction: str
    sort_field: str
    tql: str
    types: list[str]
    version: str | None = None

    @field_validator('owners', 'types', mode='before')
    @classmethod
    def _non_empty_list(cls, v):
        if not v:
            raise ValueError('must not be empty')
        return v

    @field_validator('tql', 'sort_field', 'sort_direction', mode='before')
    @classmethod
    def _non_empty_str(cls, v):
        if not v or not str(v).strip():
            raise ValueError('must not be empty')
        return v

    @field_validator('tql', mode='after')
    @classmethod
    def _no_owner_or_type_clause(cls, v):
        if re.search(r'\bownerName\b', v, re.IGNORECASE) or re.search(
            r'\btypeName\b', v, re.IGNORECASE
        ):
            raise ValueError(
                'TQL must not contain ownerName or typeName filters — owners and indicator '
                'types are controlled exclusively by the Owners and Indicator Types dropdowns.'
            )
        return v


def build_owner_type_tql(tql_config: TqlConfigModel | TqlConfigPostModel) -> tuple[str, dict]:
    """Build the owner/type-scoped TQL clause and REST params for a TQL config.

    When the config has exactly one owner, the REST-level `owner` param is used instead of
    an `ownerName in (...)` TQL clause (returned in the params dict). When it has zero or
    multiple owners, the existing `ownerName in (...)` TQL clause is kept and no `owner`
    param is set. `typeName in (...)` is always kept in the TQL string.

    Returns a `(tql, params)` tuple; `params` is empty unless the single-owner case applies.
    """
    types = {f'"{t.split(":")[0]}"' for t in tql_config.types}
    params: dict = {}

    if len(tql_config.owners) == 1:
        params['owner'] = tql_config.owners[0]
        tql = f'({tql_config.tql}) and typeName in ({",".join(types)})'
    else:
        owners = [f'"{o}"' for o in tql_config.owners]
        tql = (
            f'({tql_config.tql}) and ownerName in ({",".join(owners)}) and typeName in '
            f'({",".join(types)})'
        )

    return tql, params
