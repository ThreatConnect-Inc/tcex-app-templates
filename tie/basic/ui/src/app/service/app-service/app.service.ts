import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { AlertBoxType } from '@tc-eng/component-library';
import { Observable, ReplaySubject } from 'rxjs';
import { map, tap } from 'rxjs/operators';

export interface Validator {
  name: string;
  config?: any;
}

/** A choice carries a separate `value` when the stored value differs from its label. */
export interface Choice {
  text: string;
  value: any;
  /** Set on a persisted value the server could not match back to a live catalogue entry. */
  stale?: boolean;
}

/** One option of a `radio` field. `subtext` explains what choosing it does. */
export interface FieldOption {
  value: any;
  label: string;
  subtext?: string;
  /** Short right-aligned qualifier, e.g. 'least information captured'. */
  note?: string;
}

export interface FormField {
  choices?: (string | Choice)[];
  default?: any;
  /**
   * Field prose. Four INDEPENDENT keys — a field may carry any combination, and they
   * render in this order. None is an alias for another and none suppresses another:
   *
   * - `shortText`   — one terse line, to keep a dense Settings page scannable. Rendered
   *                   under the label in `settings`; dropped in the stepper, which has
   *                   room for the full `description` instead.
   * - `description` — plain body text. The explanation itself.
   * - `info`        — an aside the operator may want and may skip.
   * - `warning`     — a warning box. Content that must not be skippable, which is why it
   *                   is never rendered as a muted line, and never folded into a tooltip.
   *
   * A field wanting "explain it, then caution about it" sets `description` and `warning`
   * and gets both. That is where a field differs from a section, which picks ONE key by
   * precedence.
   *
   * WHERE each lands depends on the mode — see `proseFor` in generated-form.component.ts,
   * which is the single place that decides:
   *
   * - `stepper`  — `description` and `info` render as blocks (body text, info box). The
   *                stepper is teaching one decision per screen and has the room.
   * - `settings` — `description` and `info` are JOINED into the ⓘ beside the label and
   *                neither renders as a block. A settings page is a form an operator
   *                returns to; rendering both inline gave every field a callout and
   *                pushed the controls off-screen.
   * - `form`     — the ad-hoc, download-TI and job-filter forms. No prose block renders,
   *                because those forms are `display: contents` and own their layout.
   *                There `info` keeps its original meaning as the control's ⓘ tooltip.
   */
  shortText?: string;
  description?: string;
  info?: string;
  warning?: string;
  label: string;
  /** Options for a `radio` or `multi-options` field. Ignored by every other type. */
  options?: FieldOption[];
  /** Shown, with its current value, but not editable. UI affordance only. */
  disabled?: boolean;
  /** Give a select/multi-select a type-ahead filter. Opt in per field. */
  searchable?: boolean;
  /** Spinner bounds for a number input. Derived server-side from the gte/lte validators. */
  minValue?: number;
  maxValue?: number;
  minWidth?: number;
  name: string;
  /** Present only when the field is required — absent otherwise. */
  required?: boolean;
  type?: string;
  validators: Validator[];
}

export interface Form {
  fields: FormField[];
}

/**
 * One group of settings fields, as declared by `UIConfigBuilder.settings_form`.
 *
 * The Settings page renders one group per entry and the onboarding stepper one step per
 * entry, so adding a section server-side adds both with no change here.
 */
export interface SettingsSection {
  /** Heading on the Settings page, and the step name in onboarding. */
  name: string;
  /**
   * Prose under the heading. The KEY chooses the presentation:
   *
   * - `description` — a plain muted line, for saying what the fields are.
   * - `info`        — the same text in an info callout.
   * - `warning`     — the same text in a warning callout, for a caution rather than a
   *                   label: a section telling an operator NOT to change something.
   *
   * Set one. If more than one is set the most emphatic wins, so a section cannot
   * accidentally render its caution as a muted line.
   */
  description?: string;
  info?: string;
  warning?: string;
  /** False keeps the section off the onboarding stepper. Defaults to true. */
  stepper?: boolean;
  fields: FormField[];
}

