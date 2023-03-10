import { Component, Input, OnInit } from '@angular/core';

@Component({
    selector: 'card-single-value',
    templateUrl: './card-single-value.component.html',
    styleUrls: ['./card-single-value.component.less'],
})
export class CardSingleValueComponent implements OnInit {
    @Input() dateLastUpdated: string;
    @Input() title: string;
    @Input() value: number;

    // class properties
    formattedValue: string;
    dateLastUpdatedDelta: string;

    constructor() {}

    ngOnInit(): void {
        // update title
        this.title =
            this.title
                .replace(/_count/g, ' ')
                .replace(/_/g, ' ')
                .toUpperCase()
                .trim() + 'S';

        // update value
        this.formattedValue = this.nFormatter(this.value, 1);

        // calculate time delta for last updated
        const now = new Date();
        const dateNow = new Date(now.getTime() + now.getTimezoneOffset()).getTime();
        const dateLastUpdated = new Date(this.dateLastUpdated).getTime();
        const delta = (dateNow - dateLastUpdated) / 1000;
        this.dateLastUpdatedDelta = this.convertTime(delta);
    }

    convertTime(seconds: number): string {
        var seconds = parseInt(String(seconds), 10);
        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor((seconds - hours * 3600) / 60);
        var seconds = seconds - hours * 3600 - minutes * 60;
        if (!!hours) {
            if (!!minutes) {
                return `${hours}h ${minutes}m ${seconds}s`;
            } else {
                return `${hours}h ${seconds}s`;
            }
        }
        if (!!minutes) {
            return `${minutes}m ${seconds}s`;
        }
        return `${seconds}s`;
    }

    nFormatter(num: number, digits: number): string {
        const lookup = [
            { value: 1, symbol: '' },
            { value: 1e3, symbol: 'K' },
            { value: 1e6, symbol: 'M' },
            { value: 1e9, symbol: 'G' },
            { value: 1e12, symbol: 'T' },
            { value: 1e15, symbol: 'P' },
            { value: 1e18, symbol: 'E' },
        ];
        const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
        var item = lookup
            .slice()
            .reverse()
            .find(function (item) {
                return num >= item.value;
            });
        return item ? (num / item.value).toFixed(digits).replace(rx, '$1') + item.symbol : '0';
    }
}
