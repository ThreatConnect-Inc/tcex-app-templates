"""Test config resource for /api/tql-config/test endpoint."""

# third-party
import falcon
from model.tql_config_model import TqlConfigPostModel
from pydantic import ValidationError

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC


class TestConfigResource(EndpointBaseABC):
    """Class for /api/tql-config/test endpoint."""

    def on_post(self, req: falcon.Request, resp: falcon.Response):
        """Handle POST requests — validate a TQL config against the TC API and return results."""
        try:
            tql_config = TqlConfigPostModel.parse_obj(req.media or {})
        except ValidationError as ex:
            raise falcon.HTTPBadRequest(description=str(ex)) from ex
        owners = (f'"{o}"' for o in tql_config.owners)

        types = {f'"{t.split(":")[0]}"' for t in tql_config.types}
        tql = (
            f'({tql_config.tql}) and ownerName in ({",".join(owners)}) and typeName in '
            f'({",".join(types)})'
        )

        sorting = f'{tql_config.sort_field} {tql_config.sort_direction}'
        if tql_config.sort_field.lower() != 'id':
            sorting += ' ID DESC'

        params = {
            'count': 'true',
            'fields': [],
            'resultLimit': 1,
            'sorting': sorting,
        }

        indicators = self.tcex.api.tc.v3.indicators(params=params)
        indicators.tql.set_raw_tql(tql)

        # A failing TQL must not report success. `contextlib.suppress(Exception)` swallowed
        # tcex's handle_error, then returned TC's raw error body — internals and all — under
        # a 200, so a validation endpoint answered "failed" with "OK". Surface it as a 400
        # with a clean message instead, and let a genuinely missing response be a 502 rather
        # than an AttributeError on `.request`.
        try:
            next(iter(indicators))
        except StopIteration:
            pass  # no matching records is a valid result, not an error
        except Exception as ex:
            self.log.warning(f'action=test-tql-config, status=failed, error={ex}')
            raise falcon.HTTPBadRequest(
                title='TQL validation failed',
                description='The query was rejected by ThreatConnect. Check the TQL syntax.',
            ) from ex

        request = getattr(indicators, 'request', None)
        if request is None:
            raise falcon.HTTPBadGateway(
                description='ThreatConnect returned no response for the query.'
            )
        resp.media = request.json()
