/** One pre-flight check result from `POST /api/settings/validate`. */
export interface SettingsCheck {
    check: string;
    passed: boolean;
    /**
     * `error` blocks the save; `warning` does not.
     *
     * A warning flags a configuration that is unwise rather than broken — the poll
     * frequency outrunning the failure threshold, for example. It is shown, it just does
     * not stand between the operator and Save.
     */
    severity: 'error' | 'warning';
    /**
     * The whole of what the operator is told.
     *
     * There is deliberately no `remediation` field. `SettingsValidateResourceBase.check()`
     * returns only `{passed, severity, message}` on every path, so a separate advice field
     * was permanently undefined and its markup unreachable. Remediation advice belongs
     * inside this string — see the `error=`/`warning=` copy in the app's own
     * `settings_validate_resource.py`.
     */
    message: string;
}

export interface SettingsValidation {
    /** False only when a check failed with `severity: 'error'`. */
    passed: boolean;
    checks: SettingsCheck[];
}


/**
 * The settings payload is the generated form's own value map: flat, keyed by setting
 * name. The server declares the field list and re-nests it, so there is nothing here to
 * keep in sync with the model.
 */
export type SettingsPayload = { [key: string]: any };
