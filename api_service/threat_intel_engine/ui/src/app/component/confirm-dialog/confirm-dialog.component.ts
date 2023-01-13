import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';

export interface DialogData {
    buttonNo: string;
    buttonYes: string;
    title: string;
    message: string;
}

@Component({
    selector: 'app-confirm-dialog',
    templateUrl: './confirm-dialog.component.html',
    styleUrls: ['./confirm-dialog.component.less'],
})
export class ConfirmDialogComponent {
    buttonNo: string;
    buttonYes: string;
    title: string;
    message: string;

    constructor(
        public dialogRef: MatDialogRef<ConfirmDialogComponent>,
        @Inject(MAT_DIALOG_DATA) public data: DialogData,
    ) {
        this.buttonNo = data.buttonNo || 'No';
        this.buttonYes = data.buttonYes || 'Yes';
        this.message = data.message;
        this.title = data.title;
    }

    onConfirm(): void {
        // Close the dialog, return true
        this.dialogRef.close(true);
    }

    onDismiss(): void {
        // Close the dialog, return false
        this.dialogRef.close(false);
    }
}
