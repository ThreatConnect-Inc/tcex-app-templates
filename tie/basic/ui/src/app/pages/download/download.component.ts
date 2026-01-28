import { Component, DestroyRef, ViewChild, inject } from '@angular/core';
import { CheckboxState, MenuItemType } from '@tc-eng/component-library';
import { BehaviorSubject, Observable, delay, finalize, tap } from 'rxjs';
import { MonacoEditorOptions } from 'src/app/models/monaco-editor-options.interface';
import { AppService } from 'src/app/service/app-service/app.service';
import { AlertMessageService } from 'src/app/service/alert-message-service/alert-message.service';
import { DownloadTIService } from 'src/app/service/download-ti-service/download-ti.service';
import { ThemeService } from 'src/app/service/theme-service/theme.service';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { GeneratedFormComponent } from 'src/app/components/generated-form/generated-form.component';

@Component({
  selector: 'download',
  templateUrl: './download.component.html',
  styleUrl: './download.component.scss',
})
export class DownloadComponent {
  // global values
  protected readonly destroyRef = inject(DestroyRef);

  //form
  @ViewChild('form') form: GeneratedFormComponent;

  private loadingSubject = new BehaviorSubject<boolean>(false);
  public loading$ = this.loadingSubject.asObservable();

  private uploadSubject = new BehaviorSubject<boolean>(false);
  public upload$ = this.uploadSubject.asObservable();

  // editors
  editorOptionsReadOnly$: Observable<MonacoEditorOptions> = this.themeService.editorOptionsReadOnly$;
  downloadedData = '';
  convertedData = '';
  downloadForm: any;
  downloadFormConfig: any;

  request$;

  typeMenuItems = [
    {
      value: 'event',
      text: 'Event',
      type: MenuItemType.Default,
      checked: CheckboxState.Checked,
    },
    {
      value: 'report',
      text: 'Report',
      type: MenuItemType.Default,
      checked: CheckboxState.UnChecked,
    },
    {
      value: 'vulnerability',
      text: 'Vulnerability',
      type: MenuItemType.Default,
      checked: CheckboxState.UnChecked,
    },
  ];

  selectedType = 'event';
  private csrf_token: any;

  constructor(
    private alertMessageService: AlertMessageService,
    private downloadTiService: DownloadTIService,
    private themeService: ThemeService,
    private appService: AppService
  ) {}

  ngOnInit() {
    this.appService
      .getConfig()
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        tap((uiConfig) => {
          this.downloadFormConfig = uiConfig?.ui?.downloadTI?.form;
        })
      )
      .subscribe();
  }

  handleCancel() {
    if (this.request$) {
      this.request$.unsubscribe();
    }

    this.loadingSubject.next(false);
  }

  handleDownload() {
    this.loadingSubject.next(true);
    this.request$ = this.downloadTiService
      .get(this.form.getValues())
      .pipe(
        tap((resp) => {
          this.downloadedData = JSON.stringify(resp.original, null, 2);
          this.convertedData = JSON.stringify(resp.transformed, null, 2);
          this.csrf_token = resp.csrf_token;
          this.uploadSubject.next(true);
        }),
        finalize(() => this.loadingSubject.next(false))
      )
      .subscribe();
  }

  handleUpload() {
    this.downloadTiService
      .upload(JSON.parse(this.convertedData), this.csrf_token)
      .pipe(
        tap(() =>
          this.alertMessageService.add({
            summary: 'Data Uploaded to ThreatConnect',
            severity: 'success',
          })
        )
      )
      .subscribe();
  }
}
