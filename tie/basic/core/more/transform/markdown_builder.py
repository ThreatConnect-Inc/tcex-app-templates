"""Markdown formatting utilities."""

# standard library
import html
import mimetypes
from abc import ABC, abstractmethod


def _format_txt(text, msg='..(truncated)', max_len=500, prepend='', append=''):
    full_text = f'{prepend}{text}{append}'
    # Remove prepend/append from text if already present to avoid duplication
    if prepend and text.startswith(prepend):
        text = text[len(prepend) :]
    if append and text.endswith(append):
        text = text[: -len(append)]

    full_text = f'{prepend}{text}{append}'
    if len(full_text) > max_len:
        allowed_length = max_len - len(msg)
        # Ensure we don't truncate prepend/append
        text_length = allowed_length - len(prepend) - len(append)
        truncated_text = text[: max(text_length, 0)] + msg
        return f'{prepend}{truncated_text}{append}'
    return full_text


class ContentABC(ABC):
    """Abstract Base Class for Markdown components."""

    @abstractmethod
    def to_markdown(self) -> str:
        """Convert to markdown format."""


class Header(ContentABC):
    """Represents a markdown header."""

    def __init__(self, text: str, *, level: int = 3, spacing: int = 2, ai_indicator: bool = False):
        """Initialize class properties.

        Args:
            text: Header text
            level: Header level (1-6)
            spacing: Number of newlines after header
            ai_indicator: If True, prepends sparkle emoji to indicate AI-generated content
        """
        self.text = text
        self.level = level
        self.spacing = '\n' * spacing
        self.ai_indicator = ai_indicator

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        prefix = '✨ ' if self.ai_indicator else ''
        return f'{"#" * self.level} {prefix}{self.text}{self.spacing}'


class TextList(ContentABC):
    """Represents a list of text items in markdown format."""

    def __init__(
        self,
        title,
        sub_title,
        *,
        spacing=2,
        max_items=3,
        max_item_length=500,
        append='',
        prepend='',
        ai_indicator=False,
    ):
        """Initialize class properties.

        Args:
            title: Section title
            sub_title: Label used per item
            spacing: Number of newlines after section
            max_items: Max items to render
            max_item_length: Per-item truncation length
            append: Suffix for each item
            prepend: Prefix for each item
            ai_indicator: If True, prepends ✨ emoji to title for AI content
        """
        for name, value in [
            ('spacing', spacing),
            ('max_item_length', max_item_length),
            ('max_items', max_items),
        ]:
            if value < 0:
                ex_msg = f'{name} must be positive'
                raise ValueError(ex_msg)

        self.title = title
        self.sub_title = sub_title
        self.items = []
        self.spacing = '\n' * spacing
        self.max_items = max_items
        self.prepend = prepend
        self.append = append
        self.max_item_length = max_item_length
        self.ai_indicator = ai_indicator

    def add_item(self, *item: str):
        """Add an item to the list."""
        self.items.extend(item)

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        title_block = Header(self.title, level=3, ai_indicator=self.ai_indicator).to_markdown()

        if not self.items:
            return f'{title_block}No Data Provided.{self.spacing}'

        items_ = self.items[: self.max_items]
        markdown = [title_block]
        for index, item in enumerate(items_, start=1):
            item = _format_txt(
                item, max_len=self.max_item_length, prepend=self.prepend, append=self.append
            )
            markdown.append(f'**{self.sub_title} {index}**\n{item}\n\n')
        if len(self.items) > self.max_items:
            more_items_block = f'\n...and {len(self.items) - self.max_items} more items.'
            markdown.append(more_items_block)
        return '\n\n'.join(markdown) + self.spacing


