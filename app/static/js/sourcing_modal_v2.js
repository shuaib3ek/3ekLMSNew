/**
 * Sourcing Modal Controller (V2.2 Robust)
 */

(function () {
    let modalSelectedTrainers = new Set();

    // --- MODAL CONTROL ---
    window.openSourcingModal = function (mode) {
        const modal = document.getElementById('sourcingModal');
        if (modal) {
            // Force flex display for layout stability
            modal.style.display = 'flex';

            try {
                if (typeof modal.showModal === 'function' && !modal.open) {
                    modal.showModal();
                }
            } catch (e) {
                console.error('Dialog showModal failed:', e);
                modal.setAttribute('open', '');
            }

            const pulseToggle = document.getElementById('modalPulseToggle');

            // Handle pulse auto-trigger
            if (mode === 'pulse') {
                if (pulseToggle) {
                    pulseToggle.checked = true;
                    setTimeout(() => togglePulseMode(pulseToggle), 50);
                    return;
                }
            } else {
                if (pulseToggle) {
                    pulseToggle.checked = false;
                    togglePulseMode(pulseToggle);
                }
            }

            // Sync with page-level quick search
            const quickInput = document.getElementById('quickTrainerSearch_V2') || document.getElementById('quickTrainerSearch');
            if (quickInput && quickInput.value && (!pulseToggle || !pulseToggle.checked)) {
                const skillInput = document.getElementById('modalSkillSearch');
                if (skillInput) skillInput.value = quickInput.value;
            }

            applyModalFilters();
        }
    }

    window.closeSourcingModal = function () {
        const modal = document.getElementById('sourcingModal');
        if (modal) {
            try {
                if (typeof modal.close === 'function') {
                    modal.close();
                }
            } catch (e) { }
            modal.removeAttribute('open');
            modal.style.display = 'none';
        }
    }

    // --- TABS ---
    window.switchModalTab = function (tab) {
        const bodyInternal = document.getElementById('modalBodyInternal');
        const bodyDiscovery = document.getElementById('modalBodyDiscovery');
        const tabInt = document.getElementById('tab-internal');
        const tabDisc = document.getElementById('tab-discovery-new');

        if (tab === 'internal') {
            if (bodyInternal) bodyInternal.style.display = 'flex';
            if (bodyDiscovery) bodyDiscovery.style.display = 'none';
            if (tabInt) tabInt.classList.add('active');
            if (tabDisc) tabDisc.classList.remove('active');
        } else {
            if (bodyInternal) bodyInternal.style.display = 'none';
            if (bodyDiscovery) bodyDiscovery.style.display = 'flex';
            if (tabInt) tabInt.classList.remove('active');
            if (tabDisc) tabDisc.classList.add('active');
        }
    }

    // --- SEARCH ---
    window.togglePulseMode = function (checkbox) {
        const isPulse = checkbox.checked;
        const skillGroup = document.getElementById('skillInputGroup');
        const contextMsg = document.getElementById('pulseContext');

        if (isPulse) {
            if (skillGroup) {
                skillGroup.style.opacity = '0.4';
                skillGroup.style.pointerEvents = 'none';
            }
            if (contextMsg) contextMsg.style.display = 'block';
        } else {
            if (skillGroup) {
                skillGroup.style.opacity = '1';
                skillGroup.style.pointerEvents = 'auto';
            }
            if (contextMsg) contextMsg.style.display = 'none';
        }

        applyModalFilters();
    };

    window.applyModalFilters = async function () {
        const nameInput = document.getElementById('modalNameSearch');
        const skillInput = document.getElementById('modalSkillSearch');
        const locationInput = document.getElementById('modalLocationSearch');
        const rateInput = document.getElementById('modalMaxRate');
        const pulseInput = document.getElementById('modalPulseToggle');

        const name = nameInput ? nameInput.value : '';
        const skill = skillInput ? skillInput.value : '';
        const location = locationInput ? locationInput.value : '';
        const rate = rateInput ? rateInput.value : '';
        const usePulse = pulseInput ? pulseInput.checked : false;

        const resultsList = document.getElementById('modalResultsList');
        if (!resultsList) return;

        resultsList.innerHTML = `
            <div style="grid-column: 1/-1; text-align:center; padding: 5rem 2rem;">
                <i class="ph ph-circle-notch loading-spinner" style="font-size: 2.5rem; color: #6366f1;"></i>
                <p style="margin-top: 1.5rem; color: #64748b; font-weight: 600;">Scanning Database...</p>
            </div>
        `;

        try {
            const inquiryId = window.CURRENT_INQUIRY_ID;
            const params = new URLSearchParams({
                q: skill,
                name: name,
                inquiry_id: inquiryId,
                location: location,
                _b: Date.now()
            });
            if (rate) params.append('max_rate', rate);
            if (usePulse) params.append('semantic', 'true');

            const response = await fetch(`/ops/api/trainers/quick-search?${params.toString()}`);
            const trainers = await response.json();

            renderModalResults(trainers);
            const countSpan = document.getElementById('modalResultCount');
            if (countSpan) countSpan.innerText = `${trainers.length} Items`;

        } catch (err) {
            resultsList.innerHTML = `<div style="grid-column: 1/-1; color:#ef4444; padding:4rem; text-align:center;">Failed to fetch results</div>`;
        }
    }

    function renderModalResults(trainers) {
        const container = document.getElementById('modalResultsList');
        if (!trainers.length) {
            container.innerHTML = `
                <div style="padding: 5rem 2rem; text-align: center; color: #64748b;">
                    <i class="ph ph-magnifying-glass" style="font-size: 2.5rem; opacity: 0.3;"></i>
                    <p style="margin-top: 1rem; font-weight: 700; font-size: 0.8rem; text-transform: uppercase;">Reference Scanning: 0 Results</p>
                </div>`;
            return;
        }

        container.innerHTML = trainers.map(t => {
            if (t.already_mapped) {
                return `
                <div class="trainer-row" style="opacity:0.5; background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 1.5rem;">
                    <div style="flex: 1; font-weight:700; color:#0f172a; font-size: 0.85rem;">${t.name}</div>
                    <div style="font-size:0.65rem; font-weight: 700; color:#64748b; background: #f1f5f9; padding: 4px 10px; border-radius: 4px; text-transform: uppercase; border: 1px solid #e2e8f0;">Mapped Presence</div>
                </div>`;
            }

            const isSelected = modalSelectedTrainers.has(t.id);
            return `
            <div class="trainer-row ${isSelected ? 'selected' : ''}" 
                 onclick="toggleTrainerSelection(${t.id})" 
                 id="card-${t.id}"
                 data-trainer='${JSON.stringify(t).replace(/'/g, "&#39;")}'
                 style="background: ${isSelected ? '#f8fafc' : '#fff'}; border-bottom: 1px solid #e2e8f0; padding: 0.75rem 1.5rem; cursor: pointer; transition: all 0.1s; display: flex; align-items: center; gap: 1.5rem; position: relative;">
                
                <div style="position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: ${isSelected ? '#0f172a' : 'transparent'};"></div>

                <input type="checkbox" class="card-checkbox" 
                       onclick="event.stopPropagation(); toggleTrainerSelection(${t.id})" 
                       ${isSelected ? 'checked' : ''}
                       style="width: 1.1rem; height: 1.1rem; flex-shrink: 0; cursor: pointer;">

                <div style="flex: 2; min-width: 180px;">
                    <div style="font-weight:700; color: #0f172a; font-size: 0.9rem; display: flex; align-items: center; gap: 6px;">
                        ${t.name} ${t.verified ? '<i class="ph ph-seal-check-fill" style="color: #0ea5e9;"></i>' : ''}
                    </div>
                </div>

                <div style="flex: 4; font-size: 0.8rem; color: #334155; font-weight: 500; line-height: 1.4;">
                    ${t.skills}
                </div>

                <div style="flex: 2; display: flex; gap: 10px; justify-content: flex-end; align-items: center;">
                    <span style="font-size: 0.7rem; color: #475569; font-weight: 600; text-transform: uppercase;"><i class="ph ph-map-pin-fill" style="color: #64748b;"></i> ${t.location || 'Remote'}</span>
                    <span style="font-size: 0.7rem; color: #0f172a; font-weight: 700; background: #f1f5f9; padding: 4px 10px; border-radius: 4px; border: 1px solid #e2e8f0;">₹${t.rate}/HR</span>
                </div>
            </div>`;
        }).join('');
    }

    // --- SELECTION ---
    window.toggleTrainerSelection = function (id) {
        if (modalSelectedTrainers.has(id)) {
            modalSelectedTrainers.delete(id);
        } else {
            modalSelectedTrainers.add(id);
        }
        updateSelectionUI();
    }

    window.clearModalSelection = function () {
        modalSelectedTrainers.clear();
        updateSelectionUI();
    }

    function updateSelectionUI() {
        const idsContainer = document.getElementById('modalSelectedIdsContainer');
        const countMain = document.getElementById('selectedCount');
        const countSide = document.getElementById('selectedCountSide');
        const namesContainer = document.getElementById('selectedNamesSide');
        const sideBox = document.getElementById('modalSelectionBox');

        if (countMain) countMain.innerText = modalSelectedTrainers.size;
        if (countSide) countSide.innerText = modalSelectedTrainers.size;

        if (idsContainer) idsContainer.innerHTML = '';
        let namesHtml = [];

        modalSelectedTrainers.forEach(id => {
            if (idsContainer) {
                const input = document.createElement('input');
                input.type = 'hidden', input.name = 'trainer_ids', input.value = id;
                idsContainer.appendChild(input);
            }

            const card = document.getElementById(`card-${id}`);
            if (card && card.dataset.trainer) {
                try {
                    const t = JSON.parse(card.dataset.trainer);
                    namesHtml.push(`
                        <div style="display: flex; align-items: center; justify-content: space-between; background: #eff6ff; padding: 6px 10px; border-radius: 8px; border: 1px solid #dbeafe;">
                            <span style="font-weight: 700; color: #1e40af; font-size: 0.75rem;">${t.name}</span>
                            <i class="ph ph-minus-circle" onclick="event.stopPropagation(); toggleTrainerSelection(${id})" style="color: #6366f1; cursor: pointer;"></i>
                        </div>`);
                } catch (e) { }
            }
        });

        if (namesContainer) namesContainer.innerHTML = namesHtml.join('');
        if (sideBox) sideBox.style.display = modalSelectedTrainers.size > 0 ? 'flex' : 'none';

        const hasSelection = modalSelectedTrainers.size > 0;
        const btnMap = document.getElementById('btnMapSelected');
        const btnEmail = document.getElementById('btnModalEmail');
        const btnWhatsapp = document.getElementById('btnModalWhatsapp');

        [btnMap, btnEmail, btnWhatsapp].forEach(btn => {
            if (btn) {
                btn.disabled = !hasSelection;
                btn.style.opacity = hasSelection ? '1' : '0.5';
            }
        });

        document.querySelectorAll('.trainer-row').forEach(card => {
            const id = parseInt(card.id.replace('card-', ''));
            const isSel = modalSelectedTrainers.has(id);
            card.classList.toggle('selected', isSel);
            const cb = card.querySelector('input');
            if (cb) cb.checked = isSel;
        });
    }

    // --- ACTIONS ---
    window.mapSelectedTrainers = async function () {
        const btn = document.getElementById('btnMapSelected');
        if (btn) btn.innerText = 'Mapping...', btn.disabled = true;

        const inquiryId = window.CURRENT_INQUIRY_ID;
        let successCount = 0;

        for (let trainerId of modalSelectedTrainers) {
            try {
                const response = await fetch(`/ops/api/inquiries/${inquiryId}/quick-map-trainer`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' },
                    body: JSON.stringify({ trainer_id: trainerId })
                });
                if (response.ok) successCount++;
            } catch (e) { }
        }
        alert(`Mapped ${successCount} trainers successfully!`);
        location.reload();
    }

    window.submitModalReachOut = async function (type) {
        const form = document.getElementById('modalReachOutForm');
        const url = type === 'email' ? form.dataset.emailUrl : form.dataset.whatsappUrl;
        const msg = document.getElementById('modalBulkMsg').value;

        const btnE = document.getElementById('btnModalEmail'), btnW = document.getElementById('btnModalWhatsapp');
        if (btnE) btnE.disabled = true, btnE.innerText = 'Sending...';
        if (btnW) btnW.disabled = true, btnW.innerText = 'Sending...';

        try {
            const fd = new FormData();
            fd.append('inquiry_id', window.CURRENT_INQUIRY_ID);
            fd.append('message', msg);
            fd.append('subject', `Training Inquiry: {{ inquiry.topic|safe }}`);
            modalSelectedTrainers.forEach(id => fd.append('trainer_ids', id));

            const res = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' }, body: fd });
            if (res.ok) { alert('Messages sent!'); closeSourcingModal(); } else { throw new Error('Send failed'); }
        } catch (e) { alert(e.message); } finally {
            if (btnE) btnE.disabled = false, btnE.innerText = 'Send Email';
            if (btnW) btnW.disabled = false, btnW.innerText = 'Send WhatsApp';
        }
    }

    // --- AI DISCOVERY ---
    window.startDiscoveryScan = async function () {
        const btn = document.getElementById('btnDiscoveryScanMain');
        const resultsDiv = document.getElementById('discoveryResults');
        if (btn) btn.disabled = true, btn.innerHTML = '<i class="ph ph-circle-notch loading-spinner"></i> Searching Market...';

        resultsDiv.innerHTML = `<div style="text-align:center; padding: 4rem;"><i class="ph ph-sparkle loading-spinner" style="font-size: 3rem; color: #0ea5e9;"></i><h3 style="margin-top:2rem;">Deploying AI Discovery Agents...</h3></div>`;

        try {
            const res = await fetch('/ops/api/trainers/external-discovery', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' }, body: JSON.stringify({ inquiry_id: window.CURRENT_INQUIRY_ID }) });
            const data = await res.json();

            if (data.success && data.results?.length > 0) {
                resultsDiv.innerHTML = `<div style="display: flex; flex-direction: column; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;">` +
                    data.results.map(r => `
                        <div style="background: white; border-bottom: 1px solid #e2e8f0; padding: 1.25rem 1.5rem; display: flex; align-items: flex-start; gap: 1.5rem; transition: all 0.1s;">
                            <div style="flex: 1; min-width: 250px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                    <div style="font-weight: 900; color: #0f172a; font-size: 0.95rem;">${r.name}</div>
                                    <a href="${r.link}" target="_blank" style="background:#0077b5; color:white; padding:4px 10px; border-radius:4px; font-weight:900; text-decoration:none; font-size:0.65rem; display: flex; align-items: center; gap: 5px; text-transform: uppercase;">
                                        <i class="ph ph-linkedin-logo-fill"></i> LinkedIn
                                    </a>
                                </div>
                                <div style="font-size:0.75rem; color:#334155; font-weight:700; line-height:1.4;">${r.headline}</div>
                            </div>
                            <div style="flex: 1; background:#f9fafb; padding:10px 15px; border-radius:6px; font-size:0.75rem; color:#475569; font-weight: 600; line-height: 1.5; border: 1px solid #f1f5f9;">
                                "${r.snippet}"
                            </div>
                        </div>`).join('') + `</div>`;
            } else { resultsDiv.innerHTML = `<div style="text-align:center; padding:4rem; opacity:0.5;"><i class="ph ph-info" style="font-size: 2rem;"></i><p style="margin-top:1rem; font-weight:900; font-size: 0.75rem; text-transform: uppercase;">Reference Scan: 0 External Matches</p></div>`; }
        } catch (e) { resultsDiv.innerHTML = `<div style="text-align:center; padding:4rem; color:red;">Scan failed.</div>`; } finally {
            if (btn) btn.disabled = false, btn.innerHTML = '<i class="ph ph-rocket-launch"></i> Launch External Discovery';
        }
    }

})();
