import { BehaviorSubject, interval } from 'rxjs';

import { Component, DestroyRef, inject, OnInit, Renderer2, ViewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Event, NavigationEnd, Router } from '@angular/router';

import {
    alert,
    check,
    chevronLeft,
    chevronRight,
    eye,
    IconRegistry,
    info,
    moreHorizontal,
    trash,
} from '@tc-eng/component-library';

import { AppConfig, AppService } from './service/app-service/app.service';
import { PendoService } from './service/pendo-service/pendo.service';
import { ThemeService } from './service/theme-service/theme.service';

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit {
    // global values
    protected readonly destroyRef = inject(DestroyRef);

    showSideNavIcon: 'chevron-left' | 'chevron-right' = 'chevron-left';
    viewSideNav: boolean = true;
    hideSideNav: boolean = false;
    logoImage: string = 'assets/images/TCLogo_LightTheme.svg';
    appTheme: 'light' | 'dark' = 'light';
    showThemeToggle: boolean = true; // for dev purposes only

    showContent = false;
    private appConfigSubject = new BehaviorSubject<AppConfig>(null);
    appConfig$ = this.appConfigSubject.asObservable();

    constructor(
        private router: Router,
        private appService: AppService,
        private iconRegistry: IconRegistry,
        private pendoService: PendoService,
        private themeService: ThemeService,
        private renderer: Renderer2,
    ) {
        this.iconRegistry.registerIcons([
            alert,
            check,
            chevronLeft,
            chevronRight,
            eye,
            info,
            moreHorizontal,
            trash,
        ]);
    }

    ngOnInit() {
        this.pendoService.initializePendo();

        setTimeout(() => (this.showContent = true), 100);

        // Load app config
        this.appService
            .getConfig()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((config) => {
                this.appConfigSubject.next(config);
            });

        const permissions = localStorage.getItem('tc.permissions');
        if (permissions) {
            const userPermissions = JSON.parse(permissions);
            this.appTheme = userPermissions?.settingUser?.uiTheme === 'Dark' ? 'dark' : 'light';
            if (this.appTheme === 'dark') {
                this.logoImage = 'assets/images/TCLogo_DarkTheme.svg';
                this.themeService.setTheme(this.appTheme);
                this.renderer.addClass(document.body, this.appTheme);
            }
        }

        this.router.events
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((event: Event) => {
                if (event instanceof NavigationEnd && event.url.indexOf('/job-execution') != -1) {
                    this.hideSideNav = true;
                }
            });

        this.appConfig$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((config) => {
            document.title = config?.ui?.title;
        });
    }

    showSideNav() {
        this.viewSideNav = !this.viewSideNav;
        this.showSideNavIcon = this.viewSideNav ? 'chevron-left' : 'chevron-right';
    }
}

// Define AppConfig interface
