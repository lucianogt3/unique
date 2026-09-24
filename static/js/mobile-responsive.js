(() => {
    'use strict';

    const body = document.body;
    const sidebar = document.getElementById('appSidebar');
    const openButton = document.getElementById('mobileMenuButton');
    const closeButton = document.getElementById('sidebarClose');
    const overlay = document.getElementById('sidebarOverlay');
    const desktopBreakpoint = 1200;

    const setSidebarState = (open) => {
        if (!sidebar || !openButton || !overlay) {
            return;
        }

        const shouldOpen = Boolean(open)
            && window.innerWidth < desktopBreakpoint;

        body.classList.toggle('sidebar-open', shouldOpen);
        openButton.setAttribute(
            'aria-expanded',
            shouldOpen ? 'true' : 'false'
        );
        overlay.hidden = !shouldOpen;

        if (shouldOpen) {
            closeButton?.focus({ preventScroll: true });
        }
    };

    openButton?.addEventListener('click', () => {
        setSidebarState(!body.classList.contains('sidebar-open'));
    });

    closeButton?.addEventListener('click', () => {
        setSidebarState(false);
        openButton?.focus({ preventScroll: true });
    });

    overlay?.addEventListener('click', () => {
        setSidebarState(false);
    });

    sidebar?.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => {
            setSidebarState(false);
        });
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape'
            && body.classList.contains('sidebar-open')) {
            setSidebarState(false);
            openButton?.focus({ preventScroll: true });
        }
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth >= desktopBreakpoint) {
            setSidebarState(false);
        }
    }, { passive: true });

    /*
     * Converte tabelas comuns em cartões no telefone.
     * A página de prontuários possui uma implementação própria.
     * Relatórios extensos são mantidos com rolagem horizontal pelo CSS.
     */
    const prepareResponsiveTables = () => {
        document.querySelectorAll(
            '.table-responsive table'
        ).forEach((table) => {
            if (
                table.closest('.prontuarios-page')
                || table.classList.contains('no-mobile-cards')
            ) {
                return;
            }

            const headers = Array.from(
                table.querySelectorAll('thead th')
            ).map((header) => (
                header.textContent || ''
            ).trim());

            if (!headers.length) {
                return;
            }

            table.classList.add('mobile-card-table');

            table.querySelectorAll('tbody tr').forEach((row) => {
                const cells = Array.from(
                    row.children
                ).filter((cell) => cell.tagName === 'TD');

                if (
                    cells.length === 1
                    && Number(cells[0].getAttribute('colspan') || 1) > 1
                ) {
                    row.classList.add('mobile-empty-row');
                    return;
                }

                cells.forEach((cell, index) => {
                    if (!cell.dataset.label) {
                        cell.dataset.label = (
                            headers[index]
                            || `Campo ${index + 1}`
                        );
                    }
                });
            });
        });
    };

    /*
     * Em dispositivos touch, títulos nativos ajudam nos botões somente
     * com ícones, sem alterar ações ou handlers existentes.
     */
    const improveIconButtons = () => {
        document.querySelectorAll(
            'button[title], a[title]'
        ).forEach((element) => {
            if (!element.getAttribute('aria-label')) {
                element.setAttribute(
                    'aria-label',
                    element.getAttribute('title')
                );
            }
        });
    };

    /*
     * Força o Chart.js a recalcular tamanho após giro da tela.
     */
    let resizeTimer = null;
    const notifyChartsResize = () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            window.dispatchEvent(new Event('app:responsive-resize'));

            if (
                window.Chart
                && Array.isArray(window.Chart.instances)
            ) {
                window.Chart.instances.forEach((chart) => {
                    try {
                        chart.resize();
                    } catch (_) {
                        // A página pode ter removido o gráfico.
                    }
                });
            } else if (
                window.Chart
                && window.Chart.instances
                && typeof window.Chart.instances === 'object'
            ) {
                Object.values(window.Chart.instances).forEach((chart) => {
                    try {
                        chart.resize();
                    } catch (_) {
                        // Sem ação.
                    }
                });
            }
        }, 180);
    };

    window.addEventListener(
        'orientationchange',
        notifyChartsResize,
        { passive: true }
    );

    document.addEventListener('DOMContentLoaded', () => {
        prepareResponsiveTables();
        improveIconButtons();
        notifyChartsResize();
    });
})();
