import { Observable } from 'rxjs';

import { Injectable } from '@angular/core';

import { ApiResponseCollection } from '../api-response-interface';
import { BaseService } from '../base-service/base.service';
import { TIProcessingMetric } from './metric-interface';

@Injectable({
    providedIn: 'root',
})
export class MetricsService extends BaseService {
    apiUrl: string = '/api/metric';

    getProcessingCollection(params: any): Observable<any> {
        return this.http.get<ApiResponseCollection<TIProcessingMetric>>(
            `${this.apiUrl}/processing`,
            { params: this.convertToHttpParams(params) },
        );
    }

    getTasksCollection(): Observable<any> {
        return this.http.get(`${this.apiUrl}/task`);
    }
}