/**
 * The Settings form: an ordered list of sections — see `UIConfigBuilder.settings_form`.
 *
 * A list rather than a map keyed by name because the order IS the display order.
 */
export type SettingsForm = SettingsSection[];

export interface RenderedSection {
  name: string;
  description: string;
  /** Set only when the description should render as a callout rather than a plain line. */
  alertType: AlertBoxType | null;
  /**
   * Resolved `section.stepper`, defaulting to true.
   *
   * Surfaced so a caller can filter on the COMPLEMENT of the stepper set — the Settings
   * page renders only non-stepper sections while onboarding is incomplete. One resolver,
   * two filters, rather than a second mutually-exclusive option on `toSettingsSections`.
   */
  stepper: boolean;
  fields: FormField[];
}

/** Sections to render, with defaults applied and stepper-excluded ones optionally dropped. */
export function toSettingsSections(
  settingsForm: SettingsForm | undefined,
  options: { stepperOnly?: boolean } = {},
): RenderedSection[] {
  return (settingsForm ?? [])
    .filter((section) => !options.stepperOnly || section.stepper !== false)
    .map((section) => ({
      name: section.name,
      // Resolved here so neither page has to know which keys exist or how they rank.
      description: section.warning ?? section.info ?? section.description ?? '',
      alertType: section.warning
        ? AlertBoxType.Warning
        : section.info
          ? AlertBoxType.Info
          : null,
      stepper: section.stepper !== false,
      fields: section.fields ?? [],
    }));
}

export interface FieldDisplay {
  field: string;
  label: string;
  type?: string;
}

export interface AppConfig {
  schema: string;
  ui: {
    global: {
      sideNav: { label: string; path: string }[];
      featureFlags?: {
        enableAddJob?: boolean;
      };
    };
    adhocRequest?: {
      form: Form;
    };
    downloadTI?: {
      form: Form;
    };
    jobTable: {
      columns: FieldDisplay[];
      details: FieldDisplay[];
      filters: Form;
    };
    notifications?: {
      columns: FieldDisplay[];
      details: FieldDisplay[];
      filters: Form;
    };
    configure?: {
      columns: FieldDisplay[];
      formFields: any[];
      infoTooltip?: string;
    };
    egressErrors?: {
      columns: FieldDisplay[];
      details: FieldDisplay[];
    };
    /** Admin-editable settings, served as a single schema for both Settings and onboarding. */
    settingsForm?: SettingsForm;
    brand?: string;
    owner: string;
    title: string;
    version: string;
  };
}

@Injectable({
  providedIn: 'root',
})
export class AppService {
  apiUrl: string = 'api/tc';

  private appConfigSubject = new ReplaySubject<AppConfig>(1);

  constructor(private http: HttpClient) {
    this.loadUIConfig().subscribe();
  }

  public getConfig(): Observable<AppConfig> {
    return this.appConfigSubject.asObservable();
  }

  /**
   * Re-read the app config from the server.
   *
   * `settingsForm` is NOT a static schema: every field's `default` is read from
   * `self.settings.app_settings` server-side (see `api/ui_config_builder.py`), so the cached
   * `AppConfig` is a snapshot of live values, replayed forever by the `ReplaySubject(1)`
   * below. Without this, saving settings by any route leaves every consumer showing the
   * values from before the save until a hard page reload.
   */
  public refresh(): void {
    this.loadUIConfig().subscribe();
  }

  /** Fetch fresh TC owner names. Call each time the owner dropdown is opened. */
  public getOwners(): Observable<string[]> {
    return this.http
      .get<{ owners: string[] }>('api/tc-info')
      .pipe(map((d) => (Array.isArray(d?.owners) ? d.owners : [])));
  }

  private loadUIConfig(): Observable<AppConfig> {
    return this.http.get<AppConfig>(`${this.apiUrl}/app-config`).pipe(
      tap((config) => {
        this.appConfigSubject.next(config);
      }),
    );
  }
}
