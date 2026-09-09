"""UIConfigBuilderABC — abstract base for building UI configurations."""

from abc import abstractmethod
from typing import Any

from core.service.notification_service import DIGEST_INTERVAL_MAP, NOTIFICATION_TYPES
from core.task.task_path_pipe_abc import TaskPathPipeABC


class UIConfigBuilderABC:
    """Abstract base class for building UI configuration.

    Concrete subclasses override ``populate()`` and the various ``*_columns``,
    ``*_details``, ``*_filters``, and ``*_form_fields`` methods to define the
    data-driven UI for their app type.
    """

    def __init__(self, api_properties):
        """Initialize the UI configuration builder with settings."""
        self.settings = api_properties.settings
        self.tasks = api_properties.tasks
        self.sdk = getattr(api_properties, 'sdk', None)

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------

    @staticmethod
    def mask_secret(secret: str, visible: int = 2) -> str:
        """Render a secret as a mask plus its last `visible` characters.

        Enough to confirm WHICH key is deployed without disclosing it. The tail is only
        shown on a secret long enough for it to be a small fraction — on a short one those
        two characters are a meaningful share of the whole, so it is masked entirely.
        """
        secret = str(secret or '')
        if not secret:
            return ''
        if len(secret) < 8:
            return '•' * 8
        return '•' * 8 + secret[-visible:]

    @staticmethod
    def select_choices(catalogue, selected) -> tuple[list[dict], list[str]]:
        """Return `(choices, default)` for a select built from a catalogue of values.

        The catalogue is the source of truth for what may be chosen; `selected` is only
        ever filtered against it. Matching is case-insensitive and the CATALOGUE's spelling
        is returned, so a value seeded from the app inputs in another case still shows as
        selected. A stored value the catalogue no longer offers is dropped.

        A real app usually fetches the catalogue from the vendor rather than from a static
        list — `self.select_choices(self.sdk.collections(), ...)` — in which case it should
        be cached at startup, because `populate()` gates the UI boot.
        """
        selected = {str(entry).strip().lower() for entry in selected or []}

        choices = []
        default = []
        for entry in catalogue or []:
            value = str(entry)
            choices.append({'text': value, 'value': value})
            if value.lower() in selected:
                default.append(value)
        return choices, default

    # ------------------------------------------------------------------
    # Branding
    # ------------------------------------------------------------------

    def brand(self) -> str:
        """Brand key used by the UI to select the logo.

        Override in concrete subclasses to change branding
        (e.g. ``"vendor"``).  Default is ``"threatconnect"``.
        """
        return 'threatconnect'

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    @property
    def all_statuses(self):
        """All statuses for the job table."""
        statuses = []
        for task in self.tasks.all():
            if isinstance(task, TaskPathPipeABC):
                statuses.append(task.task_settings.status_active.title())
                statuses.append(task.task_settings.status_complete.title())

        statuses += ['Failed', 'Pending']
        return statuses

    # ------------------------------------------------------------------
    # Top-level assembler (abstract)
    # ------------------------------------------------------------------

    @abstractmethod
    def populate(self) -> dict:
        """Build and return the complete UI configuration dict."""

    # ------------------------------------------------------------------
    # Field generators
    # ------------------------------------------------------------------

    def generate_field(
        self, field: str, label: str, type_: str | None = None, tooltip: str | None = None
    ):
        """Generate a table column / detail field descriptor."""
        field_info = {'field': field, 'label': label}
        if type_:
            field_info['type'] = type_
        if tooltip:
            field_info['tooltip'] = tooltip
        return field_info

    def generate_side_nav_item(self, label: str, path: str):
        """Generate a side nav item."""
        return {'label': label, 'path': path}

    def generate_form_field(
        self,
        name: str,
        label: str,
        type_: str | None = None,
        choices: list | None = None,
        default: Any = '',
        required: bool = False,
        additional_validators: list[dict] | None = None,
        info: str | None = None,
        min_width: int | None = None,
    ):
        """Generate a form field descriptor."""
        choices = choices or []
        additional_validators = additional_validators or []

        field = {
            'name': name,
            'label': label,
            'type': type_,
            'choices': choices,
            'default': default,
            # `required` was only ever turned into a validator, never emitted — so the
            # `[required]` binding every control already carries was permanently
            # `undefined` and no field has ever rendered its required marker.
            # `or None` so an optional field is served exactly the JSON it was before.
            'required': required or None,
            # `additional_validators` used to be accepted and then dropped, so every
            # declared cross-field validator silently never reached the UI.
            'validators': list(additional_validators),
            'info': info,
            'minWidth': min_width,
        }
        if required and 'required' not in [
            validator['name'] for validator in additional_validators
        ]:
            field['validators'].append({'name': 'required'})

        field = {key: value for key, value in field.items() if value is not None}
        return field

    def generate_settings_input(
        self,
        name: str,
        label: str,
        type_: str | None = None,
        choices: list | None = None,
        default: Any = '',
        required: bool = False,
        info: str | None = None,
        min_width: int | None = None,
        additional_validators: list[dict] | None = None,
        short_text: str | None = None,
        description: str | None = None,
        warning: str | None = None,
        searchable: bool = False,
        options: list[dict] | None = None,
        disabled: bool = False,
    ):
        """Generate one field of the Settings form.

        A settings input IS an ordinary form field, so the shared builder produces it and
        the keys only the Settings form uses are added here. Keeping them out of
        `generate_form_field` means the ad-hoc, download and filter forms are served
        exactly the JSON they always were.

        It takes no `section`: on the Settings form a field's section is the key it is
        listed under in `settings_form()`, which keeps the grouping visible in the code
        that does the grouping.

        FIELD PROSE — four INDEPENDENT keys. None is an alias for another and none
        suppresses another; a field may carry any combination, and they render in this
        order::

            short_text = (
                '...'  # one terse line, for the dense Settings page
            )
            description = '...'  # plain body text
            info = '...'  # an info box
            warning = '...'  # a warning box

        Pick by what the words ARE, not by how much room there is. `description` is the
        explanation itself. `info` is an aside the operator may want and may skip.
        `warning` must not be skippable, which is why it is always a box and is never
        folded into a tooltip. A field wanting "explain it, then caution about it" sets
        `description` and `warning` and gets both.

        WHERE each one lands is the UI's decision, not this builder's — `proseFor` in
        `ui/src/app/components/generated-form/generated-form.component.ts` is the single
        place that decides, and it differs per mode:

        - Settings page: `label ⓘ` / `short_text` / `warning` / control. `description` and
          `info` are joined into that ⓘ and do NOT render as blocks. Write them expecting
          to be read on demand.
        - Onboarding stepper: label / `description` / `warning` / `info` / control, all as
          blocks, and `short_text` is dropped — the stepper has room for the full prose.
        - `form` mode (ad-hoc, download-TI, job-filter): no prose block renders at all,
          because those forms are `display: contents` and own their own layout. There
          `info` keeps its original meaning: the control's ⓘ tooltip.

        So `short_text` is the terse line for the Settings page and `description` is the
        long form for the stepper; a field used in both should set both.

        `disabled` shows the field and its current value but does not let an admin change
        it — for a setting fixed at deploy time, or one this install is not permitted to
        touch. It is a UI affordance ONLY. The save path does not know a field was
        disabled, so a value posted for one is applied like any other; see the note in
        `settings_resource.build_candidate` for what does and does not protect a field.
        """
        field = self.generate_form_field(
            name=name,
            label=label,
            type_=type_,
            choices=choices,
            default=default,
            required=required,
            additional_validators=additional_validators,
            info=info,
            min_width=min_width,
        )

        # Only set when asked for, so a settings field that wants none of this is served
        # the same shape as any other form field. The four prose keys are INDEPENDENT —
        # none is an alias for another, and a field may carry any combination of them.
        if short_text:
            field['shortText'] = short_text
        if description:
            field['description'] = description
        if warning:
            field['warning'] = warning
        if searchable:
            field['searchable'] = True
        if options:
            field['options'] = list(options)
        if disabled:
            field['disabled'] = True

        self._apply_value_bounds(field)
        return field

    @staticmethod
    def _apply_value_bounds(field: dict) -> None:
        """Derive minValue/maxValue from the field's range validators, in place.

        Derived from the validators rather than declared separately: `gte`/`lte` are
        what REJECT an out-of-range value, `minValue`/`maxValue` are what stop the
        number input's spinner producing one. Both are wanted, and reading the bound
        off the validator means it is written down once and they cannot disagree.
        """
        for validator in field['validators']:
            bound = (validator.get('config') or {}).get('value')
            if bound is None:
                continue
            if validator['name'] in ('gte', 'gt'):
                field['minValue'] = bound
            elif validator['name'] in ('lte', 'lt'):
                field['maxValue'] = bound

    # -- the settings form ----------------------------------------------------

    def settings_form(self) -> list[dict]:
        """Return the Settings form: an ordered list of sections.

        A LIST, not a map keyed by name, because the order is the display order and a list
        says so. A JSON object would work by accident — Python, JSON and JS all happen to
        preserve key order — but a JS object hoists integer-like keys ahead of the rest, so
        a section named `2024` would silently jump to the front.

        Each section is::

            {
                'name': 'Ingestion',  # heading, and the stepper's step name
                'description': '...',  # optional prose under the heading
                'stepper': False,  # optional; omit to include it in onboarding
                'fields': [...],
            }

        `description` is optional because most sections do not need one — but a section
        that does should say it here rather than repeating it on every field it covers. It
        matters most in the stepper, where a step is one screen with no surrounding page to
        explain why the operator is looking at this group.

        The prose key chooses its own presentation — use exactly one of::

            'description': '...'    # a plain muted line: what these fields are
            'info': '...'           # the same text in an info callout
            'warning': '...'        # the same text in a warning callout

        Reach for `warning` when the prose is a caution rather than a label: a section
        telling an operator NOT to change something has to look different from one telling
        them what the fields do. Use it sparingly — a page of four callouts draws attention
        to nothing, which is the whole point of having a plain form.

        If more than one is set the most emphatic wins, so a section cannot accidentally
        render its caution as a muted line.

        `stepper: False` keeps a section off the onboarding flow. Read-only or
        deploy-time values belong on the Settings page but not in a setup flow, which
        collects decisions.

        `populate()` serves this under `settingsForm`; the Settings page renders one group
        per entry and the stepper one step per included entry, so neither knows the field
        list.
        """
        return []

    @property
    def notification_labels(self) -> tuple[str, ...]:
        """Notification categories an admin may choose from.

        Defaults to every category the notification service knows. An app narrows this to
        the categories its `app_spec.yml` actually offers by overriding the property —
        which is the whole override, rather than a restated copy of `notification_inputs`.
        """
        return tuple(NOTIFICATION_TYPES)

    def notification_inputs(self):
        """Settings governing what reaches the ThreatConnect notification center."""
        return [
            self.generate_settings_input(
                name='notification_digest_interval',
                label='Notification Digest Interval',
                type_='select',
                required=True,
                choices=list(DIGEST_INTERVAL_MAP),
                # Stored as a timedelta, chosen by label. An interval set outside the form
                # matches nothing and renders as no selection, which is the honest answer.
                default=next(
                    (
                        label
                        for label, interval in DIGEST_INTERVAL_MAP.items()
                        if interval == self.settings.app_settings.notification_digest_interval
                    ),
                    None,
                ),
                short_text='How often queued notifications are batched and sent.',
                description=(
                    'Events are collected and delivered to the ThreatConnect notification '
                    'center as a single digest on this interval, rather than as one message '
                    'per event, so a burst of retries does not flood it. Recipients are the '
                    'ThreatConnect users and groups configured on the job itself. A shorter '
                    'interval means you hear about a problem sooner but receive more '
                    'messages; a longer one batches a whole incident into one. Nothing is '
                    'lost either way — every event is recorded on the Notifications page in '
                    'this app regardless of when, or whether, a digest is sent.'
                ),
            ),
            self.generate_settings_input(
                name='notification_types',
                label='Notification Types',
                type_='multi-options',
                # Cards, not a dropdown: each type needs a sentence saying what it means,
                # and `note` carries the priority so the ranking is legible at a glance.
                # `value` stays `config.category` so stored values round-trip unchanged.
                options=[
                    {
                        'value': NOTIFICATION_TYPES[label].category,
                        'label': label,
                        'note': NOTIFICATION_TYPES[label].priority,
                        'subtext': NOTIFICATION_TYPES[label].description,
                    }
                    for label in self.notification_labels
                ],
                default=list(self.settings.app_settings.notification_types or []),
                # `description`, not `short_text`: the cards below carry the detail, so this
                # one line is the whole explanation and is wanted in both modes.
                description='Which events are delivered to the notification center.',
                # No `info` here on purpose. Its first half restated the digest-interval
                # field directly above, and its second half near-duplicated the
                # Notifications SECTION description; the per-type `subtext` now carries the
                # substance.
            ),
        ]

    # ------------------------------------------------------------------
    # Configure page (egress TQL config management)
    # ------------------------------------------------------------------

    def configure_table_columns(self) -> list[dict]:
        """Columns shown in the Configure table.

        Override to customise which config fields appear as table columns.
        Default returns an empty list (no configure page).
        """
        return []

    def configure_form_fields(self) -> list[dict]:
        """Form fields for the Configure add/edit drawer.

        Override to provide the dynamic form layout for configuring TQL queries
        (owners, types, sort field/direction, TQL text, etc.).
        """
        return []

    def configure_info_tooltip(self) -> str | None:
        """Optional tooltip text displayed next to the Configure page title.

        Override to provide app-specific guidance (e.g. explaining TQL query
        ordering and dedup behaviour).
        """
        return None

    # ------------------------------------------------------------------
    # Egress errors page
    # ------------------------------------------------------------------

    def egress_error_table_columns(self) -> list[dict]:
        """Columns shown in the Egress Errors table.

        Override to customise which error fields appear as table columns.
        Default returns an empty list (no egress errors page).
        """
        return []

    def egress_error_table_details(self) -> list[dict]:
        """Fields shown in the Egress Error detail / side-drawer view.

        Override to customise the detail view for egress errors.
        """
        return []
