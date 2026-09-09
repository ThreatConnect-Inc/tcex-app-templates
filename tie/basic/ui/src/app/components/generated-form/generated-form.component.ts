import { BehaviorSubject, Observable } from 'rxjs';

import {
    Component,
    EventEmitter,
    HostBinding,
    Input,
    OnChanges,
    Output,
    SimpleChanges,
} from '@angular/core';

import {
    AlertBoxType,
    CheckboxState,
    MenuItemListSettings,
    MenuItemType,
} from '@tc-eng/component-library';
import { Form } from 'src/app/service/app-service/app.service';
import { ValidatorsService } from 'src/app/service/validators-service/validators.service';

/**
 * How the form presents a field's label and prose.
 *
 * - `form`     — the original behaviour, and a contract: no heading, no paragraph, no
 *                callout. The control draws its own label and `info` stays the ⓘ tooltip.
 *                The ad-hoc, download-TI and job-filter forms are `display: contents` and
 *                depend on the field emitting nothing of its own.
 * - `settings` — the form draws the heading for EVERY field, followed by `shortText`, then
 *                `warning` if there is one, then the control. `description` and `info` are
 *                joined into the ⓘ beside the label rather than rendered as blocks. A
 *                settings page is a form an operator comes back to and scans, so the label,
 *                its one-line gist and its control stay together; the long-form prose is one
 *                hover away.
 * - `stepper`  — the form draws the heading, then the description, then the callouts, then
 *                the control. There is deliberately NO ⓘ anywhere: a stepper is one
 *                decision per screen with no surrounding page to lean on, so everything
 *                worth reading is on the page.
 *
 * Both structured modes draw their OWN label, at one weight. Settings previously let the
 * library control draw its label for everything except card types, so a single page mixed
 * two label weights for no reason a reader could infer.
 */
export type GeneratedFormMode = 'form' | 'settings' | 'stepper';

@Component({
    selector: 'app-generated-form',
    templateUrl: './generated-form.component.html',
    styleUrl: './generated-form.component.scss',
})
export class GeneratedFormComponent implements OnChanges {
    private formConfigSubject = new BehaviorSubject<any[]>([]);
    formConfig$ = this.formConfigSubject.asObservable();

    private validSubject = new BehaviorSubject<boolean>(false);
    public valid$: Observable<boolean> = this.validSubject.asObservable();

    /** Bound rather than written as a literal so the template is type-checked. */
    protected readonly AlertBoxType = AlertBoxType;

    @Input() formConfig: Form;
    @Input() mode: GeneratedFormMode = 'form';

    /**
     * Exposes the mode as a host class so the stylesheet can switch layout.
     *
     * `form` keeps `display: contents` and inherits whatever the surrounding page does —
     * that is what the ad-hoc, download-TI, and filter forms have always relied on. The
     * settings and stepper modes opt into a real block layout instead, which is also what
     * lets them reset the text alignment `tcl-stepper` imposes on its step content.
     */
    @HostBinding('class') get hostClasses(): string {
        // `--structured` is what the stylesheet keys off. Emitting one shared class rather
        // than styling both mode classes keeps the compiled CSS from carrying a duplicate
        // copy of every nested selector.
        const structured = this.mode === 'form' ? '' : ' generated-form--structured';
        return `generated-form generated-form--${this.mode}${structured}`;
    }

    /**
     * Emits the full current value map after every edit.
     *
     * The Settings page and the onboarding stepper both gate Save on a server-side
     * validation result, so they need to know the moment an edit invalidates it. The
     * values ride along because a stepper destroys the form when the step changes.
     */
    @Output() fieldChange = new EventEmitter<{ [key: string]: any }>();

    /**
     * Emits this form's validity whenever it changes.
     *
     * `valid$` is the better route when the caller can reach the form with a template
     * reference — that is what the Download and Jobs pages do. The onboarding stepper
     * cannot: its form is inside the step loop and its buttons are outside it, so the
     * validity has to be pushed out rather than pulled in.
     */
    @Output() validChange = new EventEmitter<boolean>();

    form: { [key: string]: { error: string; value: any; config: any } } = {};

    constructor(private validatorsService: ValidatorsService) {}

    ngOnChanges(_changes: SimpleChanges): void {
        if (this.formConfig) {
            this.buildDownloadFormConfig(this.formConfig);
            // Compute validity up front rather than assuming false. A caller that gates a
            // button on `valid$` would otherwise keep it disabled on an untouched form
            // that is perfectly valid. `dirty` still suppresses the error TEXT, so an
            // untouched form is judged without being nagged.
            this.validateForm();
        }
    }

    getValues() {
        const values = {};
        for (const field in this.form) {
            // A disabled control does not submit — the same rule a plain HTML form
            // follows. It also means a masked read-only value (an API key shown as
            // `••••••••9f`) can never be mistaken for something the user typed.
            if (this.form[field].config.disabled) {
                continue;
            }
            values[field] = this.form[field].value;
        }

        return values;
    }

