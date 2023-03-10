import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
    name: 'stringTruncate',
})
export class StringTruncatePipe implements PipeTransform {
    transform(value: string, length: number, append_chars: string = ''): unknown {
        // short-circuit if string length is leq requested length
        if (value.length <= length) {
            return value;
        }

        // subtract append characters from the length to
        // ensure the exact length required is returned
        length -= append_chars.length;

        // truncate the string to the specified length
        value = value.substring(0, length);

        // return transformed string
        return `${value}${append_chars}`;
    }
}
