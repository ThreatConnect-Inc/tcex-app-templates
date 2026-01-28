import { ApiPaginationParams, ApiStandardParams } from '../api-response-interface';

export interface BatchError {
    id: string;
    code: string;
    dateAdded: string;
    message: string;
    requestId: string;
}


export interface BatchErrorCollectionPaginationParams extends ApiPaginationParams {
    errorCode?: string;
    messages?: string[];
    reason?: string;
    request_id?: string;
}

export interface BatchErrorExportParams extends ApiStandardParams {
    errorCode?: string;
    messages?: string[];
    reason?: string;
    request_id?: string;
    format: 'csv' | 'json';
}

export interface BatchErrorCountsParams extends ApiStandardParams {
    request_id?: string;
}
