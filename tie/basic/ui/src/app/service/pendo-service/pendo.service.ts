import { Injectable } from '@angular/core';

@Injectable({
    providedIn: 'root',
})
export class PendoService {
    constructor() {}

    initializePendo() {
        if (!window['enablePendo']) {
            throw 'enablePendo function not found';
        }

        const pendoConfigStorage = localStorage.getItem('tc.pendo');

        if (!pendoConfigStorage) {
            console.log('Pendo configuration not found, skipping initialization.');
            return;
        }

        let apiKey: string;
        let pendoConfig: Record<string, unknown>;
        try {
            ({ apiKey, ...pendoConfig } = JSON.parse(pendoConfigStorage));
        } catch (e) {
            console.warn('Failed to parse Pendo configuration from localStorage:', e);
            return;
        }

        window['enablePendo'](apiKey);

        window['pendo'].initialize(pendoConfig);
    }
}
