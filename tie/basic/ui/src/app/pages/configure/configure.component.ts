import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    inject,
    NgZone,
    OnInit,
    ViewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import {
    ButtonIcon,
    ButtonTheme,
    CheckboxState,
    checkCircle,
    dragHandle,
    DrawerSide,
    DropdownV2Component,
    IconRegistry,
    info,
    MenuItemEvent,
    MenuItemListSettings,
    MenuItemType,
    Table,
} from '@tc-eng/component-library';
import { FeatureVersion } from '@tc-eng/component-library/utils/featureFlags';

import { NxTable } from '../../modules/nx-utils/nx-table';
import { AppService } from '../../service/app-service/app.service';
import { ConfigService } from '../../service/config-service/config.service';

export interface ConfigEntry {
    id?: string;
    rank: number;
    [key: string]: any;
}

export interface ConfigEntryPost {
    rank: number;
    [key: string]: any;
}

export enum DrawerMode {
    NONE,
    EDIT,
    SAVE_CONFIRM,
}

@Component({
    selector: 'app-configure',
    templateUrl: './configure.component.html',
    styleUrls: ['./configure.component.scss'],
    standalone: false,
})
export class ConfigureComponent implements OnInit {
    protected readonly featureVersion: FeatureVersion = 'new-design';
    protected readonly Array = Array;
    protected readonly ButtonIcon = ButtonIcon;
    protected readonly ButtonTheme = ButtonTheme;
    protected readonly DrawerMode = DrawerMode;
    protected readonly DrawerSide = DrawerSide;
    private readonly destroyRef = inject(DestroyRef);

    @ViewChild('dataTable') tableComponent: Table;

    table = new NxTable({ dataColumns: [] });
    formFields: any[] = [];
    infoTooltip: string | null = null;

    configs: ConfigEntry[] = [];
    selectedIndex: number = -1;
    isNewConfig: boolean = false;
    hasPendingChanges: boolean = false;

    showSideDrawer = false;
    drawerMode: DrawerMode = DrawerMode.NONE;
    drawerTitle = 'Edit Config';
    validationError: string | null = null;
    tqlValidated = false;
    tqlMatchCount: number | null = null;
    validating = false;
    saving = false;

    showDeleteConfirm = false;
    pendingDeleteIndex = -1;
    selectedSaveMode: 'delta' | 'full' = 'delta';

    // Dynamic form values — keyed by field name
    formValues: { [key: string]: any } = {};
    // Dropdown state — keyed by field name
    dropdownMenuItems: { [key: string]: any[] } = {};
    dropdownRefs: { [key: string]: DropdownV2Component } = {};

    readonly rowActionMenuItems = [
        { label: 'Edit', value: 'edit' },
        { label: 'Delete', value: 'delete' },
    ];

    readonly ownerDropdownSettings: MenuItemListSettings = {
        filter: true,
        filterPlaceholder: 'Search owners...',
    };

    private editConfig: ConfigEntry | null = null;

    constructor(
        private configService: ConfigService,
        private appService: AppService,
        private iconRegistry: IconRegistry,
        private ngZone: NgZone,
        private cdr: ChangeDetectorRef,
    ) {
        this.iconRegistry.registerIcons([checkCircle, dragHandle, info]);
    }

    ngOnInit(): void {
        // Load UI config (columns, form fields) from backend
        this.appService
            .getConfig()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((config: any) => {
                const cfg = config?.ui?.configure;
                if (cfg?.columns) {
                    this.table = new NxTable({ dataColumns: cfg.columns });
                }
                if (cfg?.formFields) {
                    this.formFields = cfg.formFields;
                }
                if (cfg?.infoTooltip) {
                    this.infoTooltip = cfg.infoTooltip;
                }
            });

        // Load existing config entries
        this.configService
            .getConfig()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((data) => {
                this.configs = Array.isArray(data) ? data : [];
                this.table.data = [...this.configs];
            });
    }

    openAdd(): void {
        this.isNewConfig = true;
        this.selectedIndex = -1;
        this.drawerTitle = 'Add Config';
        this.drawerMode = DrawerMode.EDIT;
        this.validationError = null;
        this.editConfig = { rank: this.configs.length };
        this.initFormValues(null);
        this.showSideDrawer = true;
        this.refreshDynamicDropdowns();
    }

