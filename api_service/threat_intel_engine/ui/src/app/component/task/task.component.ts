import { BehaviorSubject, interval, Observable, tap } from 'rxjs';
import { TaskService } from 'src/app/service/task-service/task.service';

import { Component, OnInit } from '@angular/core';

@Component({
    selector: 'app-tasks',
    templateUrl: './task.component.html',
    styleUrls: ['./task.component.less'],
})
export class TaskComponent implements OnInit {
    // class properties
    private auto_refresh: any;

    // behavior subjects
    private _TaskPathPipeDataSubject = new BehaviorSubject([]);
    private _TaskStandaloneDataSubject = new BehaviorSubject(0);

    tasksPathPipe$: Observable<any> = this._TaskPathPipeDataSubject.asObservable();
    tasksStandalone$: Observable<any> = this._TaskStandaloneDataSubject.asObservable();

    constructor(private taskService: TaskService) {}

    loadTasksData() {
        this.taskService
            .getTasks()
            .pipe(
                tap((response: any) => {
                    this._TaskPathPipeDataSubject.next(
                        response.filter((task: any) => {
                            if (task.type === 'path_pipe') {
                                return task;
                            }
                        }),
                    );

                    this._TaskStandaloneDataSubject.next(
                        response.filter((task: any) => {
                            if (task.type === 'standalone') {
                                return task;
                            }
                        }),
                    );
                }),
            )
            .subscribe();
    }

    ngOnInit(): void {
        // load the data
        this.loadTasksData();

        // auto reload the data
        this.auto_refresh = interval(15 * 1000).subscribe(() => this.loadTasksData());
    }

    ngOnDestroy(): void {
        clearInterval(this.auto_refresh);
        this.auto_refresh.unsubscribe();
    }
}
