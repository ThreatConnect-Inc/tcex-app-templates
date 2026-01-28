"""JsonDB module for storing and loading entities from disk."""

# standard library
import gzip as gz
import importlib
import json
import os
import threading
import time
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from enum import Enum
from functools import cached_property, lru_cache
from pathlib import Path
from types import GenericAlias
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

# third-party
import uuid6
from pydantic import BaseModel, Field
from pydantic.fields import Undefined
from tcex.logger.trace_logger import TraceLogger

if TYPE_CHECKING:
    # third-party
    from pydantic.typing import AbstractSetIntStr, MappingIntStrAny, NoArgAnyCallable

SortBy = Enum('SortBy', ['CREATED', 'MODIFIED', 'INDEX'])
SortOrder = Enum('SortOrder', {'ASC': 'asc', 'DESC': 'desc'})


def Embedded(  # noqa: N802, PLR0913
    default: Any = Undefined,
    *,
    default_factory: 'NoArgAnyCallable | None' = None,
    alias: str | None = None,
    title: str | None = None,
    description: str | None = None,
    exclude: 'AbstractSetIntStr | MappingIntStrAny | Any | None' = None,
    include: 'AbstractSetIntStr | MappingIntStrAny | Any | None' = None,
    const: bool | None = None,
    gt: float | None = None,
    ge: float | None = None,
    lt: float | None = None,
    le: float | None = None,
    multiple_of: float | None = None,
    allow_inf_nan: bool | None = None,
    max_digits: int | None = None,
    decimal_places: int | None = None,
    min_items: int | None = None,
    max_items: int | None = None,
    unique_items: bool | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    allow_mutation: bool = True,
    regex: str | None = None,
    discriminator: str | None = None,
    repr: bool = True,  # noqa: A002
    **extra: Any,
):
    """Mark a pydantic field as being embedded.

    An embedded field will not be written to its own file, but will be written to
    the file of the parent entity.
    """
    return Field(
        default=default,
        default_factory=default_factory,
        alias=alias,
        title=title,
        description=description,
        exclude=exclude,
        include=include,
        const=const,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        allow_inf_nan=allow_inf_nan,
        max_digits=max_digits,
        decimal_places=decimal_places,
        min_items=min_items,
        max_items=max_items,
        unique_items=unique_items,
        min_length=min_length,
        max_length=max_length,
        allow_mutation=allow_mutation,
        regex=regex,
        discriminator=discriminator,
        repr=repr,
        json_db_embedded=True,
        **extra,
    )


def Index(  # noqa: N802, PLR0913
    default: Any = Undefined,
    *,
    default_factory: 'NoArgAnyCallable | None' = lambda: str(uuid6.uuid7()),
    alias: str | None = None,
    title: str | None = None,
    description: str | None = None,
    exclude: 'AbstractSetIntStr | MappingIntStrAny | Any | None' = None,
    include: 'AbstractSetIntStr | MappingIntStrAny | Any | None' = None,
    const: bool | None = None,
    gt: float | None = None,
    ge: float | None = None,
    lt: float | None = None,
    le: float | None = None,
    multiple_of: float | None = None,
    allow_inf_nan: bool | None = None,
    max_digits: int | None = None,
    decimal_places: int | None = None,
    min_items: int | None = None,
    max_items: int | None = None,
    unique_items: bool | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    allow_mutation: bool = True,
    regex: str | None = None,
    discriminator: str | None = None,
    repr: bool = True,  # noqa: A002
    **extra: Any,
):
    """Mark a pydantic field as being an index."""
    return Field(
        default=default,
        default_factory=default_factory,
        alias=alias,
        title=title,
        description=description,
        exclude=exclude,
        include=include,
        const=const,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        allow_inf_nan=allow_inf_nan,
        max_digits=max_digits,
        decimal_places=decimal_places,
        min_items=min_items,
        max_items=max_items,
        unique_items=unique_items,
        min_length=min_length,
        max_length=max_length,
        allow_mutation=allow_mutation,
        regex=regex,
        discriminator=discriminator,
        repr=repr,
        json_db_index=True,
        **extra,
    )


A = ParamSpec('A')
R = TypeVar('R')


