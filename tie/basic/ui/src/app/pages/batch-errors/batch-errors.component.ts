import { BehaviorSubject, catchError, map, merge, mergeMap, tap } from 'rxjs';

import { Component, DestroyRef, inject, OnInit, ViewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { CheckboxState, MenuItemEvent, MenuItemType, Table } from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';
import { NxPaginator } from 'src/app/modules/nx-utils/nx-paginator';
import { NxTable } from 'src/app/modules/nx-utils/nx-table';

import { BatchErrorService } from 'src/app/service/batch-errors-service/batch-error.service';

@Component({
    selector: 'batch-errors',
    templateUrl: './batch-errors.component.html',
    styleUrl: './batch-errors.component.scss',
})
export class BatchErrorsComponent implements OnInit {
    protected readonly featureVersion: FeatureVersion = 'new-design';
    private readonly destroyRef = inject(DestroyRef);

    countsSubject = new BehaviorSubject<{ name: string; value: number }[]>([]);
    counts$ = this.countsSubject.asObservable();

    view = [1200];
    valueFormatter = (value) => this.nFormatter(value, 1);

    jobId?: string;
    searchedJobId: string = null;

    showSideDrawer = false;
    selectedErrorCode: string = undefined;
    sidebarTitle: string;
    dataSubscription = null;
    dataLoading = true;
    constructor(
        private batchErrorService: BatchErrorService,
        private activeRoute: ActivatedRoute,
    ) {}

    ngOnInit(): void {
        this.activeRoute.queryParams
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((params) => {
                    this.jobId = params['jobId'];
                }),
                mergeMap(() => this.getBatchErrorCountData$()),
            )
            .subscribe();
    }

    getBatchErrorCountData() {
        if (this.dataSubscription) {
            this.dataSubscription.unsubscribe();
        }

        this.dataSubscription = this.getBatchErrorCountData$().subscribe();
    }

    handleClearClick() {
        this.jobId = null;
        this.getBatchErrorCountData();
    }

    handleJobIdChanged($event) {
        this.jobId = $event;
    }

    handleSearchClick() {
        this.getBatchErrorCountData();
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

    onCountCardClicked(event) {
        this.selectedErrorCode = event.extra.code;
        this.showSideDrawer = true;
        this.sidebarTitle =
            event.extra.code.toLowerCase() !== 'all' ? `${event.name}s` : 'All Batch Errors';
    }

    private getBatchErrorCountData$() {
        this.dataLoading = true;
        this.searchedJobId = this.jobId;
        return this.batchErrorService.getCounts({ request_id: this.jobId }).pipe(
            map((data) => {
                return data.data.map((c) => {
                    return {
                        name: c.error,
                        value: c.count,
                        extra: { code: c.code },
                    };
                });
            }),
            tap((data) => {
                this.countsSubject.next(data);
                this.dataLoading = false;
            }),
        );
    }
}