class Text(ContentABC):
    """Represents a single line of markdown with a bolded key and value."""

    def __init__(self, content: str | dict, *, spacing=1, max_length=500, prepend='', append=''):
        """Initialize class properties."""
        for name, value in [
            ('spacing', spacing),
            ('max_length', max_length),
        ]:
            if value < 0:
                ex_msg = f'{name} must be positive'
                raise ValueError(ex_msg)
        self.content = content
        self.spacing = '\n' * spacing
        self.max_length = max_length
        self.prepend = prepend
        self.append = append

    def _truncate(self, text: str) -> str:
        truncation_message = '...(truncated)'
        full_text = f'{self.prepend}{text}{self.append}'
        if len(full_text) > self.max_length:
            allowed_length = self.max_length - len(truncation_message)
            # Ensure we don't truncate prepend/append
            text_length = allowed_length - len(self.prepend) - len(self.append)
            truncated_text = text[: max(text_length, 0)] + truncation_message
            return f'{self.prepend}{truncated_text}{self.append}'
        return full_text

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        if isinstance(self.content, dict):
            lines = []
            for k, v in self.content.items():
                v = _format_txt(
                    str(v), max_len=self.max_length, prepend=self.prepend, append=self.append
                )
                # v = self._truncate(str(v))
                lines.append(f'**{k}**: {v if v else "N/A"}')
            return self.spacing.join(lines) + self.spacing
        content = _format_txt(
            self.content, max_len=self.max_length, prepend=self.prepend, append=self.append
        )
        return f'{content}{self.spacing}'


class Image(ContentABC):
    """Represents a markdown image with optional fixed size."""

    def __init__(
        self,
        text: str,
        *,
        width: int | None = 500,
        height: int | None = None,
        spacing: int = 2,
    ):
        """Initialize class properties."""
        self.text = text
        self.width = width
        self.height = height
        self.spacing = '\n' * spacing

    def to_markdown(self) -> str:
        """Render as a markdown image."""
        attrs = []
        if self.width is not None:
            attrs.append(f'width="{self.width}"')
        if self.height is not None:
            attrs.append(f'height="{self.height}"')
        attr_str = ' '.join(attrs)
        # Escape URL to prevent XSS
        safe_url = html.escape(self.text, quote=True)
        return f'<img src="{safe_url}" alt="Image" {attr_str} />{self.spacing}'


class Audio(ContentABC):
    """Represents an embedded audio player."""

    def __init__(
        self,
        text: str,
        *,
        width: int | None = 500,
        height: int | None = 50,
        spacing: int = 2,
    ):
        """Initialize class properties."""
        self.text = text
        self.width = width
        self.height = height
        self.spacing = '\n' * spacing

    @staticmethod
    def _guess_type(url: str) -> str | None:
        mime, _ = mimetypes.guess_type(url)
        return mime

    def to_markdown(self) -> str:
        """Render as an embedded audio player."""
        mime = self._guess_type(self.text)
        type_attr = f' type="{mime}"' if mime else ''

        size_attrs = []
        if self.width is not None:
            size_attrs.append(f'width="{self.width}"')
        if self.height is not None:
            size_attrs.append(f'height="{self.height}"')
        size_str = ' '.join(size_attrs)

        # Escape URL to prevent XSS
        safe_url = html.escape(self.text, quote=True)
        return (
            f'<audio controls {size_str}>\n'
            f'  <source src="{safe_url}"{type_attr}>\n'
            f'  Your browser does not support the audio element.\n'
            f'</audio>{self.spacing}'
        )


class Video(ContentABC):
    """Represents an embedded video player with fixed size support."""

    def __init__(
        self,
        text: str,
        *,
        width: int | None = 500,
        height: int | None = 300,
        spacing: int = 2,
    ):
        """Initialize class properties."""
        self.text = text
        self.width = width
        self.height = height
        self.spacing = '\n' * spacing

    @staticmethod
    def _guess_type(url: str) -> str | None:
        mime, _ = mimetypes.guess_type(url)
        return mime

    def to_markdown(self) -> str:
        """Render as an embedded video player."""
        mime = self._guess_type(self.text)
        type_attr = f' type="{mime}"' if mime else ''

        size_attrs = []
        if self.width is not None:
            size_attrs.append(f'width="{self.width}"')
        if self.height is not None:
            size_attrs.append(f'height="{self.height}"')
        size_str = ' '.join(size_attrs)

        # Escape URL to prevent XSS
        safe_url = html.escape(self.text, quote=True)
        return (
            f'<video controls {size_str}>\n'
            f'  <source src="{safe_url}"{type_attr}>\n'
            f'  Your browser does not support the video tag.\n'
            f'</video>{self.spacing}'
        )


