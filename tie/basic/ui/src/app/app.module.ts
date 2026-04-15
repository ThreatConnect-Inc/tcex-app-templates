import { ClipboardModule } from '@angular/cdk/clipboard';
// import { NgOptimizedImage } from '@angular/common';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatStepperModule } from '@angular/material/stepper';
import { MatTableModule } from '@angular/material/table';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { RouterModule } from '@angular/router';

import { NgxChartsModule } from '@swimlane/ngx-charts';
import {
    AlertToastMessageService,
    AlertToastModule,
    BadgeModule,
    ButtonModule,
    CalendarV2Module,
    CardModule,
    ChipListModule,
    CollapsibleCardModule,
    DropdownButtonModule,
    DropdownV2Module,
    EditButtonsModule,
    IconButtonModule,
    InfoTooltipModule,
    InputTextareaDirectiveModule,
    // LoadingIconModule,
    LoadingSpinnerModule,
    MenuItemModule,
    NestedMenuModule,
    PendoModel,
    PendoModule,
    PillModule,
    SideDrawerModule,
    StepperModule,
    SvgIconModule,
    TableModule,
    TabsModule,
    TextareaModule,
    TextInputModule,
    ToggleModule,
    TooltipModule,
} from '@tc-eng/component-library';
import { MonacoEditorModule, NgxMonacoEditorConfig } from 'ngx-monaco-editor-v2';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { ErrorMessageComponent } from './components/error-message/error-message.component';
import { FormattedFieldComponent } from './components/formatted-field/formatted-field.component';
import { GeneratedFormComponent } from './components/generated-form/generated-form.component';
import { SidenavMenuComponent } from './components/sidenav-menu/sidenav-menu.component';
import { errorHandlerProvider } from './error-handler/error-handler.provider';
import { httpInterceptorProviders } from './interceptors/http-interceptor-providers';
import { BatchErrorsTableComponent } from './pages/batch-errors-table/batch-errors-table.component';
import { BatchErrorsComponent } from './pages/batch-errors/batch-errors.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { DownloadComponent } from './pages/download/download.component';
import { JobsComponent } from './pages/jobs/jobs.component';
import { NotificationsComponent } from './pages/notifications/notifications.component';
import { ReportPdfTrackerComponent } from './pages/report-pdf-tracker/report-pdf-tracker.component';
import { TasksComponent } from './pages/tasks/tasks.component';
import { JsonFormatPipe } from './pipes/json-format/json-format.pipe';
import { WIN_PROVIDERS } from './service/window-service/window.service';

export function onMonacoLoad() {
    // console.log((window as any).monaco); // for debugging
    const uri = (window as any).monaco.Uri.parse('a://b/foo.json');
    (window as any).monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
        validate: true,
        schemas: [
            {
                uri: 'http://myserver/foo-schema.json',
                fileMatch: [uri.toString()],
                schema: {
                    type: 'object',
                    properties: {
                        p1: {
                            enum: ['v1', 'v2'],
                        },
                        p2: {
                            $ref: 'http://myserver/bar-schema.json',
                        },
                    },
                },
            },
            {
                uri: 'http://myserver/bar-schema.json',
                fileMatch: [uri.toString()],
                schema: {
                    type: 'object',
                    properties: {
                        q1: {
                            enum: ['x1', 'x2'],
                        },
                    },
                },
            },
        ],
    });
}

/**
 * If we can get the theme from localStorage before hand then we can set the theme before the app and
 * not set it in the component which causes it to flicker.
 */
const monacoConfig: NgxMonacoEditorConfig = {
    baseUrl: './assets', // configure base path containing monaco-editor directory
    defaultOptions: {}, // pass default options
    onMonacoLoad, // extra optional Monaco configuration
};

@NgModule({
    declarations: [
        AppComponent,
        BatchErrorsComponent,
        BatchErrorsTableComponent,
        DashboardComponent,
        DownloadComponent,
        GeneratedFormComponent,
        FormattedFieldComponent,
        JobsComponent,
        ErrorMessageComponent,
        JsonFormatPipe,
        NotificationsComponent,
        ReportPdfTrackerComponent,
        SidenavMenuComponent,
        TasksComponent,
    ],
    bootstrap: [AppComponent],
    imports: [
        AlertToastModule,
        AppRoutingModule,
        BadgeModule,
        BrowserAnimationsModule,
        BrowserModule,
        ButtonModule,
        CalendarV2Module,
        CardModule,
        ChipListModule,
        ClipboardModule,
        CollapsibleCardModule,
        DropdownButtonModule,
        DropdownV2Module,
        EditButtonsModule,
        FormsModule,
        IconButtonModule,
        InfoTooltipModule,
        InputTextareaDirectiveModule,
        // LoadingIconModule,
        LoadingSpinnerModule,
        MatButtonModule,
        MatCardModule,
        MatCheckboxModule,
        MatIconModule,
        MatMenuModule,
        MatPaginatorModule,
        MatSidenavModule,
        MatStepperModule,
        MatTableModule,
        MenuItemModule,
        MonacoEditorModule.forRoot(monacoConfig),
        NestedMenuModule,
        NgxChartsModule,
        PendoModule,
        PillModule,
        // NgOptimizedImage,
        RouterModule,
        SideDrawerModule,
        StepperModule,
        SvgIconModule,
        TableModule,
        TabsModule,
        TextareaModule,
        TextInputModule,
        ToggleModule,
        TooltipModule,
    ],
    providers: [
        WIN_PROVIDERS,
        AlertToastMessageService,
        errorHandlerProvider,
        httpInterceptorProviders,
        provideHttpClient(withInterceptorsFromDi()),
    ],
})
export class AppModule {}