    handleChange(event: any, field: string) {
        const fieldInfo = this.form[field];
        switch (fieldInfo.config.type) {
            case 'select':
                // this is likely a bug, and the correct item should be in event.selectd, but it's not.
                fieldInfo.value = event.item.value;
                fieldInfo.config.dirty = true;
                break;
            case 'multi-select':
                fieldInfo.value = event.selected.map((item) => item.value);
                fieldInfo.config.dirty = true;
                break;
            case 'date':
                fieldInfo.value = event ? event.getTime() : event;
                fieldInfo.config.dirty = true;
                break;
            case 'number':
                // tcl-text-input emits its raw string value even with type="number",
                // so coerce here rather than shipping a string to the settings API.
                // An emptied field is null, not 0 — 0 is a legitimate value.
                fieldInfo.value =
                    event === '' || event === null || event === undefined ? null : Number(event);
                fieldInfo.config.dirty = true;
                break;
            case 'toggle':
                fieldInfo.value = !!event;
                fieldInfo.config.dirty = true;
                break;
            case 'radio':
                // The template passes the chosen option's own `value`, not the DOM event,
                // so whatever type the server declared is what round-trips back to it.
                fieldInfo.value = event;
                fieldInfo.config.dirty = true;
                break;
            case 'multi-options': {
                // Toggles, where `radio` assigns. The template passes the option's own
                // value, so whatever type the server declared round-trips.
                const current: any[] = Array.isArray(fieldInfo.value) ? fieldInfo.value : [];
                // A new array rather than push/splice, so change detection sees a new
                // reference and the cards re-render.
                fieldInfo.value = current.includes(event)
                    ? current.filter((value) => value !== event)
                    : [...current, event];
                fieldInfo.config.dirty = true;
                break;
            }
            default:
                fieldInfo.value = event;
        }

        this.validateForm();
        this.fieldChange.emit(this.getValues());
    }

    validateForm() {
        for (const fieldName in this.form) {
            const field = this.form[fieldName];
            // A disabled field is not the user's to fix, so it must never hold Save
            // hostage — a `required` one served empty would otherwise do exactly that.
            if (field.config.disabled) {
                field.error = null;
                continue;
            }
            field.error = this.validatorsService.validate(
                field.value,
                field.config.validators,
                this.form,
            );
        }

        const valid = Object.values(this.form).every((field) => !field.error);
        this.validSubject.next(valid);
        // Deferred a tick because `ngOnChanges` calls this mid-change-detection: a parent
        // that stores the result would otherwise be mutating state Angular has already
        // checked this pass, which is an ExpressionChangedAfterItHasBeenChecked in dev.
        queueMicrotask(() => this.validChange.emit(valid));

        // if a field hasn't been touched yet, don't show error message yet.
        for (const fieldName in this.form) {
            const field = this.form[fieldName];
            if (!field.config.dirty) {
                field.error = null;
            }
        }
    }

    private buildDownloadFormConfig(form: Form) {
        const downloadFormConfig = form.fields.map((field) => {
            return {
                ...field,
                advancedSettings: this.buildAdvancedSettings(field),
                choices: this.mapChoices(field),
                dirty: false,
                minWidth: field.minWidth ?? 200,
                // `tcl-text-input` trims its `value`, so a numeric default crashes it.
                // The form's own value stays the real type — this is display only.
                textValue: field.default === null || field.default === undefined
                    ? ''
                    : String(field.default),
                ...this.proseFor(field),
                ownLabel: this.ownLabelFor(field),
            };
        });

        for (const field of downloadFormConfig) {
            this.form[field.name] = { error: '', value: field.default, config: field };
        }

        this.formConfigSubject.next(downloadFormConfig);
    }

    /**
     * Does the CONTROL draw the label, or do we?
     *
     * `form` mode is `true`: those forms are `display: contents` (see the .scss), so the
     * form must never emit a heading of its own — the ad-hoc, download-TI and job-filter
     * forms depend on that contract.
     *
     * BOTH structured modes are `false`, and uniformly so. Settings used to be `true`
     * except for card types, which meant a settings page mixed two different labels: the
     * library control's (lighter, drawn inside the control) for most fields and this
     * component's `.form-field__label` (600 weight, drawn above) for the card types. Same
     * page, same kind of thing, two weights — it read as if the bold ones meant something.
     * Drawing every structured label here is what makes them consistent, and it is also
     * what puts the label above its help text instead of below it.
     */
    private ownLabelFor(_field): boolean {
        return this.mode === 'form';
    }

