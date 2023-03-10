import { HIGHLIGHT_OPTIONS, HighlightModule } from 'ngx-highlightjs';

import { HTTP_INTERCEPTORS, HttpClientModule } from '@angular/common/http';
import { NgModule } from '@angular/core';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatBadgeModule } from '@angular/material/badge';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';
import { MatNativeDateModule } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatGridListModule } from '@angular/material/grid-list';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatSortModule } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { MatTabsModule } from '@angular/material/tabs';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import {
    AddRequestDialogComponent
} from './component/add-request-dialog/add-request-dialog.component';
import {
    CardSingleValueComponent
} from './component/card-single-value/card-single-value.component';
import { DashboardComponent } from './component/dashboard/dashboard.component';
import { DownloadFormComponent } from './component/download-form/download-form.component';
import { HelpComponent } from './component/help/help.component';
import { InfoFieldComponent } from './component/info-field/info-field.component';
import { JobDataFormComponent } from './component/job-data-form/job-data-form.component';
import { JobDataComponent } from './component/job-data/job-data.component';
import { JobProcessFlowComponent } from './component/job-process-flow/job-process-flow.component';
import { PageTitleComponent } from './component/page-title/page-title.component';
import {
    ReportBatchErrorComponent
} from './component/report-batch-error/report-batch-error.component';
import { TaskCardComponent } from './component/task-card/task-card.component';
import { TaskComponent } from './component/task/task.component';
import { SafeHtmlPipe } from './pipes/safe-html/safe-html.pipe';
import { StringAppendPipe } from './pipes/string-append/string-append.pipe';
import { StringTruncatePipe } from './pipes/string-truncate/string-truncate.pipe';
import {
    HttpInterceptorService
} from './service/http-interceptor-service/http-interceptor.service';
import { TaskService } from './service/task-service/task.service';

@NgModule({
    declarations: [
        AddRequestDialogComponent,
        AppComponent,
        CardSingleValueComponent,
        DashboardComponent,
        DownloadFormComponent,
        JobDataComponent,
        JobDataFormComponent,
        JobProcessFlowComponent,
        ReportBatchErrorComponent,
        SafeHtmlPipe,
        StringAppendPipe,
        StringTruncatePipe,
        TaskCardComponent,
        TaskComponent,
        PageTitleComponent,
        HelpComponent,
        InfoFieldComponent,
    ],
    imports: [
        AppRoutingModule,
        BrowserAnimationsModule,
        BrowserModule,
        FormsModule,
        HighlightModule,
        HttpClientModule,
        MatAutocompleteModule,
        MatBadgeModule,
        MatButtonModule,
        MatCardModule,
        MatCheckboxModule,
        MatChipsModule,
        MatDatepickerModule,
        MatDialogModule,
        MatFormFieldModule,
        MatGridListModule,
        MatIconModule,
        MatInputModule,
        MatMenuModule,
        MatNativeDateModule,
        MatPaginatorModule,
        MatProgressBarModule,
        MatSelectModule,
        MatSidenavModule,
        MatSlideToggleModule,
        MatSortModule,
        MatTableModule,
        MatTabsModule,
        MatToolbarModule,
        MatTooltipModule,
        ReactiveFormsModule,
    ],
    providers: [
        MatSnackBar,
        TaskService,
        // {
        //     provide: APP_BASE_HREF,
        //     useFactory: () => document.getElementsByTagName('base')[0].href.replace(/ui\/.*/, ''),
        //     deps: [],
        // },
        {
            provide: HIGHLIGHT_OPTIONS,
            useValue: {
                coreLibraryLoader: () => import('highlight.js/lib/core'),
                lineNumbersLoader: () => import('highlightjs-line-numbers.js'),
                languages: {
                    json: () => import('highlight.js/lib/languages/json'),
                },
                themePath: 'assets/styles/highlight.css',
            },
        },
        {
            provide: HTTP_INTERCEPTORS,
            useClass: HttpInterceptorService,
            multi: true,
        },
    ],
    bootstrap: [AppComponent],
})
export class AppModule {}
