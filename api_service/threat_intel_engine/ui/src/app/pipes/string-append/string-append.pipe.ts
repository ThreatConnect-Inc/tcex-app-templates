import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
    name: 'stringAppend',
})
export class StringAppendPipe implements PipeTransform {
    transform(value: string, chars: string): string {
        return `${value}${chars}`;
    }
}
