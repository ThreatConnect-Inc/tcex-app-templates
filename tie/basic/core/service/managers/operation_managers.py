"""Define several 'managers' for handling data operations.

A manager is a way to manage incremental updates, suck as writing chunks of data to a file, or
updating metrics, or updating counts.  Critically, there's a "final" operation for managers: when
a manager is done, it should perform a final operation for any leftover items.
"""

# standard library
import gzip
import json
import time
from collections.abc import Callable
from collections.abc import Generator as _Generator
from contextlib import AbstractContextManager, contextmanager
from enum import Enum
from pathlib import Path
from typing import Self, TypeAlias, TypedDict, TypeVar

# first-party
from core.beacon import inject
from core.json_db.dao import JsonDBDAO
from core.json_db.json_db import JsonDB
from core.service.metrics import Metrics
from core.task.task_path_pipe_injectables import CurrentJob, TaskOutputDir
from core.util.custom_handler import CustomHandler
from core.util.func_utils import combine_context_managers
from model.job_request_model import JobRequestModel

# Declare generic type.
A = TypeVar('A')


# define a few type aliases to make function signatures more readable from pop-ups

# We never use the SendType or ReturnType, so remove that clutter from the signatu
Generator: TypeAlias = _Generator[A, None, None]
# Signature for the function that managers will yeild, that "accepts" values
AcceptFn: TypeAlias = Callable[[dict | list[dict]], None]
# How to translate an accepted object (via AcceptFn) to a "bucket".  What that means will vary
# depending on the manager
TranslationDefinition: TypeAlias = dict[str, str] | Callable[[str], str] | str

# inject default values for several dependencies
deafult_task_output_dir = inject(TaskOutputDir)
default_json_db = inject(JsonDB)
default_current_job = inject(CurrentJob)


def _get_translate_fn(
    translate_type: TranslationDefinition,
) -> Callable[[str], str]:
    """Get the translation function from the given type."""
    match translate_type:
        case dict():
            return translate_type.__getitem__
        case Callable():
            return translate_type
        case str():
            return lambda _: translate_type


@contextmanager
def _accept(
    translate_type: TranslationDefinition,
    handle_chunk: Callable[[list[dict], str], None],
    chunk_size: int,
) -> Generator[AcceptFn]:
    """Return the base function for a manager.

    The returned type is a function that accepts a single item or a list of items, and tracks
    items by data_type.  When a given data_type has exceeded chunk_size, it calls handle_chunk and
    passes the data and data_type to it.

    Basically: manages the chunking of data by data_type.
    """
    translate_fn = _get_translate_fn(translate_type)
    buckets = {}

    def accept(item: dict | list[dict], data_type: str = '') -> None:
        """Accept the given item and add it to the appropriate bucket.

        If a given bucket's size has exceeded chunk_size, call handle_chunk on it.
        """
        for i in item if isinstance(item, list) else [item]:
            translated_type = translate_fn(data_type)
            buckets.setdefault(translated_type, []).append(i)

        for t, chunk in buckets.items():
            while len(chunk) > chunk_size:
                written_chunk, chunk = (
                    chunk[:chunk_size],
                    chunk[chunk_size:],
                )
                handle_chunk(written_chunk, t)
            buckets[t] = chunk

    try:
        yield accept
    finally:
        for data_type, chunk in buckets.items():
            if chunk:
                handle_chunk(chunk, data_type)


