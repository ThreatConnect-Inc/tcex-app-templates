import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { ReplaySubject, Observable } from 'rxjs';

export interface Validator {
  name: string;
  config?: any;
}
export interface Form {
  fields: {
    choices?: string[];
    default?: string | string[];
    info?: string;
    label: string;
    minWidth?: number;
    name: string;
    required: boolean;
    type?: string;
    validators: Validator[];
  }[];
}

export interface FieldDisplay {
  field: string;
  label: string;
  type?: string;
}

export interface AppConfig {
  schema: string;
  ui: {
    global: {
      sideNav: { label: string; path: string }[];
      featureFlags?: {
        enableAddJob?: boolean;
      };
    };
    adhocRequest: {
      form: Form;
    };
    downloadTI: {
      form: Form;
    };
    jobTable: {
      columns: FieldDisplay[];
      details: FieldDisplay[];
      filters: Form;
    };
    owner: string;
    title: string;
    version: string;
  };
}

@Injectable({
  providedIn: 'root',
})
export class AppService {
  apiUrl: string = 'api/tc';

  private appConfigSubject = new ReplaySubject<AppConfig>();

  constructor(private http: HttpClient) {
    this.loadUIConfig().subscribe((config) => {
      this.appConfigSubject.next(config);
    });
  }

  public getConfig(): Observable<AppConfig> {
    return this.appConfigSubject.asObservable();
  }

  private loadUIConfig(): Observable<AppConfig> {
    return this.http.get<AppConfig>(`${this.apiUrl}/app-config`);
  }
}