    openEdit(config: ConfigEntry, index: number): void {
        this.isNewConfig = false;
        this.editConfig = { ...config };
        this.selectedIndex = index;
        this.drawerTitle = 'Edit Config';
        this.drawerMode = DrawerMode.EDIT;
        this.validationError = null;
        this.initFormValues(config);
        this.showSideDrawer = true;
        this.refreshDynamicDropdowns();
    }

    deleteConfig(index: number): void {
        this.configs.splice(index, 1);
        this.table.data = [...this.configs];
        this.hasPendingChanges = true;
    }

    protected asIndex(i: unknown): number {
        return i as number;
    }

    onRowDragStart(event: DragEvent, config: ConfigEntry): void {
        this.ngZone.runOutsideAngular(() => {
            const ghost = document.createElement('div');
            const label = config.tql || config.name || 'Config';
            ghost.textContent = `Moving: ${String(label).slice(0, 60)}`;
            Object.assign(ghost.style, {
                position: 'fixed',
                top: '-9999px',
                left: '-9999px',
                background: 'var(--tcl-base02, #ffffff)',
                color: 'var(--tcl-textBody, #333333)',
                border: '1px solid var(--tcl-border, #d0d0d0)',
                borderRadius: '4px',
                padding: '6px 12px',
                fontSize: '13px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                whiteSpace: 'nowrap',
                maxWidth: '320px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                pointerEvents: 'none',
            });
            document.body.appendChild(ghost);
            event.dataTransfer?.setDragImage(ghost, 0, 0);
            requestAnimationFrame(() => document.body.removeChild(ghost));
        });
    }

    handleConfigMenuAction(event: string, config: ConfigEntry, index: number): void {
        if (event === 'edit') this.openEdit(config, index);
        if (event === 'delete') {
            this.pendingDeleteIndex = index;
            this.showDeleteConfirm = true;
        }
    }

    confirmDelete(): void {
        if (this.pendingDeleteIndex >= 0) {
            this.deleteConfig(this.pendingDeleteIndex);
        }
        this.showDeleteConfirm = false;
        this.pendingDeleteIndex = -1;
    }

    cancelDelete(): void {
        this.showDeleteConfirm = false;
        this.pendingDeleteIndex = -1;
    }

    onRowReorder(event: any): void {
        if (event?.dragIndex === event?.dropIndex) return;
        this.configs = [...this.tableComponent.value];
        this.table.data = this.configs;
        this.hasPendingChanges = true;
        setTimeout(() => this.cdr.detectChanges());
    }

    onDropdownChange(fieldName: string, event: MenuItemEvent): void {
        const field = this.formFields.find((f: any) => f.name === fieldName);
        if (field?.type === 'multi-select') {
            this.formValues[fieldName] = event.selected
                ? event.selected.map((item: any) => item.value as string).filter(Boolean)
                : [];
        } else {
            this.formValues[fieldName] = event.item?.value || '';
        }
        this.invalidateValidation();
    }

    onTextChange(fieldName: string, val: string): void {
        this.formValues[fieldName] = val || '';
        this.invalidateValidation();
    }

    private invalidateValidation(): void {
        this.tqlValidated = false;
        this.tqlMatchCount = null;
        this.validationError = null;
    }

