import { catchError, Observable, of } from 'rxjs';

import { HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Router } from '@angular/router';

import type { ConfigEntry } from '../../pages/configure/configure.component';
import { BaseService } from '../base-service/base.service';

@Injectable({
    providedIn: 'root',
})
export class ConfigService extends BaseService {
    apiUrl: string = 'api/tql-config';

    constructor(router: Router) {
        super(router);
    }

    public getConfig(): Observable<ConfigEntry[]> {
        return this.http
            .get<ConfigEntry[]>(this.apiUrl, { params: this.defaultParams() })
            .pipe(
                catchError((err) => {
                    this.errorHandler(err);
                    return of([]);
                }),
            );
    }

    public saveConfig(config: any, startOver: boolean = true): Observable<any> {
        return this.http
            .post(this.apiUrl, config, { params: new HttpParams().append('reset', startOver) })
            .pipe(
                catchError((err) => {
                    this.errorHandler(err);
                    return of(null);
                }),
            );
    }

    public testConfig(config: any): Observable<any> {
        return this.http.post(`${this.apiUrl}/test`, config);
    }
}
