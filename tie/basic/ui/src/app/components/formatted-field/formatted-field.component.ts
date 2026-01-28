import { tap } from 'rxjs';

import { Component, DestroyRef, inject, Input, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { FieldDisplay } from 'src/app/service/app-service/app.service';
import { TaskService } from 'src/app/service/tasks-service/tasks.service';

@Component({
    selector: 'app-formatted-field',
    templateUrl: './formatted-field.component.html',
    styleUrl: './formatted-field.component.scss',
})
export class FormattedFieldComponent implements OnInit {
    @Input() field: FieldDisplay;
    @Input() value: any;

    finalStatuses: string[] | null = null;

    private readonly destroyRef = inject(DestroyRef);

    constructor(private taskService: TaskService) {}

    ngOnInit(): void {
        this.taskService
            .getCollection()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((res) => {
                    this.finalStatuses = res.data
                        .filter((task) => task.lastTask)
                        .map((task) => task.statusComplete.toLocaleLowerCase());
                }),
            )
            .subscribe();
    }
}