class Table(ContentABC):
    """Represents a markdown table."""

    def __init__(
        self, title, *, spacing=2, max_row_length=50, level=3, max_rows=100, ai_indicator=False
    ):
        """Initialize class properties.

        Args:
            title: Table title
            spacing: Newlines after table
            max_row_length: Per-cell truncation length
            level: Header level for title
            max_rows: Max rows to render
            ai_indicator: If True, prepends ✨ emoji to title for AI content
        """
        for name, value in [
            ('spacing', spacing),
            ('max_row_length', max_row_length),
            ('level', level),
            ('max_rows', max_rows),
        ]:
            if value < 0:
                ex_msg = f'{name} must be positive'
                raise ValueError(ex_msg)
        self.title = title
        self.headers = []
        self.rows = []
        self.spacing = '\n' * spacing
        self.level = level
        self.max_row_length = max_row_length
        self.max_rows = max_rows
        self.ai_indicator = ai_indicator

    def set_headers(self, headers):
        """Set the table headers."""
        self.headers = headers

    def add_row(self, *row: dict):
        """Add a row to the table (only header keys are kept)."""
        if not self.headers:
            ex_msg = 'Headers must be set before adding rows.'
            raise ValueError(ex_msg)
        self.rows.extend(row)

    def to_markdown(self) -> str:
        """Convert the table to a markdown formatted string (with title)."""
        title_block = Header(
            self.title, level=self.level, ai_indicator=self.ai_indicator
        ).to_markdown()

        # No data → show message instead of an empty table
        if not self.rows:
            return f'{title_block}No Data Provided.{self.spacing}'

        order = self.headers or list(self.rows[0].keys())

        header_line = f'|{"|".join(order)}|'
        sep_line = f'|{"|".join("-" for _ in order)}|'
        data = self.rows[: self.max_rows]

        parts = [header_line, sep_line]
        for row_ in data:
            row = []
            for col in order:
                row.append(_format_txt(row_.get(col, ''), max_len=self.max_row_length))
            parts.append(f'|{"|".join(row)}|')

        table = '\n'.join(parts)
        return f'{title_block}{table}{self.spacing}'


class MediaList(ContentABC):
    """Represents a list of media items (images, videos, audio) with overflow handling."""

    def __init__(
        self,
        title: str,
        media_type: type[ContentABC],
        *,
        max_items: int = 3,
        overflow_message: str = '{count} more item(s) not shown.',
        level: int = 3,
        spacing: int = 2,
    ):
        """Initialize class properties.

        Args:
            title: Section title (e.g., "Images", "Videos")
            media_type: ContentABC subclass to use (Image, Video, Audio)
            max_items: Maximum number of items to display (default: 3)
            overflow_message: Message template for additional items.
                Use {count} placeholder for remaining count.
            level: Header level for the title (default: 3)
            spacing: Number of newlines after the section (default: 2)
        """
        self.title = title
        self.media_type = media_type
        self.max_items = max_items
        self.overflow_message = overflow_message
        self.level = level
        self.spacing = '\n' * spacing
        self.items = []

    def add_item(self, *urls: str):
        """Add media item URLs to the list.

        Args:
            *urls: One or more media URLs to add
        """
        self.items.extend(urls)

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        if not self.items:
            return ''

        title_block = Header(self.title, level=self.level).to_markdown()
        markdown_parts = [title_block]

        # Add up to max_items
        for item_url in self.items[: self.max_items]:
            media_component = self.media_type(item_url)
            markdown_parts.append(media_component.to_markdown())

        # Add overflow message if there are more items
        if len(self.items) > self.max_items:
            remaining = len(self.items) - self.max_items
            overflow_text = self.overflow_message.format(count=remaining)
            markdown_parts.append(f'_{overflow_text}_\n\n')

        return ''.join(markdown_parts) + self.spacing


