import { Component, Input, OnInit } from '@angular/core';

@Component({
    selector: 'page-title',
    templateUrl: './page-title.component.html',
    styleUrls: ['./page-title.component.less'],
})
export class PageTitleComponent implements OnInit {
    @Input() title: string;

    constructor() {}

    ngOnInit(): void {}
}
