import { catchError, Observable, of } from 'rxjs';

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

import { BaseService } from '../base-service/base.service';
import { GetReportBatchErrorsParam, GetReportPdfTrackerParam } from './param-interface';

@Injectable({
    providedIn: 'root',
})
export class ReportService extends BaseService {
    apiUrl: string = `${this.basePrefix}api/report`;

    constructor(private http: HttpClient, router: Router, snackBar: MatSnackBar) {
        super(router, snackBar);
    }

    public getReportBatchErrors(paramData: GetReportBatchErrorsParam): Observable<any> {
        let params = this.paginationParams(paramData);
        if (paramData.requestId) {
            params = params.append('request_id', paramData.requestId);
        }

        return this.http.get(`${this.apiUrl}/batch-error`, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public getReportPdfTracker(paramData: GetReportPdfTrackerParam): Observable<any> {
        let params = this.paginationParams(paramData);
        if (paramData.id) {
            params = params.append('id', paramData.id);
        }

        return this.http.get(`${this.apiUrl}/pdf-tracker`, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }
}
