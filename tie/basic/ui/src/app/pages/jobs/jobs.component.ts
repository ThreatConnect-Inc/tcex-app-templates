import { BehaviorSubject, EMPTY, catchError, finalize, interval, map, mergeMap, tap } from 'rxjs';

import { Component, DestroyRef, inject, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { CheckboxState, MenuItemEvent, MenuItemType, Table } from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';
import { GeneratedFormComponent } from 'src/app/components/generated-form/generated-form.component';
import { NxPaginator } from 'src/app/modules/nx-utils/nx-paginator';
import { NxTable } from 'src/app/modules/nx-utils/nx-table';
import { AlertMessageService } from 'src/app/service/alert-message-service/alert-message.service';
import { AppService, FieldDisplay, Form } from 'src/app/service/app-service/app.service';
import { BaseHttpErrorResponse } from 'src/app/service/base-service/base-http-error-response';
import { Job } from 'src/app/service/jobs-service/jobs-interface';
import { JobsService } from 'src/app/service/jobs-service/jobs.service';
import { TaskService } from 'src/app/service/tasks-service/tasks.service';

export enum SideDrawerContent {
    DETAILS,
    DOWNLOAD,
    ADD_JOB,
}

@Component({
    selector: 'jobs',
    templateUrl: './jobs.component.html',
    styleUrl: './jobs.component.scss',
})
export class JobsComponent implements OnDestroy, OnInit {
    // ui framework settings
    protected readonly featureVersion: FeatureVersion = 'new-design';

    // global values
    protected readonly destroyRef = inject(DestroyRef);

    @ViewChild('form') form: GeneratedFormComponent;
    adhocFormConfig: Form;

    @ViewChild('filterForm') filterForm: GeneratedFormComponent;
    filterFormConfig: Form;

    table: NxTable = null;
    detailsData?: any;
    enableAddJob: boolean = true; // Default to enabled if not specified in config

    multiSelectAdvancedSettings = {
        headerSelectAll: true,
        filter: true,
        filterPlaceholder: 'Search...',
        filterNoResults: 'No results found',
    };
    jobTypeMenuItems: any[] = [
        {
            text: 'Scheduled',
            value: 'scheduled',
            type: MenuItemType.MultiSelect,
            checked: CheckboxState.Checked,
        },
        {
            text: 'Ad-Hoc',
            value: 'ad-hoc',
            type: MenuItemType.MultiSelect,
            checked: CheckboxState.Checked,
        },
    ];

    jobStatusesLoaded = false;
    jobStatusMenuItems: any[] = [];

    // table
    @ViewChild('dataTable') tableComponent: Table;

    paginator = new NxPaginator({ pageChangeCallback: this.getJobData.bind(this) });

    menuItemsWithDownload = [
        { label: 'Details', value: 'details', disabled: false },
        {
            label: 'Download Files',
            value: 'download',
            title: 'Only available for finished jobs.',
        },
        {
            label: 'Batch Errors',
            value: 'batchErrors',
        },
    ];

    // private refreshTimer$ = interval(1000 * 60 * 5);
    private refreshTimer$ = interval(1000 * 20);

    private refreshTimerSubscription: any;

    // download sidebar
    private downloadFilesSubject: BehaviorSubject<any> = new BehaviorSubject<any[]>([]);
    downloadFiles$ = this.downloadFilesSubject.asObservable();

    // side nav settings
    protected readonly SideDrawerContent = SideDrawerContent;

    showSideDrawer: boolean = false;
    showSideDrawerTitle: string = 'Job Details';
    sideDrawerContent: SideDrawerContent;
    selectedJob: Job;

    constructor(
        private alertMessageService: AlertMessageService,
        private jobsService: JobsService,
        private router: Router,
        private taskService: TaskService,
        private appService: AppService,
    ) {}

    ngOnDestroy(): void {
        this.refreshTimerSubscription.unsubscribe();
    }

    ngOnInit() {
        this.getTaskStatuses();

        this.refreshTimerSubscription = this.refreshTimer$
            .pipe(mergeMap(() => this.getJobData$()))
            .subscribe();

        this.appService
            .getConfig()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((uiConfig) => {
                    this.table = this.buildTable(uiConfig?.ui?.jobTable?.columns);
                    this.detailsData = uiConfig?.ui?.jobTable?.details;
                    this.adhocFormConfig = uiConfig?.ui?.adhocRequest?.form;
                    this.filterFormConfig = uiConfig.ui.jobTable.filters;
                    // Read feature flag, default to true if not specified
                    this.enableAddJob = uiConfig?.ui?.global?.featureFlags?.enableAddJob ?? true;
                }),
                mergeMap(() => this.getJobData$()),
            )
            .subscribe();

        // build this.table data based on ui config
    }

    splitAndClean(input: string | undefined | null): string[] {
        if (!input) {
            return [];
        }
        return input.split('|').filter((value) => value.trim() !== '');
    }

    mapChoices(field: { type: string; default: string; choices?: string[] }) {
        if (field.type !== 'select' && field.type !== 'multi-select') {
            return [];
        }

        const defaultAsList =
            field.default?.split('|').filter((value) => value.trim() !== '') || [];
        return (
            field.choices?.map((choice: string) => ({
                text: choice,
                value: choice,
                type: field.type === 'select' ? MenuItemType.Default : MenuItemType.MultiSelect,
                checked: defaultAsList.includes(choice)
                    ? CheckboxState.Checked
                    : CheckboxState.UnChecked,
            })) || []
        );
    }

    buildTable(columns: FieldDisplay[]): NxTable {
        let table: NxTable | undefined;
        if (!columns) {
            console.error('Job table columns configuration is missing in app-config.json');
            return;
        }

        table = new NxTable({
            dataColumns: columns.map((column) => ({
                field: column.field,
                header: column.label,
                fieldDisplay: column,
            })),
        });
        return table;
    }

    getJobData() {
        // set dataLoaded to false to show loading spinner on pagination
        this.table.dataLoaded = false;
        this.getJobData$()
            .pipe(
                catchError((error: BaseHttpErrorResponse) => {
                    this.table.dataLoaded = true;
                    return EMPTY;
                }),
            )
            .subscribe({});
    }

    handleAddJobClick() {
        this.showSideDrawerTitle = 'Add Job';

        this.sideDrawerContent = SideDrawerContent.ADD_JOB;
        this.showSideDrawer = true;
    }

    handleNestedMenuSelection(event_, job: Job) {
        switch (event_) {
            case 'batchErrors':
                this.router.navigate(['/batchErrors'], {
                    queryParams: {
                        jobId: job.requestId,
                        errorCode: 'All',
                    },
                });
                break;
            case 'details':
                this.showSideDrawerTitle = 'Job Details';

                this.sideDrawerContent = SideDrawerContent.DETAILS;
                this.selectedJob = job;
                this.showSideDrawer = true;
                break;
            case 'download':
                this.showSideDrawerTitle = 'Download Job Files';
                this.sideDrawerContent = SideDrawerContent.DOWNLOAD;
                this.selectedJob = job;
                this.showSideDrawer = true;
                this.getJobFiles();
        }
    }

    handleSearchClick() {
        this.table.dataLoaded = false;
        this.tableComponent.first = 0;
        this.paginator.pageIndex = 0;
        this.getJobData();
    }

    handleSidenavChange(newValue) {
        if (newValue !== this.showSideDrawer) {
            this.showSideDrawer = newValue;
        }
    }

    private getTaskStatuses() {
        this.taskService
            .getTaskStatuses()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((resp) => {
                    const menuItems = resp.data.map((status) => {
                        return {
                            checked: CheckboxState.Checked,
                            text: status,
                            value: status,
                            type: MenuItemType.MultiSelect,
                        };
                    });
                    this.jobStatusMenuItems = menuItems;
                    this.jobStatusesLoaded = true;
                }),
            )
            .subscribe();
    }

    private transformFilterValues(filterValues: Record<string, unknown>): Record<string, unknown> {
        const fields = this.filterFormConfig.fields as any;
        return Object.entries(filterValues).reduce(
            (acc, [key, val]) => {
                const fieldConfig = fields?.find((f) => f.name === key);

                // Only do special handling if it's an array field and val is an actual array.
                if (fieldConfig?.type === 'multi-select' && Array.isArray(val)) {
                    // 1) If *all* possible choices are selected, we skip adding this filter altogether.
                    if (
                        Array.isArray(fieldConfig.choices) &&
                        val.length === fieldConfig.choices.length
                    ) {
                        return acc; // Skip this property (do not add to `acc`)
                    }

                    // 2) If it's a non-empty array but not the full set, join with commas.
                    if (val.length > 0) {
                        acc[key] = val.join(',');
                    }
                    // If it's empty, we do nothing, effectively skipping it as well.
                    return acc;
                }

                // For anything that isn't an array (or doesn't match the config), just copy as-is.
                if (val) {
                    acc[key] = val;
                }
                return acc;
            },
            {} as Record<string, unknown>,
        );
    }

    private getJobData$() {
        const filterValues = this.filterForm?.getValues() ?? {};

        const transformedFilterValues = this.transformFilterValues(filterValues);

        return this.jobsService
            .getCollection({
                ...this.paginator.paginationParams,
                ...transformedFilterValues,
                sort: 'created',
                sort_order: 'desc',
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

    private getJobFiles() {
        this.jobsService
            .getJobFiles(this.selectedJob.requestId)
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                map((files) => {
                    let groupedFiles = files.reduce((acc, file) => {
                        let group = file.split('/')[0];
                        if (group === file) {
                            group = 'Metadata';
                        } else {
                            group = group.split('_')[0];
                            group = group.charAt(0).toUpperCase() + group.slice(1);
                        }
                        const groupFiles = acc[group] || [];
                        groupFiles.push(file);
                        acc[group] = groupFiles;
                        return acc;
                    }, {});

                    Object.keys(groupedFiles).forEach((group) => {
                        const groups = groupedFiles[group].sort().map((file) => {
                            return {
                                name: file,
                                group: group,
                                href: `api/job/${
                                    this.selectedJob.requestId
                                }/download?file_name=${encodeURIComponent(file)}`,
                            };
                        });

                        groupedFiles[group] = groups;
                    });

                    groupedFiles = Object.keys(groupedFiles).map((group) => {
                        return {
                            group: group,
                            files: groupedFiles[group],
                        };
                    });

                    return groupedFiles;
                }),
                tap((files) => {
                    this.downloadFilesSubject.next(files);
                }),
            )
            .subscribe();
    }

    addJob() {
        this.jobsService
            .createJob(this.form.getValues())
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap(() => {
                    this.alertMessageService.add({
                        summary: 'Created Ad-Hoc Job',
                        severity: 'success',
                    });
                }),
                mergeMap(() => this.getJobData$()),
                finalize(() => {
                    this.showSideDrawer = false;
                }),
            )
            .subscribe();
    }
}
