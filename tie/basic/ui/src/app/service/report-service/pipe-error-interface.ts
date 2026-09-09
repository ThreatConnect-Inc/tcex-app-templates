export interface PipeError {
    id: string;
    step: string;
    dateAdded: string | null;
    message: string;
    raw: string;
    requestId: string;
    [key: string]: any;
}

export interface PipeErrorResponse {
    data: PipeError[];
    count: number;
    totalCount: number;
    next?: string | null;
    prev?: string | null;
    status?: string | null;
}
