import { Location } from '@angular/common';
import {Component, DestroyRef, inject, OnInit} from '@angular/core';
import { Router } from '@angular/router';
import {BehaviorSubject, config, tap} from 'rxjs';
import {takeUntilDestroyed} from "@angular/core/rxjs-interop";
import {AppConfig, AppService} from "../../service/app-service/app.service";

@Component({
    selector: 'app-sidenav-menu',
    templateUrl: './sidenav-menu.component.html',
    styleUrls: ['./sidenav-menu.component.scss'],
})
export class SidenavMenuComponent implements OnInit {
    tabIndex: number = 0;
    protected readonly destroyRef = inject(DestroyRef);
    private appConfigSubject = new BehaviorSubject<AppConfig>(null);
    sideNavItems: { label: string; path: string }[] = [];


    constructor(
        private router: Router,
        private appService: AppService,
        private location: Location,
    ) {}

    ngOnInit(): void {
        this.router.events
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap(() => this.processUrl()),
            )
            .subscribe();
        this.appService
          .getConfig()
          .pipe(
            takeUntilDestroyed(this.destroyRef),
            tap((uiConfig) => {
              this.sideNavItems = uiConfig?.ui?.global?.sideNav;
              this.processUrl();
            })
          )
          .subscribe((config) => {
            this.appConfigSubject.next(config);
          });
    }

    tabChange(tabChangeIndex: number) {
        this.tabIndex = tabChangeIndex;
        const selectedItem = this.sideNavItems[this.tabIndex];
        if (selectedItem) {
          this.router.navigateByUrl(selectedItem.path);
        }
      }

    private processUrl() {
        const urlPath = this.location.path().split('?')[0];
        const index = this.sideNavItems.findIndex((item) => {
            const itemPath = item.path.startsWith('/') ? item.path : '/' + item.path;
            return itemPath === urlPath;
          });
        if (index !== -1) {
          this.tabIndex = index;
        }
    }
}
