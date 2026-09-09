import { Pipe, PipeTransform } from '@angular/core';

/**
 * Formats an ISO 8601 timestamp for display:
 *   - Removes sub-second precision (milliseconds / microseconds)
 *   - Always displays in UTC so timestamps are unambiguous across timezones
 *   - Output format:  YYYY-MM-DD HH:mm:ss UTC
 *   - Null / empty / un-parseable values render as an empty string
 *
 * Usage in templates:
 *   {{ value.date_queued | isoDate }}
 *   -> "2026-07-17 11:21:33 UTC"
 */
@Pipe({
    name: 'isoDate',
    standalone: false,
})
export class IsoDatePipe implements PipeTransform {
    transform(value: string | null | undefined): string {
        if (!value) {
            return '';
        }
        const d = new Date(value);
        if (isNaN(d.getTime())) {
            return String(value);
        }
        return d
            .toISOString()
            .replace(/\.\d+Z$/, ' UTC')
            .replace('T', ' ');
    }
}
