import { catchError, Observable, of } from 'rxjs';

import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

import { BaseService } from '../base-service/base.service';

@Injectable({
    providedIn: 'root',
})
export class TaskService extends BaseService {
    apiUrl: string = `${this.basePrefix}api/task`;

    constructor(private http: HttpClient, router: Router, snackBar: MatSnackBar) {
        super(router, snackBar);
    }

    public getTasks(): Observable<any> {
        return this.http.get(this.apiUrl).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public getTaskStatusOptions(): Observable<any> {
        return this.http.get(`${this.apiUrl}/status`).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public killTask(taskName: string): Observable<any> {
        return this.http.delete(`${this.apiUrl}/${taskName}`).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public pauseTask(taskName: string): Observable<any> {
        const params = new HttpParams().appendAll({ pause: true });
        return this.http.put(`${this.apiUrl}/${taskName}`, null, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public resumeTask(taskName: string): Observable<any> {
        const params = new HttpParams().appendAll({ pause: false });
        return this.http.put(`${this.apiUrl}/${taskName}`, null, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }

    public runTask(taskName: string): Observable<any> {
        const params = new HttpParams().appendAll({ run: true });
        return this.http.put(`${this.apiUrl}/${taskName}`, null, { params: params }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }
}
