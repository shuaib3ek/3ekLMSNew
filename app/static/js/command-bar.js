/**
 * Pulse Command Bar - High Density Search & Actions
 */
const CommandBar = {
    isOpen: false,
    results: [],
    selectedIndex: 0,

    init() {
        this.createUI();
        this.bindEvents();
    },

    createUI() {
        const html = `
            <div id="command-bar-overlay" class="cmd-overlay" style="display: none;">
                <div class="cmd-window">
                    <div class="cmd-header">
                        <i class="ph ph-command" style="color: var(--accent);"></i>
                        <input type="text" id="cmd-input" placeholder="Search workshops, learners, or actions..." autocomplete="off">
                        <kbd>ESC</kbd>
                    </div>
                    <div id="cmd-results" class="cmd-results">
                        <div class="cmd-empty">Type to start searching...</div>
                    </div>
                    <div class="cmd-footer">
                        <span><kbd>↑↓</kbd> Navigate</span>
                        <span><kbd>↵</kbd> Select</span>
                        <span><kbd>ESC</kbd> Close</span>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
        
        // Inject Styles
        const style = `
            <style>
                .cmd-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(15, 23, 42, 0.8);
                    backdrop-filter: blur(8px);
                    z-index: 5000;
                    display: flex;
                    justify-content: center;
                    padding-top: 15vh;
                }
                .cmd-window {
                    width: 600px;
                    max-width: 90vw;
                    background: #0f172a;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                    animation: cmdEnter 0.2s ease-out;
                }
                @keyframes cmdEnter {
                    from { opacity: 0; transform: scale(0.95) translateY(-20px); }
                    to { opacity: 1; transform: scale(1) translateY(0); }
                }
                .cmd-header {
                    display: flex;
                    align-items: center;
                    padding: 1rem 1.5rem;
                    gap: 1rem;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                }
                .cmd-header input {
                    flex: 1;
                    background: transparent;
                    border: none;
                    color: white;
                    font-size: 1.1rem;
                    font-family: 'Inter', sans-serif;
                    outline: none;
                }
                .cmd-header kbd {
                    background: rgba(255, 255, 255, 0.1);
                    color: rgba(255, 255, 255, 0.4);
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 0.7rem;
                }
                .cmd-results {
                    max-height: 400px;
                    overflow-y: auto;
                    padding: 0.5rem;
                }
                .cmd-item {
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    padding: 0.75rem 1rem;
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.1s;
                    color: #94a3b8;
                }
                .cmd-item.selected {
                    background: rgba(14, 165, 233, 0.1);
                    color: white;
                }
                .cmd-item i { font-size: 1.2rem; }
                .cmd-item .cmd-label { flex: 1; font-weight: 500; }
                .cmd-item .cmd-meta { font-size: 0.75rem; opacity: 0.5; font-family: 'JetBrains Mono', monospace; }
                
                .cmd-empty { padding: 3rem; text-align: center; color: #64748b; font-size: 0.9rem; }
                
                .cmd-footer {
                    padding: 0.75rem 1.5rem;
                    background: rgba(0, 0, 0, 0.2);
                    border-top: 1px solid rgba(255, 255, 255, 0.05);
                    display: flex;
                    gap: 1.5rem;
                    font-size: 0.7rem;
                    color: #64748b;
                }
                .cmd-footer kbd { color: #94a3b8; margin-right: 2px; }
            </style>
        `;
        document.head.insertAdjacentHTML('beforeend', style);
    },

    bindEvents() {
        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }
            if (e.key === 'Escape' && this.isOpen) {
                this.toggle();
            }
        });

        const input = document.getElementById('cmd-input');
        input.addEventListener('input', () => this.search(input.value));
        input.addEventListener('keydown', (e) => this.handleNav(e));
    },

    toggle() {
        this.isOpen = !this.isOpen;
        const overlay = document.getElementById('command-bar-overlay');
        overlay.style.display = this.isOpen ? 'flex' : 'none';
        if (this.isOpen) {
            document.getElementById('cmd-input').focus();
            this.search('');
        }
    },

    async search(query) {
        const resultsContainer = document.getElementById('cmd-results');
        this.selectedIndex = 0;

        // Static Actions
        const actions = [
            { id: 'new-workshop', label: 'Create New Workshop', icon: 'ph-plus-circle', url: '/workshops/new', type: 'action' },
            { id: 'view-learners', label: 'View All Learners', icon: 'ph-users', url: '/learners', type: 'action' },
            { id: 'go-dashboard', label: 'Go to Dashboard', icon: 'ph-squares-four', url: '/admin/dashboard', type: 'action' }
        ];

        let filtered = actions.filter(a => a.label.toLowerCase().includes(query.toLowerCase()));

        if (query.length > 1) {
            try {
                // Fetch dynamic results (Workshops)
                const res = await fetch(`/api/website/workshops?q=${query}`, {
                    headers: { 'X-Service-Token': 'internal_key' } // Simulated
                });
                const data = await res.json();
                if (data.workshops) {
                    data.workshops.forEach(w => {
                        filtered.push({
                            id: w.id,
                            label: w.title,
                            icon: 'ph-presentation-chart',
                            url: `/workshops/${w.id}`,
                            type: 'workshop',
                            meta: w.start_date
                        });
                    });
                }
            } catch (e) {}
        }

        this.results = filtered;
        this.renderResults();
    },

    renderResults() {
        const container = document.getElementById('cmd-results');
        if (this.results.length === 0) {
            container.innerHTML = '<div class="cmd-empty">No results found.</div>';
            return;
        }

        container.innerHTML = this.results.map((r, i) => `
            <div class="cmd-item ${i === this.selectedIndex ? 'selected' : ''}" onclick="window.location.href='${r.url}'">
                <i class="ph ${r.icon}"></i>
                <div class="cmd-label">${r.label}</div>
                ${r.meta ? `<div class="cmd-meta">${r.meta}</div>` : ''}
            </div>
        `).join('');
    },

    handleNav(e) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex + 1) % this.results.length;
            this.renderResults();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = (this.selectedIndex - 1 + this.results.length) % this.results.length;
            this.renderResults();
        } else if (e.key === 'Enter') {
            const selected = this.results[this.selectedIndex];
            if (selected) window.location.href = selected.url;
        }
    }
};

document.addEventListener('DOMContentLoaded', () => CommandBar.init());
