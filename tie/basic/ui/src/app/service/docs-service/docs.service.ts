import { Observable } from 'rxjs';

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { Doc } from './docs-interface';

@Injectable({
    providedIn: 'root',
})
export class DocsService {
    apiUrl: string = 'api/docs';

    constructor(private http: HttpClient) {}

    /** Every TIE app packages its guide at the same path, so there is nothing to select. */
    getDoc(): Observable<Doc> {
        return this.http.get<Doc>(this.apiUrl);
    }
}
