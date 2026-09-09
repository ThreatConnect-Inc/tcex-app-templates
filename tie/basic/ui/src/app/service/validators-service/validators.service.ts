import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class ValidatorsService {
  private validatorsMap = {
    required: this.required,
    isNumber: this.isNumber,
    maxLength: this.maxLength,
    minLength: this.minLength,
    gt: this.gt,
    lt: this.lt,
    gte: this.gte,
    lte: this.lte,
    '>': this.gt,
    '<': this.lt,
    '>=': this.gte,
    '<=': this.lte,
  };

  public registerValidator(name: string, fn: Function) {
    if (this.validatorsMap[name]) {
      throw new Error(`Validator with name ${name} already exists`);
    }
    this.validatorsMap[name] = fn;
  }

  public validate(
    value: any,
    validators: { name: string; config?: any }[],
    form: { [key: string]: any }
  ): string | null {
    if (!validators) {
      return null;
    }

    const errorMessage = validators
      .map((validator) => {
        const validatorFn = this.validatorsMap[validator.name];
        // An unregistered name resolves to `undefined`. Calling it throws
        // "is not a function", which aborts validateForm and takes the whole form
        // down with it. A typo in a served validator name must not cost the user
        // the page, so skip it and say so in the console.
        if (typeof validatorFn !== 'function') {
          console.warn(`Unknown validator "${validator.name}" - skipping.`);
          return null;
        }
        if (validator.config !== null && validator.config !== undefined) {
          return validatorFn(value, { form: form, ...validator.config });
        } else {
          return validatorFn(value);
        }
      })
      .filter((error) => !!error)
      .join('\n');

    if (errorMessage.length > 0) {
      return errorMessage;
    }
    return null;
  }

  private required(value: any, config: { errorMessage: string } = { errorMessage: 'Required' }): string | null {
    if (!value || (Array.isArray(value) && value.length === 0)) {
      return config.errorMessage;
    }
  }

  private isNumber(
    value: any,
    config: { errorMessage: string } = { errorMessage: 'Input must be a number' }
  ): string | null {
    if (isNaN(Number(value))) {
      return config.errorMessage;
    }
  }

  private maxLength(value: any, config: { length: Number }): string | null {
    if (value.length > config.length) {
      if (Array.isArray(value)) {
        return `Selection must be ${config.length} or fewer items`;
      } else {
        return `Input must be less than ${config.length} characters`;
      }
    }
  }

  private minLength(value: any, config: { length: Number }): string {
    if (value.length < config.length) {
      if (Array.isArray(value)) {
        return `Selection must be ${config.length} or more items`;
      } else {
        return `Input must be greater than ${config.length} characters`;
      }
    }
  }

  private gt(value: any, config: { value: Number; form } | { field: string; form }): string {
    if (Object.keys(config).includes('field')) {
      if (Number(value) <= Number(config.form[(config as any).field].value)) {
        return `Input must be greater than ${config.form[(config as any).field].config.label}`;
      }
    }

    if (Object.keys(config).includes('value')) {
      if (Number(value) <= Number((config as any).value)) {
        return `Input must be greater than ${(config as any).value}`;
      }
    }
  }

  private lt(value: any, config: { value: Number; form } | { field: string; form }): string {
    if (Object.keys(config).includes('field')) {
      if (Number(value) >= Number(config.form[(config as any).field].value)) {
        return `Input must be less than ${config.form[(config as any).field].config.label}`;
      }
    }

    if (Object.keys(config).includes('value')) {
      if (Number(value) >= Number((config as any).value)) {
        return `Input must be less than ${(config as any).value}`;
      }
    }
  }

  private gte(value: any, config: { value: Number; form } | { field: string; form }): string {
    if (Object.keys(config).includes('field')) {
      if (Number(value) < Number(config.form[(config as any).field].value)) {
        return `Input must be greater than or equal to ${config.form[(config as any).field].config.label}`;
      }
    }

    if (Object.keys(config).includes('value')) {
      // `<`, not `<=` — the bound itself is allowed. The field branch above already
      // reads this way; the value branch did not, so `gte {value: 1}` rejected 1.
      if (Number(value) < Number((config as any).value)) {
        return `Input must be greater than or equal to ${(config as any).value}`;
      }
    }
  }

  private lte(value: any, config: { value: Number; form } | { field: string; form }): string {
    if (Object.keys(config).includes('field')) {
      if (Number(value) >= Number(config.form[(config as any).field].value)) {
        return `Input must be less than or equal to ${config.form[(config as any).field].config.label}`;
      }
    }

    if (Object.keys(config).includes('value')) {
      // `>`, not `>=` — the bound itself is allowed. See the note in `gte`.
      if (Number(value) > Number((config as any).value)) {
        return `Input must be less than or equal to ${(config as any).value}`;
      }
    }
  }
}
