import { Observable, ReplaySubject, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { SettingsPayload } from '../settings-service/settings-interface';

export interface OnboardingStatus {
    completed: boolean;
    completed_at: string | null;
}

@Injectable({
    providedIn: 'root',
})
export class OnboardingService {
    apiUrl: string = 'api/onboarding';

    private statusSubject = new ReplaySubject<OnboardingStatus>(1);

    constructor(private http: HttpClient) {
        this.load();
    }

    /**
     * Absence of the server-side record is what arms the gate; this reports it.
     *
     * Cached rather than a fresh GET per call: the route guard runs on every navigation and
     * the Settings page needs the same answer, so both must read one value. `refresh()` is
     * what invalidates it once onboarding completes.
     */
    getStatus(): Observable<OnboardingStatus> {
        return this.statusSubject.asObservable();
    }

    /** Re-read the gate. Call after anything that could have completed onboarding. */
    public refresh(): void {
        this.load();
    }

    /** Saves settings through the same server path as `PUT /api/settings`, then completes. */
    complete(payload: SettingsPayload): Observable<any> {
        return this.http.post<any>(this.apiUrl, payload);
    }

    /**
     * Push a status onto the cache — on BOTH the success and the error path.
     *
     * The error path is load-bearing. A `ReplaySubject` fed only by success stays empty
     * forever when the request fails, and the route guard would then never resolve, blanking
     * the whole app. Failing open with `completed: true` matches the intent the app component
     * already had: a stepper that cannot save would be a dead end, so let the app through.
     */
    private load(): void {
        this.http
            .get<OnboardingStatus>(this.apiUrl)
            .pipe(catchError(() => of({ completed: true, completed_at: null })))
            .subscribe((status) => this.statusSubject.next(status));
    }
}
