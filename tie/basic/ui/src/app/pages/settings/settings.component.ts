import { catchError, EMPTY, finalize, tap } from 'rxjs';

import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { AlertMessageService } from 'src/app/service/alert-message-service/alert-message.service';
import { AlertBoxType, ButtonTheme } from '@tc-eng/component-library';
import {
    AppService,
    Form,
    RenderedSection,
    toSettingsSections,
} from 'src/app/service/app-service/app.service';
import { OnboardingService } from 'src/app/service/onboarding-service/onboarding.service';
import { SettingsCheck } from 'src/app/service/settings-service/settings-interface';
import {
    initialFormValues,
    SettingsService,
} from 'src/app/service/settings-service/settings.service';

@Component({
    selector: 'settings',
    templateUrl: './settings.component.html',
    styleUrl: './settings.component.scss',
})
export class SettingsComponent implements OnInit {
    private readonly destroyRef = inject(DestroyRef);

    /**
     * One entry per section the server declared, in its order — see
     * `UIConfigBuilder.settings_form`. Each renders its own `app-generated-form`, so the
     * grouping lives here rather than being reconstructed from a flag on every field.
     */
    sections: (RenderedSection & { form: Form; valid: boolean })[] = [];

    /** Bound rather than written as a literal so the template is type-checked. */
    protected readonly AlertBoxType = AlertBoxType;
    protected readonly ButtonTheme = ButtonTheme;

    /**
     * Cleared by any edit, set only by a passing server-side validation.
     *
     * This is a usability gate, not a security one — `PUT /api/settings` re-runs the
     * same checks regardless of what the client did.
     */
    validated = false;
    checks: SettingsCheck[] = [];
    busy = false;

    /** Absence of the server-side completion record. Drives the read-only + empty-state view. */
    onboardingRequired = false;

    /** True while the operator is actually in the stepper. Read by `discardStepperGuard`. */
    showStepper = false;

    /** The "finish setup first" notice, reusing the app's existing confirmation modal. */
    showDiscardConfirm = false;

    private values: { [key: string]: any } = {};

    constructor(
        private alertMessageService: AlertMessageService,
        private appService: AppService,
        private onboardingService: OnboardingService,
        private settingsService: SettingsService,
    ) {}

    ngOnInit(): void {
        this.appService
            .getConfig()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((config) => {
                    this.sections = toSettingsSections(config?.ui?.settingsForm).map(
                        (section) => ({
                            ...section,
                            form: { fields: section.fields },
                            valid: true,
                        }),
                    );
                    // Seeded from every section, so an untouched form still posts the
                    // values the operator is looking at.
                    this.values = this.sections.reduce(
                        (values, section) => ({ ...values, ...initialFormValues(section.form) }),
                        {},
                    );
                }),
            )
            .subscribe();

        this.onboardingService
            .getStatus()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((status) => (this.onboardingRequired = !status?.completed));
    }

    /**
     * While onboarding is incomplete only the non-stepper sections show — the read-only
     * Connection block. Everything else is what the stepper is about to collect, and
     * offering it here twice is how an operator ends up half-configured by two routes.
     *
     * `stepper: false` is the same server-side flag the stepper filters on, so a section
     * appears in exactly one of the two places. No server change needed.
     */
    get visibleSections() {
        return this.onboardingRequired ? this.sections.filter((s) => !s.stepper) : this.sections;
    }

    handleStartSetup() {
        this.showStepper = true;
    }

    /**
     * Called by the stepper once the completion record exists server-side.
     *
     * Order matters. `onboardingService.refresh()` re-reads the gate so this page (and the
     * route guard) stop redirecting. `appService.refresh()` re-reads `settingsForm`, whose
     * every `default` is a server-side snapshot of the live record — without it the form the
     * operator lands on shows the values from BEFORE they just saved, and only a hard reload
     * fixes it.
     *
     * `onboardingRequired` and `sections` are deliberately not assigned here: both ngOnInit
     * subscriptions are still live, and both refreshes push new values through them. One
     * source of truth, and `this.values` gets re-seeded from the fresh defaults.
     */
    handleOnboardingComplete() {
        this.alertMessageService.add({
            summary: 'Setup complete.',
            severity: 'success',
        });
        this.onboardingService.refresh();
        this.appService.refresh();
        this.showStepper = false;
    }

    /**
     * Called by `discardStepperGuard`. Shows the explanation and denies the navigation.
     *
     * Returns a plain `false`, not an Observable. This used to hand back a Subject so the
     * guard could wait for a Discard/Keep-editing answer, but neither answer could change
     * the outcome — see the guard's docstring — so there is nothing to wait for. Deny
     * immediately and let the modal be purely informational.
     */
    blockNavDuringSetup(): boolean {
        this.showDiscardConfirm = true;
        return false;
    }

    /** Dismiss the "finish setup first" modal. The operator stays in the stepper either way. */
    handleSetupBlockAcknowledged() {
        this.showDiscardConfirm = false;
    }

    /** Green when passed, amber for a non-blocking warning, red for a real failure. */
    checkColor(check: SettingsCheck): string {
        if (check.passed) {
            return 'var(--tcl-success)';
        }
        return check.severity === 'warning' ? 'var(--tcl-warning)' : 'var(--tcl-error)';
    }

    /** Any edit invalidates the last validation result and re-disables Save. */
    handleFieldChange(values: { [key: string]: any }) {
        // Merged, not replaced: each section's form only knows its own fields.
        this.values = { ...this.values, ...values };
        this.validated = false;
        this.checks = [];
    }

    /** A section's form pushes its client-side validity here. */
    handleValidChange(section: { valid: boolean }, valid: boolean) {
        section.valid = valid;
    }

    /** Every section must be client-side valid before the server is asked anything. */
    get formValid(): boolean {
        return this.sections.every((section) => section.valid);
    }

    handleValidate() {
        this.busy = true;
        this.settingsService
            .validate(this.values)
            .pipe(
                tap((result) => {
                    this.validated = result.passed;
                    this.checks = result.checks ?? [];
                }),
                catchError((error) => {
                    this.validated = false;
                    this.checks = error?.error?.checks ?? [];
                    this.alertMessageService.add({
                        summary: 'Settings could not be validated.',
                        severity: 'error',
                    });
                    return EMPTY;
                }),
                finalize(() => (this.busy = false)),
            )
            .subscribe();
    }

    handleSave() {
        this.busy = true;
        this.settingsService
            .save(this.values)
            .pipe(
                tap(() => {
                    this.alertMessageService.add({
                        summary: 'Settings saved.',
                        severity: 'success',
                    });
                    // Re-arm: a saved form is no longer a validated candidate.
                    this.validated = false;
                }),
                catchError((error) => {
                    // `PUT /api/settings` returns {applied, errors} — pydantic errors, not
                    // `checks`. `handleValidate` above reads `checks` correctly because
                    // `/api/settings/validate` is the only endpoint that returns them, so
                    // reading them HERE meant every rejection showed the generic message
                    // with no detail at all.
                    this.checks = [];
                    this.validated = false;
                    const errors = error?.error?.errors ?? [];
                    this.alertMessageService.add({
                        summary: 'Settings were rejected and have not been saved.',
                        detail: errors.length
                            ? errors
                                  .map((e) => `${(e?.loc ?? []).join('.')} — ${e?.msg}`)
                                  .join('; ')
                            : undefined,
                        severity: 'error',
                    });
                    return EMPTY;
                }),
                finalize(() => (this.busy = false)),
            )
            .subscribe();
    }
}
