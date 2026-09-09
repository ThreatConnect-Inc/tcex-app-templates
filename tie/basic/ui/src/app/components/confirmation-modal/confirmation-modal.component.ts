import { Component, EventEmitter, Input, Output } from '@angular/core';

import { ButtonTheme } from '@tc-eng/component-library';

export interface ConfirmationModalConfig {
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    confirmTheme?: ButtonTheme;
    cancelTheme?: ButtonTheme;
    maxWidth?: string;
    modalSize?: 'small' | 'medium' | 'large';
    /**
     * Drop the cancel button, leaving only the confirm one.
     *
     * For the acknowledge case: a dialog that reports something rather than asking a
     * question. Two buttons imply a choice, so offering one that does not change the
     * outcome is worse than offering none.
     */
    hideCancel?: boolean;
    icon?: {
        name: string;
        color?: string;
    };
}

@Component({
    standalone: false,
    selector: 'app-confirmation-modal',
    templateUrl: './confirmation-modal.component.html',
    styleUrls: ['./confirmation-modal.component.scss'],
})
export class ConfirmationModalComponent {
    @Input() visible = false;
    @Input() featureVersion: string = 'new-design';
    @Input() config: ConfirmationModalConfig = {
        title: 'Confirm Action',
        message: 'Are you sure you want to proceed?',
        confirmText: 'Confirm',
        cancelText: 'Cancel',
        confirmTheme: ButtonTheme.Primary,
        cancelTheme: ButtonTheme.Secondary,
        maxWidth: '32rem',
        modalSize: 'small',
    };

    @Output() confirmed = new EventEmitter<void>();
    @Output() cancelled = new EventEmitter<void>();
    @Output() visibilityChange = new EventEmitter<boolean>();

    readonly ButtonTheme = ButtonTheme;

    onConfirm(): void {
        this.confirmed.emit();
        this.closeModal();
    }

    onCancel(): void {
        this.cancelled.emit();
        this.closeModal();
    }

    onModalClose(): void {
        this.cancelled.emit();
        this.closeModal();
    }

    private closeModal(): void {
        this.visible = false;
        this.visibilityChange.emit(false);
    }

    get effectiveConfig(): Required<ConfirmationModalConfig> {
        return {
            title: this.config.title || 'Confirm Action',
            message: this.config.message || 'Are you sure you want to proceed?',
            confirmText: this.config.confirmText || 'Confirm',
            cancelText: this.config.cancelText || 'Cancel',
            confirmTheme: this.config.confirmTheme || ButtonTheme.Primary,
            cancelTheme: this.config.cancelTheme || ButtonTheme.Secondary,
            maxWidth: this.config.maxWidth || '32rem',
            modalSize: this.config.modalSize || 'small',
            // `?? false`, not `|| false`: a boolean must not go through the same
            // falsy-means-default treatment the strings above rely on.
            hideCancel: this.config.hideCancel ?? false,
            icon: this.config.icon || undefined,
        };
    }
}