    /**
     * Resolve where each of a field's four prose keys lands, for this mode.
     *
     * The keys are INDEPENDENT. `description` is body text, `info` is an info box,
     * `warning` is a warning box, and a field may carry any combination — the template
     * renders whichever came back, in that order. None of them is an alias for another,
     * and this component must not collapse them: it serves every app built on this
     * template, not just the one in front of it.
     *
     * `shortText` is the only mode-dependent one. It is the terse line that keeps a dense
     * Settings page scannable, and it is dropped in the stepper, which has room for the
     * full `description` instead.
     *
     * `form` mode is the ad-hoc, download-TI and job-filter forms. They are
     * `display: contents` and own their own layout, so no prose block renders; there
     * `info` keeps its original meaning as the control's ⓘ tooltip.
     *
     * SETTINGS collapses `description` and `info` into `labelInfo`, the ⓘ beside the label,
     * and renders NEITHER as a block. The stepper is teaching and has the room for prose;
     * the settings page is a form an operator returns to, and rendering both there gave
     * every field a multi-line callout — seven fields became seven boxes, and the controls
     * they described were pushed off-screen. The words are not lost, they are one hover
     * away, and `shortText` still states the gist in the open.
     *
     * `warning` stays a block in BOTH modes and is deliberately never folded into the ⓘ:
     * its whole point is that it must not be skippable, and a tooltip is skippable.
     */
    private proseFor(field): {
        shortText: string | null;
        description: string | null;
        info: string | null;
        warning: string | null;
        tooltip: string | null;
        labelInfo: string | null;
    } {
        if (this.mode === 'form') {
            return {
                shortText: null,
                description: null,
                info: null,
                warning: null,
                tooltip: field.info ?? null,
                labelInfo: null,
            };
        }

        if (this.mode === 'settings') {
            return {
                shortText: field.shortText ?? null,
                description: null,
                info: null,
                warning: field.warning ?? null,
                tooltip: null,
                // Joined, not picked: the keys are independent and a field may carry both,
                // so choosing one would silently drop the other. Blank line between them
                // because `tclTooltip` renders text, and they are separate thoughts.
                labelInfo:
                    [field.description, field.info].filter(Boolean).join('\n\n') || null,
            };
        }

        return {
            shortText: null,
            description: field.description ?? null,
            info: field.info ?? null,
            warning: field.warning ?? null,
            tooltip: null,
            labelInfo: null,
        };
    }

    /** True when `option` is the field's current value, or is in it for a multi field. */
    /**
     * A toggle's checked state, read from live form state.
     *
     * `[checked]="field.default"` bound to the static server-sent default instead, which
     * `handleChange` never writes back — so the control could revert to the server value
     * on a change-detection pass while `form[name].value` held the user's choice. Every
     * other stateful type reads live state via `isSelected`; this matches.
     */
    protected isToggleChecked(field): boolean {
        return !!this.form[field.name]?.value;
    }

    protected isSelected(field, option): boolean {
        const value = this.form[field.name]?.value;
        return Array.isArray(value) ? value.includes(option.value) : value === option.value;
    }

    /**
     * A checkbox option's state as the library enum.
     *
     * A helper rather than a template ternary because `CheckboxState.Checked === 0` and is
     * therefore FALSY — an inline ternary here is a trap waiting to be "simplified" into a
     * truthiness test, which would silently invert every checkbox.
     */
    protected checkboxStateFor(field, option): CheckboxState {
        return this.isSelected(field, option) ? CheckboxState.Checked : CheckboxState.UnChecked;
    }

    private buildAdvancedSettings(field): MenuItemListSettings {
        const settings: MenuItemListSettings = {};

        if (field.type === 'multi-select') {
            settings.headerSelectAll = true;
        }

        // Opt-in per field rather than by type: a long vendor-supplied list is faster to
        // filter than to scan, a short curated one is the opposite.
        if (field.searchable) {
            settings.filter = true;
            settings.filterPlaceholder = `Search ${field.label}`;
            settings.filterNoResults = `No ${field.label.toLowerCase()} match that search`;
        }

        return settings;
    }

    private mapChoices(field) {
        if (field.type !== 'select' && field.type !== 'multi-select') {
            return [];
        }

        const multiSelectOptions =
            field.type === 'multi-select'
                ? {
                      iconRight: 'eye',
                      actionInfo: 'View Only This',
                      actionOnHover: true,
                  }
                : {};

        // `default` is normally `''` or an array, but a field served with an explicit
        // `default: null` would throw on `.includes`.
        const selected = field.default ?? [];

        return (
            field.choices?.map((choice: any) => {
                // A plain string choice is its own label and value. Settings choices
                // carry {text, value} so, for example, a vendor collection can display
                // its human-readable name while storing its UUID.
                const text = choice?.text ?? choice;
                const value = choice?.value ?? choice;

                return {
                    ...multiSelectOptions,
                    text,
                    value,
                    type: field.type === 'select' ? MenuItemType.Default : MenuItemType.MultiSelect,
                    checked: selected.includes(value)
                        ? CheckboxState.Checked
                        : CheckboxState.UnChecked,
                    selected: selected.includes(value),
                };
            }) || []
        );
    }
}