class MarkdownBuilder:
    """A simple class to format sections in Markdown."""

    def __init__(self):
        """Initialize class properties."""
        self.content = []

    def add_content(self, *content: ContentABC):
        """Add a table to the list."""
        self.content.extend(content)

    def clear(self):
        """Clear all content."""
        self.content = []

    def to_markdown(self):
        """Format the tables for output."""
        markdown = ''
        for c in self.content:
            markdown += c.to_markdown()
        markdown = markdown.rstrip('\n')
        return markdown

    def header(self, **kwargs) -> Header:
        """Add a Header to the content list.

        Args:
            **kwargs: Keyword-only arguments forwarded to `Header(...)`.
                Supported keys:
                    text (str): Header text. (required)
                    level (int): Header level (1-6). Defaults to 3.
                    spacing (int): Newlines after the header. Defaults to 2.
                    ai_indicator (bool): If True, prepends ✨ emoji for AI content.
                        Defaults to False.

        Returns:
            Header: The created header component.
        """
        obj = Header(**kwargs)
        self.add_content(obj)
        return obj

    def text(self, **kwargs) -> Text:
        """Add a Text block to the content list.

        Args:
            **kwargs: Keyword-only arguments forwarded to ``Text(...)``.
                Supported keys:
                    content (str | dict): Text or key/value dict to render. (required)
                    spacing (int, optional): Newlines after the block. Defaults to 1.
                    max_length (int, optional): Truncation length. Defaults to 500.
                    prepend (str, optional): Prefix for content. Defaults to ''.
                    append (str, optional): Suffix for content. Defaults to ''.

        Returns:
            Text: The created text component.
        """
        obj = Text(**kwargs)
        self.add_content(obj)
        return obj

    def text_list(self, **kwargs) -> TextList:
        """Add a TextList to the content list.

        Args:
            **kwargs: Keyword-only arguments forwarded to ``TextList(...)``.
                Supported keys:
                    title (str): Section title. (required)
                    sub_title (str): Label used per item (e.g., "Note"). (required)
                    spacing (int, optional): Newlines after the section. Defaults to 2.
                    max_items (int, optional): Max items to render. Defaults to 3.
                    max_item_length (int, optional): Per-item truncation length.
                        Defaults to 500.
                    prepend (str, optional): Prefix for each item. Defaults to ''.
                    append (str, optional): Suffix for each item. Defaults to ''.
                    ai_indicator (bool, optional): If True, prepends ✨ emoji to title.
                        Defaults to False.

        Returns:
            TextList: The created list component.
        """
        obj = TextList(**kwargs)
        self.add_content(obj)
        return obj

    def table(self, **kwargs) -> Table:
        """Add a Table to the content list.

        Args:
            **kwargs: Keyword-only arguments forwarded to ``Table(...)``.
                Supported keys:
                    title (str): Table title. (required)
                    spacing (int, optional): Newlines after the table. Defaults to 2.
                    max_row_length (int, optional): Per-cell truncation length. Defaults to 50.
                    level (int, optional): Header level for the title. Defaults to 3.
                    max_rows (int, optional): Max rows to render. Defaults to 100.
                    ai_indicator (bool, optional): If True, prepends ✨ emoji to title.
                        Defaults to False.

        Returns:
            Table: The created table component.
        """
        obj = Table(**kwargs)
        self.add_content(obj)
        return obj

    def media_list(self, **kwargs) -> MediaList:
        """Add a MediaList to the content list.

        Args:
            **kwargs: Keyword-only arguments forwarded to ``MediaList(...)``.
                Supported keys:
                    title (str): Section title (e.g., "Images"). (required)
                    media_type (type[ContentABC]): Media class (Image, Video, Audio). (required)
                    max_items (int, optional): Max items to display. Defaults to 3.
                    overflow_message (str, optional): Template for overflow message.
                        Defaults to '{count} more item(s) not shown.'.
                    level (int, optional): Header level for title. Defaults to 3.
                    spacing (int, optional): Newlines after section. Defaults to 2.

        Returns:
            MediaList: The created media list component.
        """
        obj = MediaList(**kwargs)
        self.add_content(obj)
        return obj
