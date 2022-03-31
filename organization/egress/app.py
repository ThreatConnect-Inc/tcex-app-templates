"""ThreatConnect Job App"""
# standard library
import itertools
from typing import TYPE_CHECKING

# third-party
from tcex.api.tc.v3.tql.tql_operator import TqlOperator
from tcex.exit import ExitCode

# first-party
from job_app import JobApp  # Import default Job App Class (Required)

if TYPE_CHECKING:
    # standard library
    from typing import Iterable

    # third-party
    from tcex import TcEx
    from tcex.api.tc.v3.indicators.indicator import Indicator
    from tcex.sessions.external_session import ExternalSession

    from .app_inputs import TCFiltersModel


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
        self.session.base_url = 'https://httpbin.org'

    def run(self) -> None:
        """Run main App logic."""
        success, error = (0, 0)
        # httbin used for demonstration only, we don't want to bombard it with traffic, so
        # send AT MOST 10 requests per run. Replace this code with your target service ASAP
        for indicator in self.get_indicators(self.inputs.model, 10):
            resp = self.session.post('/post', data=indicator.model.json())
            if resp.ok:
                success += 1
            else:
                error += 1

        exit_msg = f'Added {success} IOCs '
        if error:
            exit_msg += f'and failed to add {error} IOCs '
        else:
            exit_msg += 'to external service.'

        self.tcex.exit(ExitCode.SUCCESS, exit_msg)

    def get_indicators(self, model: 'TCFiltersModel', max_results=None) -> 'Iterable[Indicator]':
        """Retrieve indicators from ThreatConnect based on filter params.

        Args:
            model - filters for indicator retrieval
            max_results - the max number of indicators to return.

        Returns:
            A generator of v3 indicator objects.
        """

        # Retrieve all fields associated with IOCs. Can customize when needed.
        additional_fields = {
            'fields': [
                'threatAssess',
                'observations',
                'attributes',
                'falsePositives',
                'observations',
                'tags',
                'securityLabels',
            ]
        }
        indicators = self.tcex.v3.indicators(params=additional_fields)
        if model.tql:
            indicators = self.tcex.v3.indicators(params=additional_fields)

            # For now set TQL directly. Eventually
            # setting it as a param passed into constructor
            # will work.
            indicators.tql.raw_tql = model.tql

            # if user specified owners, add them too
            if model.owners:
                indicators.filter.owner_name(TqlOperator.IN, model.owners)
        else:
            indicators.filter.owner_name(TqlOperator.IN, model.owners)

            if model.max_false_positives:
                self.tcex.log.info(
                    f'Adding filter false positive count <= {model.max_false_positives}'
                )
                indicators.filter.false_positive_count(TqlOperator.LEQ, model.max_false_positives)

            if model.minimum_rating:
                self.tcex.log.info(f'Adding filter rating {TqlOperator.GEQ} {model.minimum_rating}')
                indicators.filter.rating(TqlOperator.GEQ, model.minimum_rating)

            if model.minimum_confidence:
                self.tcex.log.info(
                    f'Adding filter confidence {TqlOperator.GEQ} {model.minimum_confidence}'
                )
                indicators.filter.confidence(TqlOperator.GEQ, model.minimum_confidence)

            if model.minimum_threatassess_score:
                self.tcex.log.info(
                    f'Adding filter threatAssessScore {TqlOperator.GEQ} '
                    f'{model.minimum_threatassess_score}'
                )
                indicators.filter.threat_assess_score(
                    TqlOperator.GEQ, model.minimum_threatassess_score
                )

            if model.indicator_types:
                self.tcex.log.info(f'Adding filter types {model.indicator_types}')
                indicators.filter.type_name(TqlOperator.IN, model.indicator_types)

            if model.tags:
                self.tcex.log.debug(f'filtering for tags: {model.tags}')
                indicators.filter.has_tag.name(TqlOperator.IN, model.tags)

            if model.last_modified:
                self.tcex.log.info(f'Adding filter modified since = {model.last_modified}')
                indicators.filter.last_modified(TqlOperator.GT, model.last_modified)

        if max_results:
            yield from itertools.islice(indicators, max_results)
        else:
            yield from indicators
