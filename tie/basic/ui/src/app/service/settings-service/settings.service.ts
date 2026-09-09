import { Observable } from 'rxjs';

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { Form } from '../app-service/app.service';
import { SettingsPayload, SettingsValidation } from './settings-interface';

/**
 * Seed a value map from a form schema's defaults.
 *
 * Mirrors what GeneratedFormComponent does internally, so a form that has been rendered
 * but not yet touched still posts the values the user is looking at.
 */
export function initialFormValues(form: Form): { [key: string]: any } {
    const values: { [key: string]: any } = {};
    for (const field of form?.fields ?? []) {
        values[field.name] = field.default;
    }
    return values;
}

@Injectable({
    providedIn: 'root',
})
export class SettingsService {
    apiUrl: string = 'api/settings';

    constructor(private http: HttpClient) {}

    get(): Observable<any> {
        return this.http.get<any>(this.apiUrl);
    }

    /** Dry run. Never mutates anything — the save path re-runs these checks itself. */
    validate(payload: SettingsPayload): Observable<SettingsValidation> {
        return this.http.post<SettingsValidation>(`${this.apiUrl}/validate`, payload);
    }

    save(payload: SettingsPayload): Observable<any> {
        return this.http.put<any>(this.apiUrl, payload);
    }
}