@contextmanager
def file_writer_manager(
    translate_type: TranslationDefinition = lambda s: s,
    *,
    chunk_size=5_000,
    file_prefix: str = '',
    file_seperator: str = '#',
    file_extension: str = 'json.gz',
    out_dir: Path = deafult_task_output_dir,
) -> Generator[AcceptFn]:
    """Create a manager that will write data to files on disk."""

    def write_chunk(chunk: list[dict], data_type: str):
        if not chunk:
            return
        file_name_identifiers = [
            file_prefix,
            str(round(time.time() * 10_000_000)),
            data_type,
        ]
        file_name_identifiers = [f for f in file_name_identifiers if f]
        file_name = f'{file_seperator.join(file_name_identifiers)}.{file_extension}'
        with gzip.open(out_dir / file_name, 'wt', encoding='utf-8', compresslevel=9) as f:
            json.dump(chunk, f, cls=CustomHandler)

    with _accept(
        translate_type,
        write_chunk,
        chunk_size,
    ) as accept:
        yield accept


@contextmanager
def processing_metrics_manager(
    translate_type: TranslationDefinition = lambda s: s.replace(r'-_', ' ').title(),
    *,
    chunk_size=100,
    db: JsonDB = default_json_db,
) -> Generator[AcceptFn]:
    """Create a manager that will update the counts for TIProcessingMetrics."""
    metric_service = Metrics(db)

    def write_chunk(chunk: list[dict], data_type: str):
        metric_service.stage_metrics(data_type, len(chunk))
        metric_service.process_metrics()

    with _accept(
        translate_type,
        write_chunk,
        chunk_size,
    ) as accept:
        yield accept


RequestCountField = Enum(
    'RequestCountField',
    [
        ('count_batch_error', 'count_batch_error'),
        ('count_upload_retries', 'count_upload_retries'),
        ('count_batch_group_success', 'count_batch_group_success'),
        ('count_batch_indicator_success', 'count_batch_indicator_success'),
        ('count_download_group', 'count_download_group'),
        ('count_download_indicator', 'count_download_indicator'),
    ],
)


@contextmanager
def request_counts_manager(
    translate_type: TranslationDefinition | RequestCountField = lambda s: s.replace(
        r'-_', ' '
    ).title(),
    *,
    chunk_size=100,
    db: JsonDB = default_json_db,
    request: JobRequestModel = default_current_job,
) -> Generator[AcceptFn]:
    """Create a manager that will update a count field on a JobRequestModel."""
    # We accept an extra type for translate_type here, an enum, so we translate that to a string
    # before passsing it on.
    if isinstance(  # pylint: disable=isinstance-second-argument-not-valid-type
        translate_type, RequestCountField
    ):
        translate_type = translate_type.value

    dao = JsonDBDAO(db, JobRequestModel)

    def write_chunk(chunk: list[dict], field: str | RequestCountField):
        if isinstance(  # pylint: disable=isinstance-second-argument-not-valid-type
            field, RequestCountField
        ):
            field = field.value

        current_request = dao.get(request.request_id)
        setattr(current_request, field, getattr(current_request, field) + len(chunk))
        dao.save(current_request)

    with _accept(
        translate_type,
        write_chunk,
        chunk_size,
    ) as accept:
        yield accept


class BatchDict(TypedDict, total=False):
    """Defintion of a batch for TC."""

    group: list[dict]
    indicator: list[dict]
    association: list[dict]


@contextmanager
def batch_writer_manager(
    translate_type: TranslationDefinition = lambda s: s,
    *,
    chunk_size=5_000,
    file_name_prefix: str = '',
    file_seperator: str = '#',
    file_extension: str = 'json.gz',
    out_dir: Path = deafult_task_output_dir,
) -> Generator[Callable[[BatchDict], None]]:
    """Create a manager that will write data to files on disk."""
    translate_fn = _get_translate_fn(translate_type)
    buckets: dict[str, BatchDict] = {}

    def write_chunk(chunk: BatchDict, data_type: str):
        file_name_identifiers = [
            file_name_prefix,
            str(round(time.time() * 10_000_000)),
            data_type,
        ]
        file_name_identifiers = [f for f in file_name_identifiers if f]
        file_name = f'{file_seperator.join(file_name_identifiers).lower()}.{file_extension}'
        with gzip.open(out_dir / file_name, 'wt', encoding='utf-8', compresslevel=9) as f:
            json.dump(chunk, f, cls=CustomHandler)

    def _batch_len(batch: BatchDict):
        return (
            len(batch.get('group', []))
            + len(batch.get('indicator', []))
            + len(batch.get('association', []))
        )

    def accept(batch: BatchDict, data_type: str = '') -> None:
        translated_type = translate_fn(data_type)

        batch_len = _batch_len(batch)

        bucket_batch = buckets.setdefault(translated_type, {})
        bucket_batch_len = _batch_len(bucket_batch)

        if batch_len + bucket_batch_len > chunk_size and bucket_batch:
            write_chunk(bucket_batch, translated_type)
            buckets[translated_type] = batch
        else:
            for k, v in batch.items():
                bucket_batch.setdefault(k, []).extend(v)

    try:
        yield accept
    finally:
        for data_type, chunk in buckets.items():
            if chunk:
                write_chunk(chunk, data_type)


