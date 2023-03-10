import { throwError } from 'rxjs';

import { HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

@Injectable({
    providedIn: 'root',
})
export abstract class BaseService {
    // basePrefix: string = '../';
    basePrefix: string = '';

    constructor(public router: Router, private snackBar: MatSnackBar) {}

    public standardParams(paramData: any): HttpParams {
        let params = new HttpParams();
        // standard
        if (paramData.exclude) {
            params = params.append('exclude', paramData.exclude);
        }
        if (paramData.excludeDefaults !== undefined) {
            params = params.append('exclude_defaults', paramData.excludeDefaults);
        }
        if (paramData.excludeNone !== undefined) {
            params = params.append('exclude_none', paramData.excludeNone);
        }
        if (paramData.excludeUnset !== undefined) {
            params = params.append('exclude_unset', paramData.excludeUnset);
        }
        if (paramData.field) {
            params = params.append('field', paramData.field);
        }
        return params;
    }

    public params(): HttpParams {
        return new HttpParams();
    }

    public paginationParams(paramData: any): HttpParams {
        return this.standardParams(paramData).appendAll({
            limit: (paramData.limit || 100).toString(),
            offset: (paramData.offset || 0).toString(),
            sort: paramData.sort || 'id',
            sort_order: paramData.sortOrder || 'asc',
        });
    }

    errorHandler(error: HttpErrorResponse) {
        // console.log(error);
        let errorMessage = '';

        // if (error.error instanceof ErrorEvent) {
        //     // client-side error
        //     errorMessage = error.error.message;
        // } else {
        //     // server-side error
        //     errorMessage = error.error.description;
        // }

        // switch (error.status) {
        //     case 404:
        //         this.router.navigate(['/']);
        //         break;
        // }

        // console.log(errorMessage);
        this.snackBar.open(`${errorMessage}`, `${error.statusText}`, {
            duration: 10000,
        });
        return throwError(() => {
            return errorMessage;
        });
    }
}
