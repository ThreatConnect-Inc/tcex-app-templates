"""Config resource for /api/tql-config endpoint."""

# standard library
import json
import uuid
from threading import Lock

# third-party
import falcon
from model.tql_config_model import TqlConfigModel, TqlConfigPostModel
from pydantic import ValidationError
from records.tql_config_record import TqlConfigRecord

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC


class ConfigResource(EndpointBaseABC):
    """Class for /api/tql-config endpoint."""

    save_lock = Lock()

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests — return all TQL config records sorted by rank."""
        by_alias = req.get_param_as_bool('by_alias', default=False)
        records = sorted(
            self.db.load_all(TqlConfigRecord),
            key=lambda r: r.rank,
        )
        # NOTE: `from_orm` requires TqlConfigModel to declare `orm_mode = True` in its
        # Config. TqlConfigModel is supplied by the app (model/tql_config_model.py), not
        # by this template -- it must set it.
        resp.media = [
            json.loads(TqlConfigModel.from_orm(r).json(by_alias=by_alias)) for r in records
        ]

    def on_post(self, req: falcon.Request, resp: falcon.Response):
        """Handle POST requests — replace all TQL config records."""
        with self.save_lock:
            raw = req.media or []
            try:
                configs: list[TqlConfigPostModel] = [
                    TqlConfigPostModel.parse_obj(c) for c in (raw if isinstance(raw, list) else [])
                ]
            except ValidationError as ex:
                raise falcon.HTTPUnprocessableEntity(description=str(ex)) from ex
            self.log.warning(f'configs: {configs}')

            # delete all existing TQL config records
            for record in list(self.db.load_all(TqlConfigRecord)):
                self.db.delete(record)

            if configs:
                versions = {c.version for c in configs}
                if req.get_param('reset', default='true').lower() == 'true' or None in versions:
                    new_version = str(uuid.uuid4())
                    for c in configs:
                        c.version = new_version

                for c in configs:
                    record = TqlConfigRecord(
                        rank=c.rank,
                        owners=','.join(c.owners),
                        sort_direction=c.sort_direction,
                        sort_field=c.sort_field,
                        tql=c.tql,
                        types=','.join(c.types),
                        version=c.version,
                    )
                    self.db.save(record)

            resp.media = {'saved': len(configs)}
