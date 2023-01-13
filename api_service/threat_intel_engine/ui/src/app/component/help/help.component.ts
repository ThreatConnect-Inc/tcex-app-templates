import { Component, Input, OnInit } from '@angular/core';

@Component({
    selector: 'help',
    templateUrl: './help.component.html',
    styleUrls: ['./help.component.less'],
})
export class HelpComponent implements OnInit {
    @Input() position?: string = 'below';
    @Input() text: string;

    constructor() {}

    ngOnInit(): void {}
}
