"""Batch error collection resource for /api/report/batch-error endpoint."""

# third-party
import falcon
from model.pipe_error_model import PipeErrorModel, PipeErrorPaginatedResponseModel
from records.pipe_error_record import PipeErrorRecord

# first-party
from core.api.endpoint.endpoint_base_abc import EndpointBaseABC


class BatchErrorCollection(EndpointBaseABC):
    """Class for /api/report/batch-error endpoint."""

    def on_get(self, req: falcon.Request, resp: falcon.Response):
        """Handle GET requests — return paginated, filtered pipe error records."""
        by_alias = req.get_param_as_bool('by_alias', default=False)
        request_id_filter = req.get_param('request_id')
        offset = int(req.get_param('offset') or 0)
        limit = int(req.get_param('limit') or 50)

        def _where(r: PipeErrorRecord) -> bool:
            if request_id_filter is not None:
                return request_id_filter.lower() in r.request_id.lower()
            return True

        # load and filter records; sort by date_added desc (most recent first)
        records = list(self.db.load_all(PipeErrorRecord, where=_where))
        records = sorted(
            records,
            key=lambda r: r.date_added or '',
            reverse=True,
        )

        total_count = len(records)
        page = records[offset : offset + limit]

        # NOTE: `from_orm` requires PipeErrorModel to declare `orm_mode = True` in its
        # Config. PipeErrorModel is supplied by the app (model/pipe_error_model.py), not
        # by this template -- it must set it.
        data = [PipeErrorModel.from_orm(r) for r in page]

        response = PipeErrorPaginatedResponseModel(
            data=data,
            count=len(data),
            total_count=total_count,
        )
        resp.media = response.dict(by_alias=by_alias, exclude_none=True)