    validateTql(): void {
        // Check required fields
        const missingRequired = this.formFields
            .filter((f: any) => f.required && !this.formValues[f.name]?.length)
            .map((f: any) => f.label);
        if (missingRequired.length) {
            this.validationError = `Fill in ${missingRequired.join(', ')} before validating.`;
            return;
        }

        this.validating = true;
        this.validationError = null;
        this.tqlValidated = false;
        this.tqlMatchCount = null;

        const config = this.buildConfigFromForm();
        this.configService
            .testConfig(config)
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: (result: any) => {
                    this.validating = false;
                    if (result?.status !== 'Success') {
                        this.validationError = result?.message || JSON.stringify(result, null, 2);
                        this.tqlValidated = false;
                    } else {
                        this.tqlValidated = true;
                        this.tqlMatchCount = typeof result.count === 'number' ? result.count : null;
                    }
                },
                error: (err: any) => {
                    this.validating = false;
                    this.tqlValidated = false;
                    this.validationError =
                        err?.error?.description ||
                        err?.error?.message ||
                        err?.message ||
                        'Validation request failed.';
                },
            });
    }

    applyLocalChange(): void {
        const missingRequired = this.formFields
            .filter((f: any) => f.required && !this.formValues[f.name]?.length)
            .map((f: any) => f.label);
        if (missingRequired.length) {
            this.validationError = `${missingRequired.join(', ')} required.`;
            return;
        }

        const config: ConfigEntry = {
            id: this.editConfig?.id,
            rank: this.editConfig?.rank ?? this.configs.length,
            ...this.formValues,
        };

        if (this.isNewConfig) {
            this.configs.push(config);
        } else {
            this.configs[this.selectedIndex] = config;
        }
        this.table.data = [...this.configs];
        this.hasPendingChanges = true;
        this.showSideDrawer = false;
    }

    openSaveConfirm(): void {
        this.selectedSaveMode = 'delta';
        this.drawerMode = DrawerMode.SAVE_CONFIRM;
        this.drawerTitle = 'Save Changes';
        this.validationError = null;
        this.showSideDrawer = true;
    }

    saveAllChanges(startOver: boolean): void {
        this.saving = true;
        const payload = this.configs.map((config) => {
            const { id, ...rest } = config;
            return rest;
        });
        this.configService
            .saveConfig(payload, startOver)
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: (result: any) => {
                    this.saving = false;
                    if (result === null) {
                        // error was already surfaced by the service's errorHandler
                        this.validationError = 'Failed to save changes.';
                        return;
                    }
                    this.hasPendingChanges = false;
                    this.showSideDrawer = false;
                },
                error: () => {
                    this.saving = false;
                    this.validationError = 'Failed to save changes.';
                },
            });
    }

    discardChanges(): void {
        this.configService
            .getConfig()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((data) => {
                this.configs = Array.isArray(data) ? data : [];
                this.table.data = [...this.configs];
                this.hasPendingChanges = false;
            });
    }

    handleSidenavChange(newValue: boolean): void {
        if (newValue !== this.showSideDrawer) {
            this.showSideDrawer = newValue;
        }
    }

    private initFormValues(config: ConfigEntry | null): void {
        this.formValues = {};
        for (const field of this.formFields) {
            if (config) {
                this.formValues[field.name] = config[field.name] ?? field.default ?? '';
            } else {
                this.formValues[field.name] = field.default ?? '';
            }
        }
        this.tqlValidated = config !== null;
        this.validationError = null;
        this.rebuildDropdownMenuItems(config);
    }

    private rebuildDropdownMenuItems(config: ConfigEntry | null): void {
        for (const field of this.formFields) {
            if (field.type === 'multi-select' && field.choices) {
                const selected = this.formValues[field.name] || [];
                this.dropdownMenuItems[field.name] = field.choices.map((choice: string) => ({
                    text: choice,
                    value: choice,
                    type: MenuItemType.MultiSelect,
                    checked: selected.includes(choice)
                        ? CheckboxState.Checked
                        : CheckboxState.UnChecked,
                }));
            } else if (field.type === 'select' && field.choices) {
                const currentValue = this.formValues[field.name] || '';
                this.dropdownMenuItems[field.name] = field.choices.map((choice: string) => ({
                    text: choice,
                    value: choice,
                    type: MenuItemType.Default,
                    selected: currentValue === choice,
                }));
            }
        }
    }

    private refreshDynamicDropdowns(): void {
        // Owners dropdown needs fresh data from server
        this.appService
            .getOwners()
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe((owners: string[]) => {
                // Update any multi-select field named 'owners' with server data
                const ownerField = this.formFields.find((f: any) => f.name === 'owners');
                if (ownerField) {
                    const selected = this.formValues['owners'] || [];
                    this.dropdownMenuItems['owners'] = owners.map((name) => ({
                        text: name,
                        value: name,
                        type: MenuItemType.MultiSelect,
                        checked: selected.includes(name)
                            ? CheckboxState.Checked
                            : CheckboxState.UnChecked,
                        iconRight: 'eye',
                        actionOnHover: true,
                    }));
                }
                setTimeout(() => this.rerenderDropdowns());
            });
    }

    private rerenderDropdowns(): void {
        // Re-render dropdown refs if available
        for (const key of Object.keys(this.dropdownRefs)) {
            this.dropdownRefs[key]?.forceRerender(this.dropdownMenuItems[key]);
        }
    }

    private buildConfigFromForm(): ConfigEntryPost {
        const result: ConfigEntryPost = {
            rank: this.editConfig?.rank ?? this.configs.length,
        };
        for (const field of this.formFields) {
            result[field.name] = this.formValues[field.name];
        }
        if (this.editConfig?.version) {
            result['version'] = this.editConfig.version;
        }
        return result;
    }
}