@contextmanager
def combine_managers(
    *managers: AbstractContextManager[Callable[[dict | list[dict]], None]],
) -> Generator[AcceptFn]:
    """Create a manager that is a composition of several other mangers."""
    with combine_context_managers(*managers) as fns:
        yield lambda *args, **kwargs: [fn(*args, **kwargs) for fn in fns]


class ManagerBuilder:
    """A builder for creating managers."""

    def __init__(self):
        """Initialize the manager builder."""
        self.managers = []

    def with_file_writer_manager(
        self,
        translate_type: TranslationDefinition = lambda s: s,
        *,
        chunk_size=5_000,
        file_prefix: str = '',
        file_seperator: str = '#',
        file_extension: str = 'json.gz',
        out_dir: Path = deafult_task_output_dir,
    ) -> Self:
        """Add a file writer manager to the builder."""
        self.managers.append(
            file_writer_manager(
                translate_type=translate_type,
                chunk_size=chunk_size,
                file_prefix=file_prefix,
                file_seperator=file_seperator,
                file_extension=file_extension,
                out_dir=out_dir,
            )
        )

        return self

    def with_processing_metrics_manager(
        self,
        translate_type: TranslationDefinition = lambda s: s.replace(r'-_', ' ').title(),
        *,
        chunk_size=100,
        db: JsonDB = default_json_db,
    ) -> Self:
        """Add a processing metrics manager to the builder."""
        self.managers.append(
            processing_metrics_manager(
                translate_type=translate_type,
                chunk_size=chunk_size,
                db=db,
            )
        )

        return self

    def with_request_counts_manager(
        self,
        translate_type: TranslationDefinition | RequestCountField = lambda s: s.replace(
            r'-_', ' '
        ).title(),
        *,
        chunk_size=100,
        db: JsonDB = default_json_db,
        request: JobRequestModel = default_current_job,
    ) -> Self:
        """Add a request counts manager to the builder."""
        self.managers.append(
            request_counts_manager(
                translate_type=translate_type, chunk_size=chunk_size, db=db, request=request
            )
        )

        return self

    def with_batch_writer_manager(
        self,
        translate_type: TranslationDefinition = lambda s: s,
        *,
        chunk_size=5_000,
        file_name_prefix: str = '',
        file_seperator: str = '#',
        file_extension: str = 'json.gz',
        out_dir: Path = deafult_task_output_dir,
    ) -> Self:
        """Add a batch writer manager to the builder."""
        self.managers.append(
            batch_writer_manager(
                translate_type=translate_type,
                chunk_size=chunk_size,
                file_name_prefix=file_name_prefix,
                file_seperator=file_seperator,
                file_extension=file_extension,
                out_dir=out_dir,
            )
        )

        return self

    def build(self) -> AbstractContextManager[AcceptFn]:
        """Build the manager."""
        if not self.managers:
            msg = 'No managers added to the builder.'
            raise ValueError(msg)

        return combine_managers(*self.managers)
