import { tap } from 'rxjs';

import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';

import { TaskService } from '../../service/task-service/task.service';
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'task-card',
    templateUrl: './task-card.component.html',
    styleUrls: ['./task-card.component.less'],
})
export class TaskCardComponent implements OnInit {
    @Input() task: any;
    @Output() onChange = new EventEmitter<string>();

    cardClass = 'notAlive';
    schedule: string;

    // dialog settings
    dialogWidth: string = '500px';

    constructor(private dialog: MatDialog, private taskService: TaskService) {}

    ngOnInit(): void {
        if (this.task?.process?.is_alive) {
            this.cardClass = 'alive';
        } else if (this.task?.paused) {
            this.cardClass = 'paused';
        }
        this.schedule = `Every ${this.task.schedule_period} ${this.task.schedule_unit}`;
    }

    killTask(): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            width: this.dialogWidth,
            data: {
                buttonNo: 'Cancel',
                buttonYes: 'Kill Task',
                title: 'Kill Task',
                message:
                    'Running task are actively processing data. ' +
                    'Are you sure you want to kill this task?',
            },
        });

        dialogRef.afterClosed().subscribe((confirmed: boolean) => {
            if (confirmed) {
                this.taskService
                    .killTask(this.task.name)
                    .pipe(tap(() => this.onChange.emit('Kill')))
                    .subscribe();
            }
        });
    }

    pauseTask(): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            width: this.dialogWidth,
            data: {
                buttonNo: 'Cancel',
                buttonYes: 'Pause Task',
                title: 'Pause Task',
                message:
                    'Paused tasks will no longer pick up jobs from the queue. ' +
                    'Are you sure you want to pause this task? ',
            },
        });

        dialogRef.afterClosed().subscribe((confirmed: boolean) => {
            if (confirmed) {
                this.taskService
                    .pauseTask(this.task.slug)
                    .pipe(tap(() => this.onChange.emit('Paused')))
                    .subscribe();
            }
        });
    }

    resumeTask(): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            width: this.dialogWidth,
            data: {
                buttonNo: 'Cancel',
                buttonYes: 'Resume Task',
                title: 'Resume Task',
                message: 'Are you sure you want to resume this paused task? ',
            },
        });

        dialogRef.afterClosed().subscribe((confirmed: boolean) => {
            if (confirmed) {
                this.taskService
                    .resumeTask(this.task.slug)
                    .pipe(tap(() => this.onChange.emit('Resumed')))
                    .subscribe();
            }
        });
    }

    runTask(): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            width: this.dialogWidth,
            data: {
                buttonNo: 'Cancel',
                buttonYes: 'Run Task',
                title: 'Run Task',
                message:
                    'Task are configured on a schedule and should only be run ' +
                    'adhoc if necessary. Are you sure you want to run this task? ',
            },
        });

        dialogRef.afterClosed().subscribe((confirmed: boolean) => {
            if (confirmed) {
                this.taskService
                    .runTask(this.task.slug)
                    .pipe(tap(() => this.onChange.emit('Success')))
                    .subscribe();
            }
        });
    }
}
