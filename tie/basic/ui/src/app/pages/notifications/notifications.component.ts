import { Component, DestroyRef, inject, OnInit, ViewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MenuItemType, Table } from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';
import { catchError, EMPTY, finalize, mergeMap, tap } from 'rxjs';
import { GeneratedFormComponent } from 'src/app/components/generated-form/generated-form.component';
import { AlertMessageService } from 'src/app/service/alert-message-service/alert-message.service';
import { NxPaginator } from 'src/app/modules/nx-utils/nx-paginator';
import { NxTable } from 'src/app/modules/nx-utils/nx-table';
import { AppService, FieldDisplay, Form } from 'src/app/service/app-service/app.service';
import { Notification } from 'src/app/service/notification-service/notification-interface';
import { NotificationService } from 'src/app/service/notification-service/notification.service';

export enum SideDrawerContent {
    DETAILS,
    SEND,
}

@Component({
    selector: 'notifications',
    templateUrl: './notifications.component.html',
    styleUrl: './notifications.component.scss',
})
export class NotificationsComponent implements OnInit {
    protected readonly featureVersion: FeatureVersion = 'new-design';
    protected readonly SideDrawerContent = SideDrawerContent;
    private destroyRef = inject(DestroyRef);

    @ViewChild('dataTable') tableComponent: Table;
    @ViewChild('filterForm') filterForm: GeneratedFormComponent;

    paginator = new NxPaginator({ pageChangeCallback: this.getNotificationData.bind(this) });
    table: NxTable = null;
    detailsData: FieldDisplay[] = [];
    filterFormConfig: Form;

    // Side drawer
    showSideDrawer: boolean = false;
    showSideDrawerTitle: string = 'Send Notification';
    sideDrawerContent: SideDrawerContent = SideDrawerContent.SEND;
    selectedNotification: Notification | null = null;

    // Send form
    newMessage: string = '';
    newNotificationType: string = 'TIE Pipeline Alert';
    newPriority: string = 'Medium';
    priorityOptions = [
        { text: 'Low', value: 'Low', type: MenuItemType.Default, selected: false },
        { text: 'Medium', value: 'Medium', type: MenuItemType.Default, selected: true },
        { text: 'High', value: 'High', type: MenuItemType.Default, selected: false },
    ];
    sending: boolean = false;

    constructor(
        private notificationService: NotificationService,
        private alertMessageService: AlertMessageService,
        private appService: AppService,
    ) {}

    ngOnInit(): void {
        this.appService
            .getConfig()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((uiConfig) => {
                    this.table = this.buildTable(uiConfig?.ui?.notifications?.columns);
                    this.detailsData = uiConfig?.ui?.notifications?.details;
                    this.filterFormConfig = uiConfig?.ui?.notifications?.filters;
                }),
                mergeMap(() => this.getNotificationData$()),
            )
            .subscribe();
    }

    buildTable(columns: FieldDisplay[]): NxTable {
        if (!columns) {
            console.error('Notification table columns configuration is missing in app-config');
            return;
        }

        return new NxTable({
            dataColumns: columns.map((column) => ({
                field: column.field,
                header: column.label,
                fieldDisplay: column,
            })),
        });
    }

    getNotificationData() {
        this.table.dataLoaded = false;
        this.getNotificationData$()
            .pipe(
                catchError(() => {
                    this.table.dataLoaded = true;
                    return EMPTY;
                }),
            )
            .subscribe({});
    }

    handleSearchClick() {
        this.table.dataLoaded = false;
        this.tableComponent.first = 0;
        this.paginator.pageIndex = 0;
        this.getNotificationData();
    }

    handleRowClick(notification: Notification) {
        this.selectedNotification = notification;
        this.showSideDrawerTitle = 'Notification Details';
        this.sideDrawerContent = SideDrawerContent.DETAILS;
        this.showSideDrawer = true;
    }

    handleSendClick() {
        this.newMessage = '';
        this.newNotificationType = 'TIE Pipeline Alert';
        this.newPriority = 'Medium';
        this.showSideDrawerTitle = 'Send Notification';
        this.sideDrawerContent = SideDrawerContent.SEND;
        this.showSideDrawer = true;
    }

    handleSidenavChange(open: boolean) {
        this.showSideDrawer = open;
    }

    sendNotification() {
        this.sending = true;
        this.notificationService
            .sendNotification(this.newMessage, this.newNotificationType, this.newPriority)
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap(() => {
                    this.alertMessageService.add({
                        summary: 'Notification sent',
                        severity: 'success',
                    });
                }),
                mergeMap(() => this.getNotificationData$()),
                finalize(() => {
                    this.showSideDrawer = false;
                    this.sending = false;
                }),
                catchError(() => {
                    this.alertMessageService.add({
                        summary: 'Failed to send notification',
                        severity: 'error',
                    });
                    return [];
                }),
            )
            .subscribe();
    }

    private transformFilterValues(filterValues: Record<string, unknown>): Record<string, unknown> {
        const fields = this.filterFormConfig?.fields as any;
        return Object.entries(filterValues).reduce(
            (acc, [key, val]) => {
                const fieldConfig = fields?.find((f) => f.name === key);

                if (fieldConfig?.type === 'multi-select' && Array.isArray(val)) {
                    if (
                        Array.isArray(fieldConfig.choices) &&
                        val.length === fieldConfig.choices.length
                    ) {
                        return acc;
                    }

                    if (val.length > 0) {
                        if (key === 'send_status') {
                            // Convert display labels to API values
                            // e.g. "Success" → "success", "Not Sent" → "not_sent"
                            acc[key] = val
                                .map((v: string) => v.toLowerCase().replace(/ /g, '_'))
                                .join(',');
                        } else if (key === 'category') {
                            // Convert display labels (Title Case) back to stored values (snake_case)
                            acc[key] = val
                                .map((v: string) => v.toLowerCase().replace(/ /g, '_'))
                                .join(',');
                        } else {
                            acc[key] = val.join(',');
                        }
                    }
                    return acc;
                }

                if (val) {
                    acc[key] = val;
                }
                return acc;
            },
            {} as Record<string, unknown>,
        );
    }

    private getNotificationData$() {
        const filterValues = this.filterForm?.getValues() ?? {};
        const transformedFilterValues = this.transformFilterValues(filterValues);

        return this.notificationService
            .getCollection({
                ...this.paginator.paginationParams,
                ...transformedFilterValues,
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
