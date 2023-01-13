import { Component, Input, OnInit } from '@angular/core';

@Component({
    selector: 'app-info-field',
    templateUrl: './info-field.component.html',
    styleUrls: ['./info-field.component.less'],
})
export class InfoFieldComponent implements OnInit {
    @Input('data') data: string;
    @Input('formatType') formatType: string = null;
    @Input('label') label: string;

    constructor() {}

    ngOnInit(): void {}
}
