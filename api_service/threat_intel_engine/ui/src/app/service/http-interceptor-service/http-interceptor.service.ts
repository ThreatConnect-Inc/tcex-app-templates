import { Observable } from 'rxjs';

import { HttpEvent, HttpHandler, HttpInterceptor, HttpRequest } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({
    providedIn: 'root',
})
export class HttpInterceptorService implements HttpInterceptor {
    intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
        // find 'ui' and truncate everything after
        const baseUrl = document.getElementsByTagName('base')[0].href.replace(/ui\/.*/, '');
        const updatedUrl = `${baseUrl}${request.url}`;

        // console.log('baseUrl', baseUrl);
        // console.log('updatedUrl', updatedUrl);
        const apiRequest = request.clone({ url: updatedUrl });
        return next.handle(apiRequest);
    }
}
