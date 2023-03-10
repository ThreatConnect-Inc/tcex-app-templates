import { StandardParams } from './standard-param-interface';

export interface PaginationParams extends StandardParams {
    // pagination | sorting
    limit?: number;
    offset?: number;
    sort?: string;
    sortOrder?: string;
}
