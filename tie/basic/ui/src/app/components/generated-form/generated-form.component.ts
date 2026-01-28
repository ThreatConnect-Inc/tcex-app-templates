import { BehaviorSubject, Observable } from 'rxjs';

import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import { CheckboxState, MenuItemType } from '@tc-eng/component-library';
import { Form } from 'src/app/service/app-service/app.service';
import { ValidatorsService } from 'src/app/service/validators-service/validators.service';

@Component({
    selector: 'app-generated-form',
    templateUrl: './generated-form.component.html',
    styleUrl: './generated-form.component.scss',
})
export class GeneratedFormComponent implements OnChanges {
    private formConfigSubject = new BehaviorSubject<any[]>([]);
    formConfig$ = this.formConfigSubject.asObservable();

    private validSubject = new BehaviorSubject<boolean>(false);
    public valid$: Observable<boolean> = this.validSubject.asObservable();

    @Input() formConfig: Form;

    form: { [key: string]: { error: string; value: any; config: any } } = {};

    constructor(private validatorsService: ValidatorsService) {}

    ngOnChanges(_changes: SimpleChanges): void {
        if (this.formConfig) {
            this.validSubject.next(false);
            this.buildDownloadFormConfig(this.formConfig);
        }
    }

    getValues() {
        const values = {};
        for (const field in this.form) {
            values[field] = this.form[field].value;
        }

        return values;
    }

    handleChange(event: any, field: string) {
        const fieldInfo = this.form[field];
        switch (fieldInfo.config.type) {
            case 'select':
                // this is likely a bug, and the correct item should be in event.selectd, but it's not.
                fieldInfo.value = event.item.value;
                fieldInfo.config.dirty = true;
                break;
            case 'multi-select':
                fieldInfo.value = event.selected.map((item) => item.value);
                fieldInfo.config.dirty = true;
                break;
            case 'date':
                fieldInfo.value = event ? event.getTime() : event;
                fieldInfo.config.dirty = true;
                break;
            default:
                fieldInfo.value = event;
        }

        this.validateForm();
    }

    validateForm() {
        for (const fieldName in this.form) {
            const field = this.form[fieldName];
            field.error = this.validatorsService.validate(
                field.value,
                field.config.validators,
                this.form,
            );
        }

        const valid = Object.values(this.form).every((field) => !field.error);
        this.validSubject.next(valid);

        // if a field hasn't been touched yet, don't show error message yet.
        for (const fieldName in this.form) {
            const field = this.form[fieldName];
            if (!field.config.dirty) {
                field.error = null;
            }
        }
    }

    private buildDownloadFormConfig(form: Form) {
        const downloadFormConfig = form.fields.map((field) => {
            return {
                ...field,
                advancedSettings: this.buildAdvancedSettings(field),
                choices: this.mapChoices(field),
                dirty: false,
                minWidth: field.minWidth ?? 200,
            };
        });

        for (const field of downloadFormConfig) {
            this.form[field.name] = { error: '', value: field.default, config: field };
        }

        this.formConfigSubject.next(downloadFormConfig);
    }

    private buildAdvancedSettings(field) {
        if (field.type !== 'multi-select') {
            return {};
        }

        return { headerSelectAll: true };
    }

    private mapChoices(field) {
        if (field.type !== 'select' && field.type !== 'multi-select') {
            return [];
        }

        const multiSelectOptions =
            field.type === 'multi-select'
                ? {
                      iconRight: 'eye',
                      actionInfo: 'View Only This',
                      actionOnHover: true,
                  }
                : {};

        return (
            field.choices?.map((choice: string) => ({
                ...multiSelectOptions,
                text: choice,
                value: choice,
                type: field.type === 'select' ? MenuItemType.Default : MenuItemType.MultiSelect,
                checked: field.default.includes(choice)
                    ? CheckboxState.Checked
                    : CheckboxState.UnChecked,
                selected: field.default.includes(choice) ? true : false,
            })) || []
        );
    }
}
