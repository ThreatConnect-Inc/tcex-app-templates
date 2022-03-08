"""ThreatConnect Job App"""
# standard library
from typing import TYPE_CHECKING

# third-party
from tcex.api.tc.v3.tql.tql_operator import TqlOperator
from tcex.exit import ExitCode

# first-party
from job_app import JobApp  # Import default Job App Class (Required)

if TYPE_CHECKING:
    # standard library
    from datetime import datetime
    from typing import Iterable, List, Optional

    # third-party
    from tcex import TcEx
    from tcex.api.tc.v3.indicators.indicator import Indicator
    from tcex.sessions.external_session import ExternalSession


class App(JobApp):
    """Job App"""

    def __init__(self, _tcex: 'TcEx') -> None:
        """Initialize class properties."""
        super().__init__(_tcex)

        # properties
        self.session = None

    def setup(self) -> None:
        """Perform prep/setup logic."""
        # using tcex session_external to get built-in features (e.g., proxy, logging, retries)
        self.session: 'ExternalSession' = self.tcex.session_external

        # setting the base url allow for subsequent API calls to be made by only
        # providing the API endpoint/path.
        self.session.base_url = 'https://my.external_service.com/api'

    def run(self) -> None:
        """Run main App logic."""
        success, error = (0, 0)
        for indicator in self.get_indicators(
            tql=self.inputs.model.tql,
            owners=self.inputs.model.owners,
            indicator_types=self.inputs.model.indicator_types,
            tags=self.inputs.model.tags,
            max_false_positives=self.inputs.model.max_false_positive,
            minimum_confidence=self.inputs.model.minimum_confidence,
            minimum_rating=self.inputs.model.minimum_rating,
            minimum_threatassess_score=self.inputs.model.minimum_threatassess_score,
            last_modified=self.inputs.model.last_modified,
        ):
            resp = self.session.post('/iocs/submit', json=indicator.model.dict())
            if resp.ok:
                success += 1
            else:
                error += 1

        self.tcex.exit(
            ExitCode.SUCCESS,
            f'Added {success} IOCs and failed to add {error} IOCs to external service.',
        )

    def get_indicators(
        self,
        tql: 'Optional[str]' = None,
        owners: 'Optional[List[str]]' = None,
        indicator_types: 'Optional[List[str]]' = None,
        tags: 'Optional[List[str]]' = None,
        max_false_positives: 'Optional[int]' = None,
        minimum_confidence: 'Optional[int]' = None,
        minimum_rating: 'Optional[int]' = None,
        minimum_threatassess_score: 'Optional[int]' = None,
        last_modified: 'Optional[datetime]' = None,
    ) -> 'Iterable[Indicator]':
        """Retrieve indicators from ThreatConnect based on filter params."""

        indicators = self.tcex.v3.indicators()
        if tql:
            indicators = self.tcex.v3.indicators(tql=tql)
            indicators.filter.owner_name(TqlOperator.IN, owners)
        else:
            indicators.filter.owner_name(TqlOperator.IN, owners)

            if max_false_positives:
                self.tcex.log.info(f'Adding filter false positive count <= {max_false_positives}')
                indicators.filter.false_positive_count(TqlOperator.LT, max_false_positives)

            if minimum_rating:
                self.tcex.log.info(f'Adding filter rating {TqlOperator.GEQ} {minimum_rating}')
                indicators.filter.rating(TqlOperator.GEQ, minimum_rating)

            if minimum_confidence:
                self.tcex.log.info(
                    f'Adding filter confidence {TqlOperator.GEQ} {minimum_confidence}'
                )
                indicators.filter.confidence(TqlOperator.GEQ, minimum_confidence)

            if minimum_threatassess_score:
                self.tcex.log.info(
                    f'Adding filter threatAssessScore {TqlOperator.GEQ} '
                    f'{minimum_threatassess_score}'
                )
                indicators.filter.threat_assess_score(TqlOperator.GEQ, minimum_threatassess_score)

            if indicator_types:
                self.tcex.log.info(f'Adding filter types {indicator_types}')
                indicators.filter.type_name(TqlOperator.IN, indicator_types)

            if tags:
                self.tcex.log.debug(f'filtering for tags: {tags}')
                indicators.filter.has_tag.name(TqlOperator.IN, tags)

            if last_modified:
                self.tcex.log.info(f'Adding filter modified since = {last_modified}')
                indicators.filter.last_modified(TqlOperator.GT, last_modified)

            yield from indicators