def enforce_write_policies(fn: Callable[A, R]) -> Callable[A, R]:
    """Decorate function to enforce write policies."""

    def _decorator(*args: A.args, **kwargs: A.kwargs) -> R:
        self: JsonDB = args[0]  # type: ignore
        if not self.allow_multiprocess_write and self.pid != os.getpid():
            msg = 'Multiprocess write is not allowed.'
            raise RuntimeError(msg)
        if not self.allow_multithread_write and (
            self.tid != threading.get_ident() or self.pid != os.getpid()
        ):
            msg = 'Multithread write is not allowed.'
            raise RuntimeError(msg)
        return fn(*args, **kwargs)

    return _decorator


T = TypeVar('T')
P = TypeVar('P', bound=BaseModel)


class JsonDB:
    """JsonDB class for storing and loading entities from disk."""

    def __init__(
        self,
        path: str | Path,
        log: TraceLogger,
        *,
        gzip: bool = True,
        json_args=None,
        allow_multiprocess_write=True,
        allow_multithread_write=True,
    ) -> None:
        """Initialize JsonDB."""
        self.allow_multiprocess_write = allow_multiprocess_write
        self.allow_multithread_write = allow_multithread_write
        self.log = log
        self.gzip = gzip
        self.json_args = json_args if json_args is not None else {}
        self.path = Path(path)
        if self.path.exists() and not self.path.is_dir():
            msg = 'Path is not a directory.'
            raise ValueError(msg)
        self.path.mkdir(parents=True, exist_ok=True)
        self.pid = os.getpid()
        self.tid = threading.get_ident()

        self._cleanup()
        self._migrate_gzip()

    @contextmanager
    def acquire(
        self, cls: type[P], index_value: Any, *, timeout: float = 20
    ) -> Generator[P, None, None]:
        """Acquire entity of a given class by index value."""
        lock_file_path = None
        try:
            now = time.time_ns()
            directory = self._storage_directory(cls)
            lock_file_path = directory / f'{index_value}#{now}.lock'
            lock_file_path.touch()

            lock_files = directory.glob(f'{index_value}#*.lock')
            winner = self._get_winning_lock_file(lock_files)

            while winner != lock_file_path and (timeout == -1 or timeout > 0):
                time.sleep(0.5)
                if timeout != -1:
                    timeout -= 0.5
                lock_files = directory.glob(f'{index_value}#*.lock')
                winner = self._get_winning_lock_file(lock_files)

            if winner != lock_file_path:
                msg = 'Entity has already been aquired.'
                raise RuntimeError(msg)  # noqa: TRY301

            yield self.load(cls, index_value)
        except Exception as e:
            msg = 'Could not acquire entity.'
            raise RuntimeError(msg) from e
        finally:
            if lock_file_path:
                lock_file_path.unlink(missing_ok=True)

    def get_paths(
        self,
        cls: type[P],
        *,
        sort_by: SortBy | str = SortBy.INDEX,
        sort_order: SortOrder | str = SortOrder.ASC,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Path]:
        """Get all paths for entities of the given type"""
        if isinstance(sort_by, str):
            sort_by = SortBy[sort_by.upper()]

        if isinstance(sort_order, str):
            sort_order = SortOrder[sort_order.upper()]

        paths = list(self._storage_directory(cls).rglob(f'*.{self._get_file_extension}'))

        sort_order = SortOrder[sort_order.upper()] if isinstance(sort_order, str) else sort_order

        reverse = sort_order == SortOrder.DESC
        sort_by = sort_by or SortBy.INDEX
        offset = offset if offset is not None else 0

        match sort_by:
            case SortBy.MODIFIED:
                paths.sort(key=lambda x: x.stat().st_mtime, reverse=reverse)
            case SortBy.CREATED:
                try:
                    paths.sort(key=lambda x: x.stat().st_birthtime, reverse=reverse)
                except AttributeError:
                    paths.sort(key=lambda x: x.stat().st_ctime, reverse=reverse)
            case SortBy.INDEX:
                paths.sort(key=self.get_index_from_path, reverse=reverse)
        return paths[offset : limit + offset if limit else limit]

    def load(self, cls: type[P], index_value: Any) -> P:
        """Load entity of a given class by index value."""
        paths = self._storage_directory(cls).rglob(f'{index_value}.jsondb*')
        path = next(paths, None)

        if path is None:
            msg = f'Entity of type {cls.__name__} with index {index_value!r} does not exist.'
            raise FileNotFoundError(msg)

        return self.load_from_path(cls, path, raise_on_missing=True)  # type: ignore

    def _file_text_preview(
        self, p: Path, head_len: int = 100, tail_len: int = 100
    ) -> tuple[str, str]:
        """Safely read a file for logging previews: returns (head, tail)."""
        try:
            if any(suf == '.gz' for suf in p.suffixes):
                with gz.open(p, 'rt', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            else:
                content = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            # Preview read failed; log and return empty previews.
            self.log.exception(f'event=preview-read-failed file="{p}"')
            return '', ''
        if not content:
            return '', ''
        return content[:head_len], content[-tail_len:]

    def _handle_invalid_json_file(
        self,
        p: Path,
        err: Exception,
        *,
        head_len: int = 100,
        tail_len: int = 100,
    ) -> None:
        """Log an invalid JSON file with previews and then delete it."""
        head, tail = self._file_text_preview(p, head_len=head_len, tail_len=tail_len)
        content = [head, tail]
        content = [c for c in content if c]
        content = '...'.join(content)
        self.log.warning(f'event=invalid-json file="{p}" error="{err}" content="{content}"')
        try:
            p.unlink()
            self.log.info(f'event=invalid-json-removed file="{p}"')
        except Exception:
            self.log.exception(f'event=invalid-json-remove-failed file="{p}"')

    def load_all(
        self,
        cls: type[P],
        *,
        where: Callable[[P], bool] | None = None,
        sort_by: SortBy | str = SortBy.INDEX,
        sort_order: SortOrder | str = SortOrder.ASC,
        offset: int = 0,
        limit: int | None = None,
    ) -> Iterable[P]:
        """Load all entities of a given class.  Sort by options are CREATED, MODIFIED, INDEX."""
        paths = self.get_paths(
            cls, sort_by=sort_by, sort_order=sort_order, offset=offset, limit=limit
        )

        target_count = limit + offset if limit is not None else len(paths)
        yielded = 0

        for p in paths:
            try:
                entity = self.load_from_path(cls, p)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self._handle_invalid_json_file(p, e)  # <- central handler
                continue
            if entity is None:
                # File was deleted between get_paths() and load - skip it
                continue
            if where is None or where(entity):
                yield entity
                yielded += 1
                if yielded >= target_count:
                    break

    def load_from_path(
        self, clz: type[P], file_path: Path, *, raise_on_missing: bool = False
    ) -> P | None:
        """Load a model from a file path.

        Args:
            clz: The model class to load.
            file_path: Path to the file.
            raise_on_missing: If True, raises FileNotFoundError when file doesn't exist.
                If False (default), returns None and logs a warning. Use False when
                iterating over paths from get_paths() to handle race conditions where
                files are deleted between listing and loading.

        Returns:
            The loaded model, or None if file doesn't exist and raise_on_missing=False.
        """
        # if this is a subclass, we need to import the correct class to instantiate it.
        if file_path.parent != self._storage_directory(clz):
            module = '.'.join(file_path.parent.name.split('.')[:-1])
            class_name = file_path.parent.name.split('.')[-1]
            clz = getattr(importlib.import_module(module), class_name)

        try:
            if file_path.suffix == '.gz':
                with gz.open(file_path, 'rt', encoding='utf-8') as f:
                    unserialized = json.loads(f.read())
            else:
                unserialized = json.loads(file_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            if raise_on_missing:
                raise
            self.log.warning(f'event=stale-path-skipped, file="{file_path}"')
            return None

        for field, model_info in clz.__fields__.items():
            if (
                isinstance(model_info.outer_type_, GenericAlias)
                and model_info.outer_type_.__origin__ is list
                and issubclass(model_info.type_, BaseModel)
                and not model_info.field_info.extra.get('json_db_embedded', False)
            ):
                unserialized[field] = [
                    self.load(model_info.type_, item) for item in unserialized[field]
                ]
            elif issubclass(model_info.type_, BaseModel) and not model_info.field_info.extra.get(
                'json_db_embedded', False
            ):
                unserialized[field] = self.load(model_info.type_, unserialized[field])

        return clz(**unserialized)

    def load_paths(self, clz: type[P], paths: list[Path]) -> list[P]:
        """Load entities from paths, skipping any that no longer exist.

        Use this when iterating over paths from get_paths() to safely handle
        race conditions where files are deleted between listing and loading.
        """
        results = []
        for path in paths:
            entity = self.load_from_path(clz, path)
            if entity is not None:
                results.append(entity)
        return results

    @enforce_write_policies
    def delete(self, entity: BaseModel):
        """Delete entity from disk."""
        self._get_file_path(entity).unlink()

    @enforce_write_policies
    def save(self, entity: BaseModel):
        """Save entity to disk in a safe way."""
        composed_entities = []
        for field, field_info in entity.__fields__.items():
            value = getattr(entity, field)
            if isinstance(value, BaseModel) and not field_info.field_info.extra.get(
                'json_db_embedded', False
            ):
                composed_entities.append((field, self.get_index_value(value), value))
            if (
                isinstance(value, list)
                and len(value) > 0
                and isinstance(value[0], BaseModel)
                and not field_info.field_info.extra.get('json_db_embedded', False)
            ):
                composed_entities.append(
                    (field, [self.get_index_value(item) for item in value], value)
                )

        serialized = entity.dict(exclude={field[0] for field in composed_entities})
        for field_name, index_value, value in composed_entities:
            if isinstance(value, list):
                for item in value:
                    self.save(item)
            else:
                self.save(value)
            serialized[field_name] = index_value

        swap_file_path = self._get_swp_path(entity)
        file_path = self._get_file_path(entity)
        if self.gzip:
            with gz.open(swap_file_path, 'wt', encoding='utf-8') as f:
                f.write(json.dumps(serialized, indent=None, **self.json_args))
        else:
            swap_file_path.write_text(json.dumps(serialized, indent=None, **self.json_args))

        # this is atomic, and that is crucial.
        # see https://docs.python.org/3/library/pathlib.html#pathlib.Path.rename, but especially
        # https://docs.python.org/3/library/pathlib.html#pathlib.Path.rename
        swap_file_path.rename(file_path)

    def _cleanup(self):
        for path in self.path.rglob('*.lock'):
            path.unlink()

        for path in self.path.rglob('*.swp'):
            path.unlink()

    def _get_file_name(self, entity: Any) -> str:
        return f'{self.get_index_value(entity)}.{self._get_file_extension}'

    @cached_property
    def _get_file_extension(self) -> str:
        return 'jsondb.gz' if self.gzip else 'jsondb'

    def _get_file_path(self, entity: BaseModel) -> Path:
        return self._storage_directory(entity.__class__) / self._get_file_name(entity)

    def get_index_field(self, entity: type[BaseModel]) -> str | None:
        """Determine the index field for a given Pydantic model entity.

        This method checks the fields of the provided Pydantic model to identify
        the field marked with the `json_db_index` extra attribute. If no such field
        is found, it defaults to using the 'id' field if it exists. If neither is
        present, a `TypeError` is raised.

        Args:
            entity (type[BaseModel]): The Pydantic model class to inspect.

        Returns:
            str: The name of the index field.

        Raises:
            TypeError: If no index field is defined or found for the given entity.
        """
        index_field = None
        for field, value in entity.__fields__.items():
            if value.field_info.extra.get('json_db_index', False):
                index_field = field
                break
        else:
            if 'id' in entity.__fields__:
                index_field = 'id'

        if index_field is None:
            msg = f'Index field is not defined for type {entity.__class__.__name__}.'
            raise TypeError(msg)

        return index_field

    def get_index_from_path(self, path: Path) -> str:
        """Extract an index string from a given file path.

        The method removes the file extension (and an additional '.gz' suffix if present)
        from the file name and returns the remaining portion as a dot-separated string.

        Args:
            path (Path): The file path from which to extract the index.

        Returns:
            str: The extracted index string.
        """
        name = path.name
        if name.endswith('.gz'):
            name = name[:-3]
        return '.'.join(name.split('.')[0:-1])

    def get_index_value(self, entity: BaseModel):
        """Retrieve the value of the index field from the given entity.

        Args:
            entity (BaseModel): The entity object from which to retrieve the index value.

        Returns:
            Any: The value of the index field.

        Raises:
            ValueError: If the index field is not defined for the entity's class.
            ValueError: If the index field value is None.
        """
        index_field = self.get_index_field(entity.__class__)
        if index_field is None:
            msg = 'Index field is not defined.'
            raise ValueError(msg)

        index = getattr(entity, index_field, None)

        if index is None:
            msg = f'Index field {index_field} cannot be None.'
            raise ValueError(msg)

        return index

    def _get_swp_path(self, entity: BaseModel) -> Path:
        regular_file_name = self._get_file_name(entity)
        return (
            self._storage_directory(entity.__class__) / f'{time.time_ns()}#{regular_file_name}.swp'
        )

    def _get_winning_lock_file(self, lock_files) -> Path:
        winner = None
        for lock_file in lock_files:
            parts = ''.join(lock_file.name.split('.')[:-1]).split('#')
            timestamp = float(parts[-1])
            if winner is None or timestamp < winner[0]:  # pylint: disable=unsubscriptable-object
                winner = (timestamp, lock_file)

        if winner is None:
            msg = (
                'No lock files found. This may be a transient race condition '
                'where lock files were deleted between listing and selection.'
            )
            raise RuntimeError(msg)
        return winner[1]  # pylint: disable=unsubscriptable-object

    def _migrate_gzip(self):
        """Migrate existing files to or from gzip.

        This only really matters when the gzip flag is changed across runs.
        """
        if self.gzip:
            for path in self.path.rglob('*.jsondb'):
                with gz.open(path.with_suffix('.jsondb.gz'), 'wt', encoding='utf-8') as f:
                    f.write(path.read_text(encoding='utf-8'))
                path.unlink()
        else:
            for path in self.path.rglob('*.jsondb.gz'):
                with gz.open(path, 'rt', encoding='utf-8') as f:
                    path.with_suffix('.jsondb').write_text(f.read())
                    path.unlink()

    def _storage_directory(self, clz: type[P]) -> Path:
        return find_storage_directory_for_type(clz, self.path)

    @staticmethod
    def type_slug(clz) -> str:
        """Generate a unique type slug for a given class.

        The type slug is a string that combines the module name and the class name
        of the provided class, separated by a dot.

        Args:
            clz: The class for which the type slug is to be generated.

        Returns:
            str: A string representing the type slug in the format 'module_name.class_name'.
        """
        return f'{clz.__module__}.{clz.__name__}'

    @property
    def _pydantic(self) -> BaseModel:
        return cast('BaseModel', self)


@lru_cache(maxsize=20)
def find_storage_directory_for_type(clz: type[P], base_path: Path) -> Path:
    """Determine and creates the storage directory for a given type within a base path.

    This function recursively resolves the storage directory for the provided class type
    by traversing its inheritance hierarchy. If the class does not inherit from `BaseModel`,
    it continues up the hierarchy until it finds a suitable base. The resulting directory
    is named using a slug derived from the class type and is created if it does not already exist.

    Args:
        clz (type[P]): The class type for which the storage directory is being determined.
        base_path (Path): The base directory path where the storage directory will be created.

    Returns:
        Path: The resolved and created storage directory path.

    Raises:
        ValueError: If a file with the same name as the intended directory already exists
                    and is not a directory.
    """
    if len(clz.__bases__) == 0:
        directory = base_path
    elif clz.__bases__[0] != BaseModel:
        directory = find_storage_directory_for_type(clz.__bases__[0], base_path)  # type: ignore
    else:
        directory = base_path

    directory = directory / JsonDB.type_slug(clz)  # type: ignore
    if directory.exists() and not directory.is_dir():
        msg = f'File {directory} exists and is not a directory.'
        raise ValueError(msg)

    directory.mkdir(parents=True, exist_ok=True)

    return directory
