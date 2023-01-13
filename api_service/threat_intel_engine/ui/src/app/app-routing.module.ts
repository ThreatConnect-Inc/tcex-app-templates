import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { DashboardComponent } from './component/dashboard/dashboard.component';
import { DownloadFormComponent } from './component/download-form/download-form.component';
import { JobDataComponent } from './component/job-data/job-data.component';
import {
    ReportBatchErrorComponent
} from './component/report-batch-error/report-batch-error.component';
import { TaskComponent } from './component/task/task.component';

const routes: Routes = [
    {
        path: 'ui/dashboard',
        component: DashboardComponent,
    },
    {
        path: 'ui/download',
        component: DownloadFormComponent,
    },
    {
        path: 'ui/job',
        component: JobDataComponent,
    },
    {
        path: 'ui/download',
        component: DownloadFormComponent,
    },
    {
        path: 'ui/tasks',
        component: TaskComponent,
    },
    {
        path: 'ui/report/batch-error',
        component: ReportBatchErrorComponent,
    },
    {
        path: '**',
        pathMatch: 'full',
        redirectTo: 'ui/dashboard',
    },
];

@NgModule({
    imports: [RouterModule.forRoot(routes, { onSameUrlNavigation: 'reload' })],
    exports: [RouterModule],
})
export class AppRoutingModule {}
