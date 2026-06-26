import { Observable } from 'rxjs';

import { Injectable } from '@angular/core';

import { BaseService } from '../base-service/base.service';
import { ApiResponseCollection } from '../api-response-interface';
import { Notification, NotificationPaginationParams } from './notification-interface';

@Injectable({
    providedIn: 'root',
})
export class NotificationService extends BaseService {
    apiUrl: string = '/api/notification';

    getCollection(params: NotificationPaginationParams): Observable<ApiResponseCollection<Notification>> {
        return this.http.get<ApiResponseCollection<Notification>>(`${this.apiUrl}`, {
            params: this.convertToHttpParams(params),
        });
    }

    sendNotification(
        message: string,
        notificationType: string,
        priority: string,
    ): Observable<Notification> {
        return this.http.post<Notification>(`${this.apiUrl}`, {
            message,
            notification_type: notificationType,
            priority,
        });
    }
}
