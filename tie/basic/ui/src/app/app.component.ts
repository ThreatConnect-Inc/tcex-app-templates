import { BehaviorSubject, catchError, first, of, timeout } from 'rxjs';

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
import { OnboardingService } from './service/onboarding-service/onboarding.service';
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
    private brand: string = 'threatconnect';
    logoReady: boolean = false;

    private static readonly BRAND_LOGOS: Record<string, { light: string; dark: string }> = {
        threatconnect: {
            light: 'assets/images/TCLogo_LightTheme.svg',
            dark: 'assets/images/TCLogo_DarkTheme.svg',
        },
        dataminr: {
            light: 'assets/images/dataminr-logo-black.png',
            dark: 'assets/images/dataminr-logo-white.png',
        },
    };

    showContent = false;
    private appConfigSubject = new BehaviorSubject<AppConfig>(null);
    appConfig$ = this.appConfigSubject.asObservable();

    constructor(
        private router: Router,
        private appService: AppService,
        private iconRegistry: IconRegistry,
        private onboardingService: OnboardingService,
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
        try {
            this.pendoService.initializePendo();
        } catch (e) {
            console.warn('Pendo initialization failed:', e);
        }

        // The nav waits on the gate RESOLVING so it never renders for a frame and then gets
        // redirected out from under the operator. WHAT the status says is `onboardingGuard`'s
        // business, not this component's — all that is needed here is the moment an answer
        // exists. `first()` is required: the source is a ReplaySubject that never completes.
        // The timeout and catchError are belt-and-braces on top of the service already
        // failing open, so a hung request cannot leave the app blank forever.
        this.onboardingService
            .getStatus()
            .pipe(
                first(),
                timeout(10_000),
                takeUntilDestroyed(this.destroyRef),
                catchError(() => of(null)),
            )
            .subscribe(() => (this.showContent = true));

        // Load app config
        this.appService
            .getConfig()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((config) => {
                this.appConfigSubject.next(config);
                if (config?.ui?.brand) {
                    this.brand = config.ui.brand;
                    this.updateLogo();
                }
            });

        const permissions = localStorage.getItem('tc.permissions');
        if (permissions) {
            const userPermissions = JSON.parse(permissions);
            this.appTheme = userPermissions?.settingUser?.uiTheme === 'Dark' ? 'dark' : 'light';
            if (this.appTheme === 'dark') {
                this.themeService.setTheme(this.appTheme);
                this.renderer.addClass(document.body, this.appTheme);
            }
        }
        this.updateLogo();

        this.router.events.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((event: Event) => {
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

    private updateLogo(): void {
        const logos = AppComponent.BRAND_LOGOS[this.brand] ?? AppComponent.BRAND_LOGOS['threatconnect'];
        this.logoImage = this.appTheme === 'dark' ? logos.dark : logos.light;
        this.logoReady = true;
    }
}

// Define AppConfig interface
