import { Component, Input, OnInit } from '@angular/core';

@Component({
    selector: 'job-process-flow',
    templateUrl: './job-process-flow.component.html',
    styleUrls: ['./job-process-flow.component.less'],
})
export class JobProcessFlowComponent implements OnInit {
    @Input() jobData: any;

    // download settings
    downloadClass: string;
    downloadIcon: string;
    downloadTooltip: string;

    // processing settings
    processClass: string;
    processIcon: string;
    processTooltip: string;

    // status settings
    statusClass: string;
    statusIcon: string;
    statusTooltip: string;

    // upload settings
    uploadClass: string;
    uploadIcon: string;
    uploadTooltip: string;

    constructor() {}

    getClass(completeStatus: string[], activeStatus: string): string {
        if (completeStatus.includes(this.jobData.status.toLowerCase())) {
            return 'success';
        } else if (this.jobData.status.toLowerCase() === activeStatus) {
            return 'active';
        } else if (this.jobData.status.toLowerCase() === 'failed') {
            return 'failed';
        } else {
            return 'pending';
        }
    }

    ngOnInit(): void {
        // download icon
        this.downloadClass = this.getClass(
            [
                'download complete',
                'convert in progress',
                'convert complete',
                'upload in progress',
                'upload complete',
            ],
            'download in progress',
        );
        this.downloadIcon = 'south';
        this.downloadTooltip = 'Download Threat Intelligence\n';
        if (this.jobData.download_runtime !== undefined) {
            this.downloadTooltip += 'Runtime: ' + this.jobData.download_runtime;
        }

        // processing icon
        this.processClass = this.getClass(
            ['convert complete', 'upload in progress', 'upload complete'],
            'convert in progress',
        );
        this.processIcon = 'repeat';
        this.processTooltip = 'Process Threat Intelligence\n';
        if (this.jobData.convert_runtime !== undefined) {
            this.processTooltip += 'Runtime: ' + this.jobData.convert_runtime;
        }

        // status icon
        if (this.jobData.status.toLowerCase() === 'upload complete') {
            this.statusClass = 'success';
            this.statusIcon = 'done';
            this.statusTooltip = 'Job Completed\n' + 'Date: ' + this.jobData.date_completed;
            if (this.jobData.total_runtime !== undefined) {
                this.statusTooltip += '\nRuntime: ' + this.jobData.total_runtime;
            }
        } else if (this.jobData.status.toLowerCase() === 'failed') {
            this.statusClass = 'failed';
            this.statusIcon = 'error_outline';
            this.statusTooltip = 'Job Failed\n' + 'Date: ' + this.jobData.date_failed;
        } else {
            this.statusClass = 'pending';
            this.statusIcon = 'help_outline';
            this.statusTooltip = this.jobData.status;
        }

        // upload icon
        this.uploadClass = this.getClass(['upload complete'], 'upload in progress');
        this.uploadIcon = 'north';
        this.uploadTooltip = 'Upload Threat Intelligence\n';
        if (this.jobData.upload_runtime !== undefined) {
            this.uploadTooltip += 'Runtime: ' + this.jobData.upload_runtime;
        }
    }
}
