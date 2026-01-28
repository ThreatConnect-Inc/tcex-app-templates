import { BehaviorSubject, interval, map, merge, mergeMap, tap } from 'rxjs';

import { Component, DestroyRef, inject, OnDestroy, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { NestedMenuItem } from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';
import { NxTable } from 'src/app/modules/nx-utils/nx-table';
import { MetricsService } from 'src/app/service/metrics-service/metrics.service';
import { TaskService } from 'src/app/service/tasks-service/tasks.service';
import { Task } from 'src/app/service/tasks-service/task-interface';

export enum SideDrawerContent {
    KILL,
    PAUSE,
    RUN,
    RESUME,
}

@Component({
    selector: 'tasks',
    templateUrl: './tasks.component.html',
    styleUrl: './tasks.component.scss',
})
export class TasksComponent implements OnDestroy, OnInit {
    // tcl ui framework settings
    protected readonly featureVersion: FeatureVersion = 'new-design';
    private readonly destroyRef = inject(DestroyRef);

    // charts data
    metricsSubject = new BehaviorSubject([]);
    metrics$ = this.metricsSubject.asObservable();

    view = [1000, 500];

    // table state
    table = new NxTable({
        dataColumns: [
            { field: 'name', header: 'Name' },
            { field: 'description', header: 'Description' },
            // { field: 'schedule', header: 'Schedule' },
            { field: 'maxExecutionMinutes', header: 'Heartbeat Timeout (Minutes)' },
        ],
    });

    private refreshTimer$ = interval(1000 * 60 * 1);
    private refreshTimerSubscription: any;

    // side nav settings
    protected readonly SideDrawerContent = SideDrawerContent;

    showSideDrawer: boolean = false;
    showSideDrawerTitle: string = 'Pause';
    sideDrawerContent: SideDrawerContent;

    selectedTask?: Task;

    constructor(
        private metricsService: MetricsService,
        private taskService: TaskService,
    ) {}

    ngOnDestroy(): void {
        this.refreshTimerSubscription.unsubscribe();
    }

    ngOnInit(): void {
        this.loadTasks$().pipe(takeUntilDestroyed(this.destroyRef)).subscribe();

        this.metricsService
            .getTasksCollection()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                map((data) => {
                    let metrics = [];

                    const runtimeMetrics = data.runtime_metrics;

                    if (runtimeMetrics) {
                        metrics = metrics.concat(
                            Object.keys(runtimeMetrics)
                                .filter((key) => key.startsWith('average') || key.startsWith('max'))
                                .map((key) => {
                                    return {
                                        name: this.formatField(key),
                                        value: runtimeMetrics[key],
                                    };
                                }),
                        );
                    }

                    return metrics;
                }),
                tap((data) => {
                    this.metricsSubject.next(data);
                }),
            )
            .subscribe();

        this.refreshTimerSubscription = this.refreshTimer$
            .pipe(mergeMap(() => this.loadTasks$()))
            .subscribe();
    }

    closeSideDrawer() {
        this.showSideDrawer = false;
    }

    formatField(label: string) {
        return label.replace(/^_*(.)|_+(.)/g, (s, c, d) =>
            c ? c.toUpperCase() : ' ' + d.toUpperCase(),
        );
    }

    formatSchedule(task: Task): string {
        return `Every ${task.schedulePeriod} ${task.scheduleUnit}`;
    }

    getMenuItemsForTask(task: Task) {
        const menuItems: NestedMenuItem[] = [];

        if (this.isTaskRunning(task)) {
            menuItems.push({ label: 'Kill', value: 'kill' });
        } else {
            menuItems.push({ label: 'Run', value: 'run' });
        }

        if (task.paused) {
            menuItems.push({ label: 'Resume', value: 'resume' });
        } else {
            menuItems.push({ label: 'Pause', value: 'pause' });
        }

        return menuItems;
    }

    handleNestedMenuSelection(event_, task: Task) {
        switch (event_) {
            case 'kill':
                this.showSideDrawerTitle = 'Kill Task';
                this.sideDrawerContent = SideDrawerContent.KILL;
                this.selectedTask = task;
                this.showSideDrawer = true;
                break;
            case 'pause':
                this.showSideDrawerTitle = 'Pause Task';
                this.sideDrawerContent = SideDrawerContent.PAUSE;
                this.selectedTask = task;
                this.showSideDrawer = true;
                break;
            case 'run':
                this.showSideDrawerTitle = 'Run Task';
                this.sideDrawerContent = SideDrawerContent.RUN;
                this.selectedTask = task;
                this.showSideDrawer = true;
                break;
            case 'resume':
                this.showSideDrawerTitle = 'Resume Task';
                this.sideDrawerContent = SideDrawerContent.RESUME;
                this.selectedTask = task;
                this.showSideDrawer = true;
                break;
        }
    }

    handleSidenavChange(newValue) {
        if (newValue !== this.showSideDrawer) {
            this.showSideDrawer = newValue;
        }
    }

    isTaskRunning(task: Task) {
        return task?.process?.is_alive;
    }

    killTask(task: Task) {
        this.taskService
            .killTask(task)
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                mergeMap(() => this.loadTasks$()),
                tap(() => {
                    this.showSideDrawer = false;
                }),
            )
            .subscribe();
    }

    pauseTask(task: Task) {
        this.taskService
            .pauseTask(task)
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                mergeMap(() => this.loadTasks$()),
                tap(() => {
                    this.showSideDrawer = false;
                }),
            )
            .subscribe();
    }

    resumeTask(task: Task) {
        this.taskService
            .resumeTask(task)
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                mergeMap(() => this.loadTasks$()),
                tap(() => {
                    this.showSideDrawer = false;
                }),
            )
            .subscribe();
    }

    runTask(task: Task) {
        this.taskService
            .runTask(task)
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                mergeMap(() => this.loadTasks$()),
                tap(() => {
                    this.showSideDrawer = false;
                }),
            )
            .subscribe();
    }

    private loadTasks$() {
        return this.taskService.getCollection().pipe(
            tap((resp) => {
                this.table.data = resp.data.map((task) => {
                    return {
                        ...task,
                        menuItems: this.getMenuItemsForTask(task),
                    };
                });
            }),
        );
    }
}
