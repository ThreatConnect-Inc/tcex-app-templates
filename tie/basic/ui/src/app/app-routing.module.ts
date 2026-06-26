import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { JobsComponent } from './pages/jobs/jobs.component';
import { TasksComponent } from './pages/tasks/tasks.component';
import { DownloadComponent } from './pages/download/download.component';
import { BatchErrorsComponent } from './pages/batch-errors/batch-errors.component';
import { NotificationsComponent } from './pages/notifications/notifications.component';
import { ReportPdfTrackerComponent } from './pages/report-pdf-tracker/report-pdf-tracker.component';

const routes: Routes = [
    { path: 'dashboard', component: DashboardComponent },
    { path: 'jobs', component: JobsComponent },
    { path: 'tasks', component: TasksComponent },
    { path: 'download', component: DownloadComponent },
    { path: 'batchErrors', component: BatchErrorsComponent },
    { path: 'notifications', component: NotificationsComponent },
    { path: 'reportPdfTrackers', component: ReportPdfTrackerComponent },
    { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
];

@NgModule({
    imports: [RouterModule.forRoot(routes, { onSameUrlNavigation: 'reload' })],
    exports: [RouterModule],
})
export class AppRoutingModule {}
