import { BehaviorSubject, Observable } from 'rxjs';

import { Injectable } from '@angular/core';
import { Router } from '@angular/router';

import { ApiResponseCollection } from '../api-response-interface';
import { BaseService } from '../base-service/base.service';
import { Task } from './task-interface';

@Injectable({
    providedIn: 'root',
})
export class TaskService extends BaseService {
    apiUrl: string = '/api/task';

    private tasksSubject: BehaviorSubject<ApiResponseCollection<Task>> = new BehaviorSubject<
        ApiResponseCollection<Task>
    >({ data: [], totalCount: 0 });

    constructor(public router: Router) {
        super(router);
        this.loadCollection();
    }

    private loadCollection() {
        return this.http
            .get<ApiResponseCollection<Task>>(`${this.apiUrl}`, {
                params: this.convertToHttpParams({}),
            })
            .subscribe((res) => {
                this.tasksSubject.next(res);
            });
    }

    getCollection(): Observable<ApiResponseCollection<Task>> {
        return this.tasksSubject.asObservable();
    }

    getTaskStatuses(): Observable<any> {
        return this.http.get<ApiResponseCollection<string[]>>(`${this.apiUrl}/status`);
    }

    killTask(task: Task) {
        return this.http.delete(`${this.apiUrl}/${task.slug}`);
    }

    pauseTask(task: Task) {
        return this.http.put(`${this.apiUrl}/${task.slug}`, null, { params: { pause: true } });
    }

    resumeTask(task: Task) {
        return this.http.put(`${this.apiUrl}/${task.slug}`, null, { params: { pause: false } });
    }

    runTask(task: Task) {
        return this.http.put(`${this.apiUrl}/${task.slug}`, null, { params: { run: true } });
    }
}
