import { catchError, EMPTY, tap } from 'rxjs';

import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { Marked } from 'marked';
import { DocsService } from 'src/app/service/docs-service/docs.service';

/**
 * Markdown renderer that gives headings GitHub-style `id`s.
 *
 * `marked` stopped emitting heading ids in v5, so without this every link in the guide's
 * Table of Contents points at an anchor that does not exist. The slug rule matches the one
 * GitHub uses, which is what the `#...` links in `docs/user-guide.md` were written against:
 * lowercase, drop punctuation, collapse whitespace to hyphens — so "Workflow/Use Cases"
 * becomes `workflowuse-cases`, not `workflow-use-cases`.
 */
const markdown = new Marked({
    renderer: {
        heading(token) {
            const text = this.parser.parseInline(token.tokens);
            const id = text
                .replace(/<[^>]*>/g, '')
                .toLowerCase()
                .trim()
                .replace(/[^\w\s-]/g, '')
                .replace(/\s+/g, '-');
            return `<h${token.depth} id="${id}">${text}</h${token.depth}>\n`;
        },
    },
});

@Component({
    selector: 'documentation',
    templateUrl: './documentation.component.html',
    styleUrl: './documentation.component.scss',
})
export class DocumentationComponent implements OnInit {
    html: string = '';
    errorMessage: string = '';

    private readonly destroyRef = inject(DestroyRef);

    constructor(private docsService: DocsService) {}

    ngOnInit(): void {
        this.docsService
            .getDoc()
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                tap((doc) => {
                    // The markdown is shipped in the app package, not user input.
                    this.html = markdown.parse(doc.markdown, { async: false }) as string;
                }),
                catchError(() => {
                    this.errorMessage = 'The user guide could not be loaded.';
                    return EMPTY;
                }),
            )
            .subscribe();
    }

    /**
     * Scroll table-of-contents links to their heading.
     *
     * `index.html` carries `<base href="./">`, and a bare `#fragment` resolves against the
     * *base* URL rather than the current one — so letting the browser handle these would
     * navigate to `./#section` and bounce the router (`onSameUrlNavigation: 'reload'`)
     * instead of scrolling. Doing it manually also targets the real scroll container,
     * `.page-container`, rather than the document, which `body { overflow: hidden }` has
     * pinned.
     */
    handleAnchorClick(event: MouseEvent): void {
        const anchor = (event.target as HTMLElement | null)?.closest('a');
        const href = anchor?.getAttribute('href');
        if (!anchor || !href?.startsWith('#')) {
            return;
        }

        event.preventDefault();
        const id = decodeURIComponent(href.slice(1));
        const target = anchor.closest('.markdown')?.querySelector(`[id="${CSS.escape(id)}"]`);
        target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}
