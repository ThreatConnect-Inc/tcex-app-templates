import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { discardStepperGuard, onboardingGuard } from './guard/onboarding.guard';
import { BatchErrorsComponent } from './pages/batch-errors/batch-errors.component';
import { ConfigureComponent } from './pages/configure/configure.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { DocumentationComponent } from './pages/documentation/documentation.component';
import { DownloadComponent } from './pages/download/download.component';
import { EgressErrorsComponent } from './pages/egress-errors/egress-errors.component';
import { JobsComponent } from './pages/jobs/jobs.component';
import { NotificationsComponent } from './pages/notifications/notifications.component';
import { ReportPdfTrackerComponent } from './pages/report-pdf-tracker/report-pdf-tracker.component';
import { SettingsComponent } from './pages/settings/settings.component';
import { TasksComponent } from './pages/tasks/tasks.component';

const routes: Routes = [
    // Ingress routes
    { path: 'dashboard', component: DashboardComponent, canActivate: [onboardingGuard] },
    { path: 'download', component: DownloadComponent, canActivate: [onboardingGuard] },
    { path: 'batchErrors', component: BatchErrorsComponent, canActivate: [onboardingGuard] },
    {
        path: 'reportPdfTrackers',
        component: ReportPdfTrackerComponent,
        canActivate: [onboardingGuard],
    },

    // Egress routes
    { path: 'configure', component: ConfigureComponent, canActivate: [onboardingGuard] },
    { path: 'errors', component: EgressErrorsComponent, canActivate: [onboardingGuard] },

    // Shared routes
    { path: 'jobs', component: JobsComponent, canActivate: [onboardingGuard] },
    { path: 'tasks', component: TasksComponent, canActivate: [onboardingGuard] },
    { path: 'notifications', component: NotificationsComponent, canActivate: [onboardingGuard] },
    // NOT guarded — this is where the guard sends everything else.
    { path: 'settings', component: SettingsComponent, canDeactivate: [discardStepperGuard] },
    { path: 'documentation', component: DocumentationComponent, canActivate: [onboardingGuard] },

    // There is deliberately no `onboarding` route — the stepper is rendered conditionally
    // by SettingsComponent. A route would add a URL that itself needed guarding against
    // post-completion visits, for no benefit.
    //
    // `onboardingGuard` is what makes "no URL can bypass setup" true: every route above
    // except `settings` redirects there while onboarding is incomplete, on every
    // navigation, not just at boot. `discardStepperGuard` on `settings` is the other half —
    // it stops that redirect silently throwing away an in-progress stepper.

    // Default — side nav config drives which page is the landing page. Left unguarded on
    // purpose: a redirect carries no component, and the guard fires on `dashboard`.
    { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
];

@NgModule({
    imports: [RouterModule.forRoot(routes, { onSameUrlNavigation: 'reload' })],
    exports: [RouterModule],
})
export class AppRoutingModule {}
