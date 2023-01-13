import { Observable } from 'rxjs';
import { TaskService } from 'src/app/service/task-service/task.service';

import { Component, EventEmitter, OnInit, Output } from '@angular/core';

@Component({
    selector: 'job-data-form',
    templateUrl: './job-data-form.component.html',
    styleUrls: ['./job-data-form.component.less'],
})
export class JobDataFormComponent implements OnInit {
    @Output() doSearchEvent = new EventEmitter<any>();

    // form inputs -> query params
    jobType: string;
    requestId: string;
    status: string;

    // form options
    jobTypeOptions: string[] = ['ad-hoc', 'scheduled'];
    taskStatusOptions$: Observable<any>;

    // pagination | sorting
    pageIndex: number = 0;
    pageSize: number = 20;
    sort: string;
    sortOrder: string;

    constructor(private taskService: TaskService) {}

    ngOnInit(): void {
        this.doSearch();

        // get the available task statuses
        this.taskStatusOptions$ = this.taskService.getTaskStatusOptions();
    }

    clearForm() {
        this.jobType = undefined;
        this.status = undefined;
        this.requestId = undefined;
    }

    doSearch() {
        console.log('do search');
        this.doSearchEvent.emit({
            // form inputs -> query params
            jobType: this.jobType,
            status: this.status,
            requestId: this.requestId,
        });
    }

    // updateData(searchData: any) {
    //     for (let key in searchData) {
    //         if (searchData[key] !== undefined) {
    //             this[key] = searchData[key];
    //         }
    //     }
    // }
}
