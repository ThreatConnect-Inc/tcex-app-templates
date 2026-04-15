import { catchError, finalize, mergeMap, tap } from 'rxjs';

import { Component, Input, OnChanges, OnInit, SimpleChanges, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { MenuItem, Table } from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';
import { NxPaginator } from 'src/app/modules/nx-utils/nx-paginator';
import { NxTable } from 'src/app/modules/nx-utils/nx-table';
import { BaseHttpErrorResponse } from 'src/app/service/base-service/base-http-error-response';
import { BatchErrorService } from 'src/app/service/batch-errors-service/batch-error.service';
import { HttpResponse } from '@angular/common/http';

@Component({
    selector: 'batch-errors-table',
    templateUrl: './batch-errors-table.component.html',
    styleUrl: './batch-errors-table.component.scss',
})
export class BatchErrorsTableComponent implements OnChanges, OnInit {
    // ui framework settings
    protected readonly featureVersion: FeatureVersion = 'new-design';

    @Input() errorCode: string;
    @Input() jobId: string;

    // search
    reason?: string;

    // table
    @ViewChild('dataTable') tableComponent: Table;

    paginator = new NxPaginator({ pageChangeCallback: this.getBatchErrorData.bind(this) });
    table = new NxTable({
        dataColumns: [
            { field: 'requestId', header: 'Job ID' },
            { field: 'dateAdded', header: 'Date Added' },
            { field: 'reason', header: 'Reason' },
        ],
    });

    dataSubscription = null;

    // export
    exportLoading: boolean = false;
    exportMenuItems: MenuItem[] = [
        {
            value: 'Export as CSV',
            // icon: 'file_download',
            command: () => this.handleExportClick('csv'),
        },
        {
            value: 'Export as JSON',
            // icon: 'file_download',
            command: () => this.handleExportClick('json'),
        },
    ];

    private initialized = false;

    constructor(
        private batchErrorService: BatchErrorService,
        private activeRoute: ActivatedRoute,
    ) {}
    ngOnInit(): void {
        this.dataSubscription = this.activeRoute.queryParams
            .pipe(
                tap((params) => {
                    this.jobId = params['jobId'];
                    this.initialized = true;
                }),
                mergeMap(() => {
                    return this.getBatchErrorData$().pipe(
                        catchError((error: BaseHttpErrorResponse) => {
                            return [];
                        }),
                    );
                }),
            )
            .subscribe();
    }

    ngOnChanges(changes: SimpleChanges): void {
        if (this.initialized) {
            this.reason = null;
            this.paginator.reset();
            this.table.data = [];
            this.table.dataLoaded = false;
            this.getBatchErrorData();
        }
    }

    getBatchErrorData() {
        // set dataLoaded to false to show loading spinner on pagination
        // this.table.dataLoaded = false;
        if (this.dataSubscription) {
            this.dataSubscription.unsubscribe();
        }

        this.dataSubscription = this.getBatchErrorData$()
            .pipe(
                catchError((error: BaseHttpErrorResponse) => {
                    return [];
                }),
            )
            .subscribe();
    }

    handleExportClick(format: 'csv' | 'json') {
        this.exportLoading = true;
        this.batchErrorService
            .export({
                errorCode: this.errorCode !== 'All' ? this.errorCode : undefined,
                reason: this.reason,
                request_id: this.jobId,
                format,
            })
            .pipe(
                tap((response: HttpResponse<Blob>) => {
                    const contentDisposition = response.headers.get('content-disposition');
                    if (!contentDisposition) {
                        throw new Error('Missing content-disposition header');
                    }
                    const filename = contentDisposition.split('filename')[1].split('=')[1].trim();
                    const downloadLink = document.createElement('a');
                    downloadLink.href = window.URL.createObjectURL(
                        new Blob([response.body], { type: response.body.type }),
                    );
                    downloadLink.setAttribute('download', filename);
                    document.body.appendChild(downloadLink);
                    downloadLink.click();
                    document.body.removeChild(downloadLink);
                }),
                catchError(() => {
                    return [];
                }),
                finalize(() => {
                    this.exportLoading = false;
                }),
            )
            .subscribe();
    }

    handleSearchClick() {
        this.table.dataLoaded = false;
        this.tableComponent.first = 0;
        this.paginator.pageIndex = 0;
        this.getBatchErrorData();
    }

    handleReasonInput($event) {
        this.reason = $event;
    }

    private getBatchErrorData$() {
        return this.batchErrorService
            .getCollection({
                ...this.paginator.paginationParams,
                errorCode: this.errorCode !== 'All' ? this.errorCode : undefined,
                reason: this.reason,
                request_id: this.jobId,
                sort: 'created',
                sortOrder: 'desc',
            })
            .pipe(
                tap((resp) => {
                    this.table.data = resp.data;
                    this.table.dataLoaded = true;
                    if (resp.totalCount) {
                        this.paginator.pageTotal = resp.totalCount;
                    }
                }),
            );
    }
}
