import { PaginationParams } from '../base-service/pagination-param-interface';

export interface GetJobRequestParam extends PaginationParams {
    jobType?: string;
    requestId?: string;
    status?: string;
}
