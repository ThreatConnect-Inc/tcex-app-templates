import { tap } from 'rxjs';

import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatChipInputEvent } from '@angular/material/chips';
import { MatSnackBar } from '@angular/material/snack-bar';

import { DownloadService } from '../../service/download-service/download.service';

@Component({
    selector: 'app-download-form',
    templateUrl: './download-form.component.html',
    styleUrls: ['./download-form.component.less'],
})
export class DownloadFormComponent implements OnInit {
    separatorKeysCodes: number[] = [ENTER, COMMA];

    downloading: boolean = false;
    form: FormGroup = new FormGroup({});
    response?: string;

    constructor(
        private formBuilder: FormBuilder,
        private downloadService: DownloadService,
        private snackBar: MatSnackBar,
    ) {}

    ngOnInit(): void {
        this.form = this.formBuilder.group({
            type: [null, [Validators.required]],
            ids: [null, [Validators.required]],
            convert: [null, []],
            enrich: [null, []],
        });
    }

    saveDetails(form) {
        this.response = undefined;
        this.downloading = true;
        this.downloadService
            .downloadTi({
                type: this.form.controls['type'].value,
                ids: this.form.controls['ids'].value
                    .split(',')
                    .map((id: string) => encodeURIComponent(id.trim())),
                convert: this.form.controls['convert'].value || false,
                enrich: this.form.controls['enrich'].value || false,
            })
            .pipe(tap(() => this.snackBar.open('Success', 'OK', { duration: 10000 })))
            .subscribe((resp) => {
                this.response = JSON.stringify(resp.body, null, 2);
                this.downloading = false;
            });
    }
}
