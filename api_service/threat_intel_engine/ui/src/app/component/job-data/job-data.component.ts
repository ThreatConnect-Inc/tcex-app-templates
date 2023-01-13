import { BehaviorSubject, interval, Observable, tap } from 'rxjs';

import { formatNumber } from '@angular/common';
import { Component, Inject, LOCALE_ID, OnInit, ViewChild } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatPaginator } from '@angular/material/paginator';
import { MatDrawer } from '@angular/material/sidenav';
import { MatSort } from '@angular/material/sort';

import { AddRequestDialogComponent } from '../../component/add-request-dialog/add-request-dialog.component';
import { JobService } from '../../service/job-service/job.service';
import { GetJobRequestParam } from '../../service/job-service/param-interface';

@Component({
    selector: 'job-data',
    templateUrl: './job-data.component.html',
    styleUrls: ['./job-data.component.less'],
})
export class JobDataComponent implements OnInit {
    @ViewChild(MatDrawer) drawer: MatDrawer;
    @ViewChild(MatPaginator) paginator: MatPaginator;
    @ViewChild(MatSort) sort: MatSort;

    selectedRequest?: any;
    paginatorDisabled: boolean = false;

    // class properties
    private auto_refresh: any;

    // behavior subjects
    private _JobRequestDataSubject = new BehaviorSubject([]);
    private _JobRequestCountSubject = new BehaviorSubject(0);

    // table data
    dataSource$: Observable<any> = this._JobRequestDataSubject.asObservable();
    displayedColumns: string[] = [
        'request-id',
        'job-type',
        'group-count',
        'indicator-count',
        // 'date-queued',
        // 'date-started',
        // 'date-failed',
        // 'date-completed',
        'last-modified-filter-start',
        'last-modified-filter-end',
        // 'status-flow',
        'status',
    ];

    // details drawer
    detailsData = [
        { name: 'job_type', formatType: null },
        { name: 'request_id', formatType: null },
        { name: 'last_modified_filter_start', formatType: 'date' },
        { name: 'last_modified_filter_end', formatType: 'date' },
        { name: 'group_types', formatType: null },
        { name: 'indicator_types', formatType: null },
        { name: 'status', formatType: null },
        { name: 'date_queued', formatType: 'date' },
        { name: 'date_started', formatType: 'date' },
        { name: 'date_download_start', formatType: 'date' },
        { name: 'date_download_complete', formatType: 'date' },
        { name: 'download_runtime', formatType: null },
        { name: 'date_convert_start', formatType: 'date' },
        { name: 'date_convert_complete', formatType: 'date' },
        { name: 'convert_runtime', formatType: null },
        { name: 'date_upload_start', formatType: 'date' },
        { name: 'date_upload_complete', formatType: 'date' },
        { name: 'upload_runtime', formatType: null },
        { name: 'date_complete', formatType: 'date' },
        { name: 'total_runtime', formatType: null },
        { name: 'count_download_group', formatType: 'number' },
        { name: 'count_batch_group_success', formatType: 'number' },
        { name: 'count_download_indicator', formatType: 'number' },
        { name: 'count_batch_indicator_success', formatType: 'number' },
        { name: 'count_batch_error', formatType: 'number' },
        { name: 'date_failed', formatType: 'date' },
    ];

    // form inputs -> query params
    jobType: string;
    requestId: string;
    status: string;

    // pagination | sorting
    pageIndex: number = 0; // paginator index
    pageSize: number = 20; // paginator and api result limit
    pageTotal$: Observable<number> = this._JobRequestCountSubject.asObservable();

    constructor(
        @Inject(LOCALE_ID) public locale: string,
        private dialog: MatDialog,
        private jobService: JobService,
    ) {}

    ngOnInit(): void {
        // load the data
        this.loadJobRequestData();

        // auto reload the data
        this.auto_refresh = interval(20 * 1000).subscribe(() => this.loadJobRequestData());
    }

    ngOnDestroy(): void {
        this.auto_refresh.unsubscribe();
    }

    closeDrawer() {
        this.selectedRequest = null;
        if (this.drawer) {
            this.drawer.close();
        }
    }

    formatSettings(element: any): string {
        return (
            'Job Settings\n\n' +
            // 'Download Start: ' +
            // element.last_modified_filter_start +
            // '\n' +
            // 'Download End: ' +
            // element.last_modified_filter_end +
            // '\n' +
            // 'Group Download Count: ' +
            // element.count_download_group +
            // '\n' +
            // 'Group Batch Count: ' +
            // element.count_batch_group_success +
            // '\n' +
            // 'Indicator Download Count: ' +
            // element.count_download_indicator +
            // '\n' +
            // 'Indicator Batch Count: ' +
            // element.count_batch_indicator_success +
            // '\n' +
            'Batch Errors: ' +
            element.count_batch_error
        );
    }

    formatGroupCounts(element: any): string {
        return (
            'Download Count: ' +
            formatNumber(element.count_download_group, this.locale, '1.0-0') +
            '\n' +
            'Upload Count: ' +
            formatNumber(element.count_batch_group_success, this.locale, '1.0-0')
        );
    }

    formatIndicatorCounts(element: any): string {
        return (
            'Download Count: ' +
            formatNumber(element.count_download_indicator, this.locale, '1.0-0') +
            '\n' +
            'Upload Count: ' +
            formatNumber(element.count_batch_indicator_success, this.locale, '1.0-0')
        );
    }

    loadJobRequestData(searchData?: any) {
        this.updateData(searchData);

        const paramData: GetJobRequestParam = {
            jobType: this.jobType,
            requestId: this.requestId,
            status: this.status,
            // pagination|sorting
            limit: this.pageSize,
            offset: this.pageIndex * this.pageSize, // pageOffset
            sort: 'date_queued',
            sortOrder: 'desc',
        };
        console.log('paramData', paramData);
        console.log('searchData', searchData);
        this.jobService
            .getJobRequests(paramData)
            .pipe(
                tap((response: any) => {
                    this._JobRequestDataSubject.next(response.data);
                    this._JobRequestCountSubject.next(response.total_count);
                }),
            )
            .subscribe();
    }

    pageChanged(event: any) {
        this.paginatorDisabled = true;
        setTimeout(() => {
            this.closeDrawer();
            this.pageIndex = event.pageIndex;
            this.pageSize = event.pageSize;
            this.loadJobRequestData();
            this.paginatorDisabled = false;
        }, 500);
    }

    showAddRequestDialog() {
        this.dialog
            .open(AddRequestDialogComponent, {
                disableClose: true,
                // height: '800px',
                // width: '800px',
            })
            .afterClosed()
            .subscribe((result) => {
                if (!result) return;
                this.jobService.postJobRequest(result).subscribe(() => this.loadJobRequestData());
            });
    }

    showDetailsForRequest(request: any) {
        if (request.request_id === this.selectedRequest?.request_id) {
            this.closeDrawer();
        } else {
            this.selectedRequest = request;
            this.drawer.open();
        }
    }

    updateData(searchData: any) {
        for (let key in searchData) {
            this[key] = searchData[key];
        }
    }
}
