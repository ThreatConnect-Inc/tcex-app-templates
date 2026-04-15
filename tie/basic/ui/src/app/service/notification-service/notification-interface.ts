import { ApiPaginationParams } from '../api-response-interface';

export interface Notification {
    id: string;
    dateAdded: string;
    category: string;
    notificationType: string;
    priority: string;
    message: string;
    sendStatus: string | null;
    sendStatusCode: number | null;
    sendStatusText: string | null;
    apiRequest: Record<string, unknown> | null;
    apiResponse: Record<string, unknown> | null;
}

export interface NotificationPaginationParams extends ApiPaginationParams {
    category?: string;
    priority?: string;
    send_status?: string;
}
