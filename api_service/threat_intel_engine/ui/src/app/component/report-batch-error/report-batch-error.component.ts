import { BehaviorSubject, interval, Observable, tap } from 'rxjs';

import { Component, OnInit, ViewChild } from '@angular/core';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';

import { GetReportBatchErrorsParam } from '../../service/report-service/param-interface';
import { ReportService } from '../../service/report-service/report.service';

@Component({
    selector: 'report-batch-error',
    templateUrl: './report-batch-error.component.html',
    styleUrls: ['./report-batch-error.component.less'],
})
export class ReportBatchErrorComponent implements OnInit {
    @ViewChild(MatPaginator) paginator: MatPaginator;
    @ViewChild(MatSort) sort: MatSort;

    // class properties
    private auto_refresh: any;

    // behavior subjects
    private _BatchErrorDataSubject = new BehaviorSubject([]);
    private _BatchErrorCountSubject = new BehaviorSubject(0);

    // table data
    dataSource$: Observable<any> = this._BatchErrorDataSubject.asObservable();
    displayedColumns: string[] = ['request_id', 'date_added', 'code', 'message', 'reason'];

    // form inputs -> query params
    requestId: string;

    // pagination | sorting
    pageIndex: number = 0; // paginator index
    pageSize: number = 20; // paginator and api result limit
    pageTotal$: Observable<number> = this._BatchErrorCountSubject.asObservable();

    constructor(private reportService: ReportService) {}

    ngOnInit(): void {
        // load the data
        this.loadBatchErrorData();

        // auto reload the data
        this.auto_refresh = interval(30 * 1000).subscribe(() => this.loadBatchErrorData());
    }

    ngOnDestroy(): void {
        this.auto_refresh.unsubscribe();
    }

    loadBatchErrorData() {
        const paramData: GetReportBatchErrorsParam = {
            requestId: this.requestId,
            // pagination|sorting
            limit: this.pageSize,
            offset: this.pageIndex * this.pageSize, // pageOffset
            sort: 'request_id',
            sortOrder: 'asc',
        };
        this.reportService
            .getReportBatchErrors(paramData)
            .pipe(
                tap((response: any) => {
                    this._BatchErrorDataSubject.next(response.data);
                    this._BatchErrorCountSubject.next(response.total_count);
                }),
            )
            .subscribe();
    }

    pageChanged(event: any) {
        this.pageIndex = event.pageIndex;
        this.pageSize = event.pageSize;
        this.loadBatchErrorData();
    }
}
