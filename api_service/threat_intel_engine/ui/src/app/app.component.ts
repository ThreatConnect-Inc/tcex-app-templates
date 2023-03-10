import { filter } from 'rxjs';

import { Component } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.less'],
})
export class AppComponent {
    activeTab: string = '';

    constructor(private router: Router) {
        // console.log(router.url);

        this.router.events
            .pipe(filter((event) => event instanceof NavigationEnd))
            .subscribe((event) => {
                this.activeTab = (<any>event).url;
                // console.log(event);
            });
    }
}
