import { catchError, EMPTY, finalize, tap } from 'rxjs';

import { Component, DestroyRef, EventEmitter, inject, OnInit, Output } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { AlertBoxType } from '@tc-eng/component-library';
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

type OnboardingStep = RenderedSection & {
    form: Form;
    /** This step's client-side validity, pushed up by its generated form. */
    valid: boolean;
};


@Component({
    selector: 'app-onboarding',
    templateUrl: './onboarding.component.html',
    styleUrl: './onboarding.component.scss',
})
export class OnboardingComponent implements OnInit {
    private readonly destroyRef = inject(DestroyRef);

    /** Emitted once the completion record exists server-side. */
    @Output() completed = new EventEmitter<void>();

    steps: OnboardingStep[] = [];

    /** Bound rather than written as a literal so the template is type-checked. */
    protected readonly AlertBoxType = AlertBoxType;
    stepIndex = 0;

    validated = false;
    checks: SettingsCheck[] = [];
    busy = false;
    errorMessage = '';

    private values: { [key: string]: any } = {};

    constructor(
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
                    this.steps = toSettingsSections(config?.ui?.settingsForm, {
                        stepperOnly: true,
                    }).map((section) => ({
                        ...section,
                        form: { fields: section.fields },
                        valid: true,
                    }));
                    this.values = this.steps.reduce(
                        (values, step) => ({ ...values, ...initialFormValues(step.form) }),
                        {},
                    );
                }),
            )
            .subscribe();
    }

    /** Green when passed, amber for a non-blocking warning, red for a real failure. */
    checkColor(check: SettingsCheck): string {
        if (check.passed) {
            return 'var(--tcl-success)';
        }
        return check.severity === 'warning' ? 'var(--tcl-warning)' : 'var(--tcl-error)';
    }

    get isLastStep(): boolean {
        return this.stepIndex >= this.steps.length - 1;
    }

    /**
     * Keep the collected values, and write them back onto the step's own field defaults.
     *
     * `tcl-stepper` renders only the active step's template, so leaving a step destroys
     * its form. Writing the value back into `field.default` is what makes the edit
     * survive until the step is opened again.
     */
    /** The active step's form pushes its validity here — see `GeneratedFormComponent`. */
    handleValidChange(step: OnboardingStep, valid: boolean) {
        step.valid = valid;
    }

    get activeStepValid(): boolean {
        return this.steps[this.stepIndex]?.valid !== false;
    }

    handleFieldChange(step: OnboardingStep, values: { [key: string]: any }) {
        this.values = { ...this.values, ...values };
        // `values` is the generated form's own value map, which omits disabled fields
        // (they never submit) — only write back a field whose value was actually part of
        // this emission, so a disabled field's default is never clobbered to `undefined`.
        for (const field of step.form.fields) {
            if (field.name in values) {
                field.default = values[field.name];
            }
        }
        this.validated = false;
        this.checks = [];
    }

    handleBack() {
        this.stepIndex = Math.max(0, this.stepIndex - 1);
    }

    handleNext() {
        this.stepIndex = Math.min(this.steps.length - 1, this.stepIndex + 1);
    }

    handleValidate() {
        this.busy = true;
        this.errorMessage = '';
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
                    this.errorMessage = 'These settings could not be validated.';
                    return EMPTY;
                }),
                finalize(() => (this.busy = false)),
            )
            .subscribe();
    }

    handleFinish() {
        this.busy = true;
        this.errorMessage = '';
        this.onboardingService
            .complete(this.values)
            .pipe(
                tap(() => this.completed.emit()),
                catchError((error) => {
                    this.validated = false;
                    // `POST /api/onboarding` returns {completed, errors} — pydantic errors,
                    // not `checks`. `handleValidate` above reads `checks` correctly because
                    // `/api/settings/validate` is the only endpoint that returns them, so
                    // reading them HERE meant every rejection showed the generic message
                    // with no detail at all.
                    this.checks = [];
                    const errors = error?.error?.errors ?? [];
                    this.errorMessage = errors.length
                        ? `These settings were rejected: ${errors
                              .map((e) => `${(e?.loc ?? []).join('.')} — ${e?.msg}`)
                              .join('; ')}`
                        : 'These settings were rejected and have not been saved.';
                    return EMPTY;
                }),
                finalize(() => (this.busy = false)),
            )
            .subscribe();
    }

}
