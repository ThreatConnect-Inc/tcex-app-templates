import { BehaviorSubject, Observable, tap } from 'rxjs';

import { Component, OnInit } from '@angular/core';

import { MetricService } from '../../service/metric-service/metric.service';
import { GetTiProcessingMetricsParam } from '../../service/metric-service/param-interface';

@Component({
    selector: 'app-dashboard',
    templateUrl: './dashboard.component.html',
    styleUrls: ['./dashboard.component.less'],
})
export class DashboardComponent implements OnInit {
    // behavior subjects
    private _MetricDataSubject = new BehaviorSubject([]);

    // card data
    metricData$: Observable<any> = this._MetricDataSubject.asObservable();

    constructor(private metricService: MetricService) {}

    ngOnInit(): void {
        this.loadJobRequestData();
    }

    loadJobRequestData() {
        const paramData: GetTiProcessingMetricsParam = {};
        this.metricService
            .getMetricProcessing(paramData)
            .pipe(
                tap((response: any) => {
                    console.log('response', response);
                    this._MetricDataSubject.next(response.data);
                }),
            )
            .subscribe();
    }
}
