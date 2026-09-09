import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { ButtonTheme, DrawerSide } from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';
import { mergeMap, tap } from 'rxjs/operators';

import { NxPaginator } from '../../modules/nx-utils/nx-paginator';
import { NxTable } from '../../modules/nx-utils/nx-table';
import { AppService } from '../../service/app-service/app.service';
import { PipeError, PipeErrorResponse } from '../../service/report-service/pipe-error-interface';
import { ReportService } from '../../service/report-service/report.service';

@Component({
    selector: 'app-egress-errors',
    templateUrl: './egress-errors.component.html',
    styleUrls: ['./egress-errors.component.scss'],
    standalone: false,
})
export class EgressErrorsComponent implements OnInit {
    protected readonly featureVersion: FeatureVersion = 'new-design';
    protected readonly ButtonTheme = ButtonTheme;
    protected readonly DrawerSide = DrawerSide;
    private readonly destroyRef = inject(DestroyRef);

    table = new NxTable({ dataColumns: [] });
    detailFields: { field: string; label: string; type?: string }[] = [];

    paginator = new NxPaginator({
        pageSize: 20,
        pageChangeCallback: this.loadErrors.bind(this),
    });

    jobId: string = '';
    loading = false;

    showSideDrawer = false;
    sideDrawerTitle = 'Error Details';
    selectedError: PipeError | null = null;

    constructor(
        private reportService: ReportService,
        private appService: AppService,
        private activatedRoute: ActivatedRoute,
    ) {}

    ngOnInit(): void {
        // Load column/detail config from the backend
        this.appService
            .getConfig()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((config: any) => {
                const cfg = config?.ui?.egressErrors;
                if (cfg?.columns) {
                    this.table = new NxTable({ dataColumns: cfg.columns });
                }
                if (cfg?.details) {
                    this.detailFields = cfg.details;
                }
            });

        // Load initial data (respecting query param pre-filter)
        this.activatedRoute.queryParams
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((params) => {
                    if (params['request_id']) {
                        this.jobId = params['request_id'];
                    }
                }),
                mergeMap(() => this.getErrors$()),
            )
            .subscribe();
    }

    handleJobIdChange(val: string): void {
        this.jobId = val || '';
    }

    handleSearchClick(): void {
        this.paginator.pageTotalReset = 0;
        this.loadErrors();
    }

    handleClearClick(): void {
        this.jobId = '';
        this.loadErrors();
    }

    handleRowClick(error: PipeError): void {
        this.selectedError = error;
        this.showSideDrawer = true;
    }

    handleSidenavChange(newValue: boolean): void {
        if (newValue !== this.showSideDrawer) {
            this.showSideDrawer = newValue;
        }
    }

    loadErrors(): void {
        this.loading = true;
        this.table.dataLoaded = false;
        this.getErrors$().pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
    }

    private getErrors$() {
        return this.reportService
            .getReportBatchErrors({
                limit: this.paginator.pageSize,
                offset: this.paginator.offset,
                sort: 'id',
                sortOrder: 'desc',
                jobId: this.jobId || undefined,
            })
            .pipe(
                tap((resp: PipeErrorResponse | null) => {
                    this.loading = false;
                    if (resp) {
                        this.table.data = resp.data || [];
                        const total = resp.totalCount ?? resp.count;
                        if (total !== undefined) {
                            this.paginator.pageTotal = total;
                        }
                    }
                    this.table.dataLoaded = true;
                }),
            );
    }
}
