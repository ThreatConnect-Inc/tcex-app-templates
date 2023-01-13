import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { Component } from '@angular/core';
import { MatAutocompleteSelectedEvent } from '@angular/material/autocomplete';
import { MatDialogRef } from '@angular/material/dialog';

import { JobService } from '../../service/job-service/job.service';

@Component({
    selector: 'app-add-request-dialog',
    templateUrl: './add-request-dialog.component.html',
    styleUrls: ['./add-request-dialog.component.less'],
})
export class AddRequestDialogComponent {
    rangeStart: string;
    rangeEnd: string;
    constructor(
        public dialogRef: MatDialogRef<AddRequestDialogComponent>,
        private jobService: JobService,
    ) {
        const now = new Date();
        const formatted = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, -1);
        this.rangeStart = formatted;
        this.rangeEnd = formatted;

        // load the settings
        this.loadSettings();
    }

    close() {
        this.dialogRef.close({
            rangeStart: this.rangeStart,
            rangeEnd: this.rangeEnd,
        });
    }

    loadSettings() {
        this.jobService.getJobSettings().subscribe((settings) => {
            // this loads job settings and can be used to auto-fill form
        });
    }
}
