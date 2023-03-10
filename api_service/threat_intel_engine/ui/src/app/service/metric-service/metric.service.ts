import { catchError, Observable, of } from 'rxjs';

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

import { BaseService } from '../base-service/base.service';
import { GetTiProcessingMetricsParam } from './param-interface';

@Injectable({
    providedIn: 'root',
})
export class MetricService extends BaseService {
    apiUrl: string = `${this.basePrefix}api/metric`;

    constructor(private http: HttpClient, router: Router, snackBar: MatSnackBar) {
        super(router, snackBar);
    }

    public getMetricProcessing(paramData: GetTiProcessingMetricsParam): Observable<any> {
        let params = this.paginationParams(paramData);

        return this.http.get(`${this.apiUrl}/processing`, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public getMetricTasks(): Observable<any> {
        return this.http.get(`${this.apiUrl}/tasks`).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }
}
