import { catchError, Observable, of } from 'rxjs';

import { Injectable } from '@angular/core';

import { BaseService } from '../base-service/base.service';
import { GetReportBatchErrorsParam } from './param-interface';
import { PipeErrorResponse } from './pipe-error-interface';

@Injectable({
    providedIn: 'root',
})
export class ReportService extends BaseService {
    apiUrl: string = 'api/report';

    public getReportBatchErrors(
        paramData: GetReportBatchErrorsParam,
    ): Observable<PipeErrorResponse | null> {
        const params = this.convertToHttpParams({
            limit: paramData.limit || 20,
            offset: paramData.offset || 0,
            sort: paramData.sort || 'id',
            sort_order: paramData.sortOrder || 'desc',
            ...(paramData.jobId ? { request_id: paramData.jobId } : {}),
        });

        return this.http
            .get<PipeErrorResponse>(`${this.apiUrl}/batch-error`, { params })
            .pipe(
                catchError(() => {
                    return of(null);
                }),
            );
    }
}
