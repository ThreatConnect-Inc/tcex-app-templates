import { PaginationParams } from '../base-service/pagination-param-interface';

export interface GetReportBatchErrorsParam extends PaginationParams {
    requestId?: string;
}

export interface GetReportPdfTrackerParam extends PaginationParams {
    id?: string;
}
