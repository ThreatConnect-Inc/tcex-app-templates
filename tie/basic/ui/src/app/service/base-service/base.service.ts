import { throwError } from 'rxjs';

import { formatDate } from '@angular/common';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { ErrorHandler, inject, Injectable } from '@angular/core';
import { Router } from '@angular/router';

import { BaseHttpErrorResponse } from './base-http-error-response';

// generic interface for query params
interface QueryParamObject {
    [key: string]: any;
}

@Injectable({
    providedIn: 'root',
})
export abstract class BaseService {
    protected http: HttpClient = inject(HttpClient);
    private _errorHandler: ErrorHandler = inject(ErrorHandler);
    constructor(public router: Router) {}

    protected errorHandler(err: any): void {
        this._errorHandler.handleError(err);
    }

    public convertToHttpParams(queryParams: QueryParamObject): HttpParams {
        let httpParams = this.defaultParams();

        // Iterate over the properties of the queryParams object
        for (const key in queryParams) {
            if (queryParams.hasOwnProperty(key)) {
                let value = queryParams[key];

                if (value === undefined || value === null) {
                    continue;
                }

                // Check the type of the value and convert if needed
                if (typeof value === 'number' || typeof value === 'boolean') {
                    // Convert number and boolean values to strings
                    httpParams = httpParams.set(key, value.toString());
                } else if (typeof value === 'string') {
                    // Use the value as is if it's a string
                    httpParams = httpParams.set(key, value);
                } else {
                    // Handle other data types gracefully (e.g., by converting to JSON)
                    try {
                        const jsonValue = JSON.stringify(value);
                        httpParams = httpParams.set(key, jsonValue);
                    } catch (error) {
                        // Handle JSON serialization error, or throw an error if needed
                        throw new Error(
                            `Invalid type for query parameter '${key}': ${typeof value}`,
                        );
                    }
                }
            }
        }
        return httpParams;
    }

    public dateToApiString(date: Date) {
        // the api expects dates in the format yyyy-MM-dd
        return formatDate(date, 'yyyy-MM-dd', 'en-GB');
    }

    public defaultParams(): HttpParams {
        let params = this.params();
        params = params.set('byAlias', true);
        return params;
    }

    public params(): HttpParams {
        return new HttpParams();
    }
}
