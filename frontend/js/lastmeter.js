/**
 * OncologieWijzer Lastmeter Component
 * Self-contained distress thermometer with domain checklists and resource lookup.
 * All data stays client-side (localStorage, cleared on close).
 */

(function () {
    'use strict';

    var API_BASE = window.location.origin;
    var panel = document.getElementById('lastmeter-panel');
    var overlay = document.getElementById('lastmeter-overlay');
    var content = document.getElementById('lastmeter-content');
    var closeBtn = document.getElementById('lastmeter-close');

    var state = {
        step: 'thermometer', // thermometer | domains | summary
        score: 0,
        checkedDomains: [],
        resources: [],
        domainData: null,
    };

    // ===== Open / Close =====
    function openPanel() {
        resetState();
        panel.classList.add('open');
        overlay.classList.add('visible');
        renderStep();
    }

    function closePanel() {
        panel.classList.remove('open');
        overlay.classList.remove('visible');
        // Clear localStorage on close
        try { localStorage.removeItem('lastmeter_state'); } catch (e) { /* ignore */ }
    }

    function resetState() {
        state = {
            step: 'thermometer',
            score: 0,
            checkedDomains: [],
            resources: [],
            domainData: null,
        };
    }

    closeBtn.addEventListener('click', closePanel);
    overlay.addEventListener('click', closePanel);

    // Expose globally for app.js
    window.openLastmeter = openPanel;

    // ===== Rendering =====
    function renderStep() {
        switch (state.step) {
            case 'thermometer':
                renderThermometer();
                break;
            case 'domains':
                renderDomains();
                break;
            case 'summary':
                renderSummary();
                break;
        }
    }

    // ===== Step 1: Thermometer =====
    function renderThermometer() {
        var html = '<div class="lm-consent">' +
            'Uw antwoorden worden niet opgeslagen. Ze worden alleen gebruikt om relevante informatie te tonen.' +
            '</div>' +
            '<div class="lm-thermometer-container">' +
            '<h3>Hoe veel last heeft u?</h3>' +
            '<p class="lm-instruction">Schuif de thermometer naar het niveau dat past bij hoeveel last u de afgelopen week heeft ervaren.</p>' +
            '<div class="lm-thermo-visual">' +
            '<div class="lm-thermo-bar">' +
            '<div class="lm-thermo-fill" id="lm-thermo-fill" style="height: ' + (state.score * 10) + '%;"></div>' +
            '<div class="lm-thermo-marker" id="lm-thermo-marker" style="bottom: ' + (state.score * 10) + '%;"></div>' +
            '</div>' +
            '<div class="lm-thermo-labels">' +
            '<span class="lm-label-top">10 - Extreme last</span>' +
            '<span class="lm-label-mid">5</span>' +
            '<span class="lm-label-bottom">0 - Geen last</span>' +
            '</div>' +
            '</div>' +
            '<div class="lm-slider-wrap">' +
            '<input type="range" min="0" max="10" step="1" value="' + state.score + '" class="lm-slider" id="lm-slider" />' +
            '<div class="lm-score-display" id="lm-score-display">' + state.score + '</div>' +
            '</div>' +
            '<button class="lm-btn lm-btn-primary" id="lm-thermo-next">Volgende</button>' +
            '</div>';

        content.innerHTML = html;

        var slider = document.getElementById('lm-slider');
        var scoreDisplay = document.getElementById('lm-score-display');
        var fill = document.getElementById('lm-thermo-fill');
        var marker = document.getElementById('lm-thermo-marker');

        slider.addEventListener('input', function () {
            var val = parseInt(this.value, 10);
            state.score = val;
            scoreDisplay.textContent = val;
            fill.style.height = (val * 10) + '%';
            marker.style.bottom = (val * 10) + '%';
        });

        document.getElementById('lm-thermo-next').addEventListener('click', function () {
            if (state.score >= 4) {
                state.step = 'domains';
                fetchDomains();
            } else {
                state.step = 'summary';
                renderStep();
            }
        });
    }

    // ===== Fetch Domains =====
    function fetchDomains() {
        if (state.domainData) {
            renderDomains();
            return;
        }

        content.innerHTML = '<div class="lm-loading">Domeinen laden...</div>';

        fetch(API_BASE + '/lastmeter/domains')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                state.domainData = data;
                renderDomains();
            })
            .catch(function () {
                content.innerHTML = '<div class="lm-error">Kon domeinen niet laden. Probeer opnieuw.</div>' +
                    '<button class="lm-btn lm-btn-secondary" id="lm-retry">Opnieuw</button>';
                document.getElementById('lm-retry').addEventListener('click', fetchDomains);
            });
    }

    // ===== Step 2: Domain Checklists =====
    function renderDomains() {
        var domains = state.domainData || [];
        var html = '<div class="lm-consent">' +
            'Uw antwoorden worden niet opgeslagen. Ze worden alleen gebruikt om relevante informatie te tonen.' +
            '</div>' +
            '<h3>Op welke gebieden ervaart u problemen?</h3>' +
            '<p class="lm-instruction">Vink aan wat op u van toepassing is (afgelopen week).</p>' +
            '<div class="lm-domains">';

        for (var i = 0; i < domains.length; i++) {
            var domain = domains[i];
            html += '<div class="lm-domain-group">' +
                '<div class="lm-domain-header">' +
                '<span class="lm-domain-icon">' + domain.icon + '</span>' +
                '<span class="lm-domain-name">' + escapeHtml(domain.name) + '</span>' +
                '</div>' +
                '<div class="lm-domain-items">';

            for (var j = 0; j < domain.items.length; j++) {
                var item = domain.items[j];
                var key = domain.id + ':' + item.id;
                var checked = state.checkedDomains.indexOf(key) !== -1 ? ' checked' : '';
                html += '<label class="lm-checkbox-label">' +
                    '<input type="checkbox" class="lm-checkbox" data-domain="' + key + '"' + checked + ' />' +
                    '<span>' + escapeHtml(item.label) + '</span>' +
                    '</label>';
            }

            html += '</div></div>';
        }

        html += '</div>' +
            '<div class="lm-domain-actions">' +
            '<button class="lm-btn lm-btn-secondary" id="lm-domain-back">Terug</button>' +
            '<button class="lm-btn lm-btn-primary" id="lm-domain-next">Bekijk resultaten</button>' +
            '</div>';

        content.innerHTML = html;

        // Wire checkboxes
        var checkboxes = content.querySelectorAll('.lm-checkbox');
        checkboxes.forEach(function (cb) {
            cb.addEventListener('change', function () {
                var key = this.getAttribute('data-domain');
                if (this.checked) {
                    if (state.checkedDomains.indexOf(key) === -1) {
                        state.checkedDomains.push(key);
                    }
                } else {
                    state.checkedDomains = state.checkedDomains.filter(function (d) { return d !== key; });
                }
            });
        });

        document.getElementById('lm-domain-back').addEventListener('click', function () {
            state.step = 'thermometer';
            renderStep();
        });

        document.getElementById('lm-domain-next').addEventListener('click', function () {
            state.step = 'summary';
            if (state.checkedDomains.length > 0) {
                fetchResources();
            } else {
                renderStep();
            }
        });
    }

    // ===== Fetch Resources =====
    function fetchResources() {
        content.innerHTML = '<div class="lm-loading">Relevante informatie ophalen...</div>';

        fetch(API_BASE + '/lastmeter/resources', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domains: state.checkedDomains }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                state.resources = data;
                renderStep();
            })
            .catch(function () {
                state.resources = [];
                renderStep();
            });
    }

    // ===== Step 3: Summary =====
    function renderSummary() {
        var html = '<div class="lm-summary">';

        // Score
        var scoreClass = state.score >= 7 ? 'lm-score-high' : (state.score >= 4 ? 'lm-score-medium' : 'lm-score-low');
        html += '<div class="lm-summary-score ' + scoreClass + '">' +
            '<div class="lm-summary-score-number">' + state.score + '</div>' +
            '<div class="lm-summary-score-label">Uw lastmeter score</div>' +
            '</div>';

        if (state.score < 4) {
            html += '<div class="lm-summary-message lm-summary-ok">' +
                '<p>Uw score is relatief laag. Als u toch vragen heeft, kunt u altijd met uw zorgverlener praten of de chat gebruiken.</p>' +
                '</div>';
        } else {
            // Checked domains summary
            if (state.checkedDomains.length > 0) {
                html += '<h3>Probleemgebieden</h3>' +
                    '<div class="lm-checked-domains">';
                for (var i = 0; i < state.checkedDomains.length; i++) {
                    var parts = state.checkedDomains[i].split(':');
                    var domainLabel = getDomainLabel(parts[0]);
                    var itemLabel = getItemLabel(parts[0], parts[1]);
                    html += '<span class="lm-domain-tag">' + escapeHtml(domainLabel) + ': ' + escapeHtml(itemLabel) + '</span>';
                }
                html += '</div>';
            }

            // Resources
            if (state.resources.length > 0) {
                html += '<h3>Relevante informatie</h3>' +
                    '<div class="lm-resources">';
                for (var j = 0; j < state.resources.length; j++) {
                    var res = state.resources[j];
                    html += '<a class="lm-resource-card" href="' + escapeAttr(res.url) + '" target="_blank" rel="noopener">' +
                        '<div class="lm-resource-title">' + escapeHtml(res.title) + '</div>' +
                        '<div class="lm-resource-domain">' + escapeHtml(res.domain) + '</div>' +
                        '</a>';
                }
                html += '</div>';
            } else if (state.checkedDomains.length > 0) {
                html += '<p class="lm-no-resources">Geen specifieke bronnen gevonden voor uw selectie. Gebruik de chat om meer informatie te vragen.</p>';
            }

            html += '<div class="lm-summary-advice">' +
                '<p>Bespreek deze resultaten met uw zorgverlener. De Lastmeter kan helpen om het gesprek te starten.</p>' +
                '</div>';
        }

        html += '<div class="lm-summary-actions">' +
            '<button class="lm-btn lm-btn-secondary" id="lm-summary-restart">Opnieuw</button>' +
            '<button class="lm-btn lm-btn-secondary" id="lm-summary-print">Afdrukken</button>' +
            '<button class="lm-btn lm-btn-primary" id="lm-summary-chat">\uD83D\uDCAC Bespreek in chat</button>' +
            '</div>' +
            '</div>';

        content.innerHTML = html;

        document.getElementById('lm-summary-restart').addEventListener('click', function () {
            resetState();
            renderStep();
        });

        document.getElementById('lm-summary-print').addEventListener('click', function () {
            window.print();
        });

        document.getElementById('lm-summary-chat').addEventListener('click', function () {
            sendResultsToChat();
            closePanel();
        });
    }

    // ===== Send Lastmeter results into the chat =====
    function sendResultsToChat() {
        // Build a summary message from the Lastmeter results
        var parts = [];
        parts.push('Lastmeter resultaat: score ' + state.score + '/10.');

        if (state.checkedDomains.length > 0) {
            var domainDescriptions = [];
            for (var i = 0; i < state.checkedDomains.length; i++) {
                var keyParts = state.checkedDomains[i].split(':');
                var domainLabel = getDomainLabel(keyParts[0]);
                var itemLabel = getItemLabel(keyParts[0], keyParts[1]);
                domainDescriptions.push(domainLabel + ': ' + itemLabel);
            }
            parts.push('Probleemgebieden: ' + domainDescriptions.join(', ') + '.');
        }

        parts.push('Kun je me helpen met informatie en tips over deze klachten?');

        var message = parts.join(' ');

        // Use the global chat send function
        if (window.sendChatMessage) {
            window.sendChatMessage(message);
        }
    }

    // ===== Helpers =====
    function getDomainLabel(domainId) {
        if (!state.domainData) return domainId;
        for (var i = 0; i < state.domainData.length; i++) {
            if (state.domainData[i].id === domainId) return state.domainData[i].name;
        }
        return domainId;
    }

    function getItemLabel(domainId, itemId) {
        if (!state.domainData) return itemId;
        for (var i = 0; i < state.domainData.length; i++) {
            if (state.domainData[i].id === domainId) {
                var items = state.domainData[i].items;
                for (var j = 0; j < items.length; j++) {
                    if (items[j].id === itemId) return items[j].label;
                }
            }
        }
        return itemId;
    }

    function escapeHtml(text) {
        var map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, function (c) { return map[c]; });
    }

    function escapeAttr(text) {
        return String(text).replace(/"/g, '&quot;').replace(/'/g, '&#039;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

})();
