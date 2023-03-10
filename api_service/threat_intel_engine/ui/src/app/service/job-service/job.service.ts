import { catchError, Observable, of } from 'rxjs';

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

import { BaseService } from '../base-service/base.service';
import { GetJobRequestParam } from './param-interface';

@Injectable({
    providedIn: 'root',
})
export class JobService extends BaseService {
    apiUrl: string = `${this.basePrefix}api/job`;

    constructor(private http: HttpClient, router: Router, snackBar: MatSnackBar) {
        super(router, snackBar);
    }

    public getJobRequests(paramData: GetJobRequestParam): Observable<any> {
        let params = this.paginationParams(paramData);
        if (paramData.jobType) {
            params = params.append('job_type', paramData.jobType);
        }
        if (paramData.requestId) {
            params = params.append('request_id', paramData.requestId);
        }
        if (paramData.status) {
            params = params.append('status', paramData.status);
        }

        return this.http.get(`${this.apiUrl}/request`, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public getJobSettings(): Observable<any> {
        return this.http.get(`${this.apiUrl}/setting`).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public postJobRequest(request: any): Observable<any> {
        return this.http.post(`${this.apiUrl}/request`, request).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }
}
