import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { BehaviorSubject, map, tap } from 'rxjs';
import { TIProcessingMetric } from 'src/app/service/metrics-service/metric-interface';
import { MetricsService } from 'src/app/service/metrics-service/metrics.service';

@Component({
    selector: 'dashboard',
    templateUrl: './dashboard.component.html',
    styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
    private readonly destroyRef = inject(DestroyRef);

    metricsSubject = new BehaviorSubject<TIProcessingMetric[]>([]);
    metrics$ = this.metricsSubject.asObservable();

    view = [1200];
    valueFormatter = (value) => this.nFormatter(value, 1);

    constructor(private metricsService: MetricsService) {}

    ngOnInit(): void {
        this.metricsService
            .getProcessingCollection({})
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                map((data) => {
                    return data.data.map((metric: TIProcessingMetric) => {
                        return {
                            name: metric.tiType,
                            value: metric.tiCount,
                        };
                    });
                }),
                tap((data) => {
                    this.metricsSubject.next(data);
                }),
            )
            .subscribe();

        this.view = [window.innerWidth * 0.7, window.innerHeight * 0.7];
    }

    nFormatter(num: number, digits: number): string {
        const lookup = [
            { value: 1, symbol: '' },
            { value: 1e3, symbol: 'K' },
            { value: 1e6, symbol: 'M' },
            { value: 1e9, symbol: 'G' },
            { value: 1e12, symbol: 'T' },
            { value: 1e15, symbol: 'P' },
            { value: 1e18, symbol: 'E' },
        ];
        const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
        var item = lookup
            .slice()
            .reverse()
            .find(function (item) {
                return num >= item.value;
            });
        return item ? (num / item.value).toFixed(digits).replace(rx, '$1') + item.symbol : '0';
    }
}
