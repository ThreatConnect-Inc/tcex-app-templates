import { catchError, Observable, of } from 'rxjs';

import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

import { BaseService } from '../base-service/base.service';

@Injectable({
    providedIn: 'root',
})
export class DownloadService extends BaseService {
    apiUrl: string = `${this.basePrefix}api/download/falcon-ti`;

    constructor(private http: HttpClient, router: Router, snackBar: MatSnackBar) {
        super(router, snackBar);
    }
    downloadTi(request: {
        ids: string;
        type: string;
        enrich: boolean;
        convert: boolean;
    }): Observable<any> {
        const params = new HttpParams().appendAll(request);

        return this.http.get(`${this.apiUrl}`, { params: params, observe: 'response' }).pipe(
            catchError((err) => {
                this.errorHandler(err);
                return of();
            }),
        );
    }
}
