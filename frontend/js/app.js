/**
 * KankerWijzer Chat Application
 * Frontend for the IKNL Medical-Grade Cancer Information System
 */

(function () {
    'use strict';

    // ===== Configuration =====
    const API_BASE = window.location.origin;
    const API_ENDPOINT = API_BASE + '/agent/answer';

    // Source badge color mapping
    const SOURCE_COLORS = {
        'kanker.nl': '#2196F3',
        'nkr-cijfers': '#4CAF50',
        'kankeratlas': '#FF9800',
        'richtlijnendatabase': '#9C27B0',
        'iknl-reports': '#607D8B',
        'scientific-publications': '#795548',
    };

    // Friendly source labels
    const SOURCE_LABELS = {
        'kanker.nl': 'Kanker.nl',
        'nkr-cijfers': 'NKR Cijfers',
        'kankeratlas': 'Kanker Atlas',
        'richtlijnendatabase': 'Richtlijnen',
        'iknl-reports': 'IKNL Rapport',
        'scientific-publications': 'Wetenschappelijk',
    };

    // ===== DOM Elements =====
    const chatArea = document.getElementById('chat-area');
    const messagesEl = document.getElementById('messages');
    const welcomeScreen = document.getElementById('welcome-screen');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('btn-new-chat');
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const audienceSelect = document.getElementById('audience');
    const exampleButtons = document.querySelectorAll('.example-q');
    const lastmeterBtn = document.getElementById('btn-lastmeter');

    // ===== State =====
    let isLoading = false;
    let messageCount = 0;

    // ===== Initialize =====
    function init() {
        // Input events
        userInput.addEventListener('input', onInputChange);
        userInput.addEventListener('keydown', onInputKeydown);
        sendBtn.addEventListener('click', onSend);

        // New chat
        newChatBtn.addEventListener('click', resetChat);

        // Example questions
        exampleButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var question = btn.getAttribute('data-question');
                userInput.value = question;
                onInputChange();
                onSend();
            });
        });

        // Mobile sidebar
        menuToggle.addEventListener('click', toggleSidebar);
        sidebarOverlay.addEventListener('click', closeSidebar);

        // Lastmeter - open the panel (handled by lastmeter.js)
        lastmeterBtn.addEventListener('click', function () {
            if (window.openLastmeter) {
                window.openLastmeter();
            }
        });

        // Focus input
        userInput.focus();
    }

    // ===== Input Handling =====
    function onInputChange() {
        var hasText = userInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isLoading;

        // Auto-resize textarea
        userInput.style.height = 'auto';
        userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
    }

    function onInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                onSend();
            }
        }
    }

    // ===== Send Message =====
    function onSend() {
        var query = userInput.value.trim();
        if (!query || isLoading) return;

        // Hide welcome screen
        welcomeScreen.classList.add('hidden');

        // Add user message
        addUserMessage(query);

        // Clear input
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;

        // Show loading
        var loadingEl = addLoadingIndicator();

        // Close mobile sidebar
        closeSidebar();

        // Make API call
        isLoading = true;
        var audience = audienceSelect.value;

        fetch(API_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, audience: audience }),
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Server fout (HTTP ' + response.status + ')');
                }
                return response.json();
            })
            .then(function (data) {
                loadingEl.remove();
                handleApiResponse(data);
            })
            .catch(function (err) {
                loadingEl.remove();
                addErrorMessage(
                    'Er ging iets mis bij het ophalen van het antwoord. Probeer het opnieuw. (' + err.message + ')'
                );
            })
            .finally(function () {
                isLoading = false;
                onInputChange();
                userInput.focus();
            });
    }

    // ===== Handle API Response =====
    function handleApiResponse(data) {
        if (data.refusal_reason) {
            var contacts = data.contacts || [];
            var severity = data.severity || 'info';
            addRefusalMessage(data.refusal_reason, contacts, severity);
            return;
        }

        var answer = data.answer_markdown || 'Geen antwoord ontvangen.';
        var citations = data.citations || [];
        var confidence = data.confidence;
        var confidenceLabel = data.confidence_label;
        addAIMessage(answer, citations, confidence, confidenceLabel);
    }

    // ===== Message Rendering =====
    function addUserMessage(text) {
        messageCount++;
        var div = document.createElement('div');
        div.className = 'message-user';
        div.innerHTML = '<div class="bubble">' + escapeHtml(text) + '</div>';
        messagesEl.appendChild(div);
        scrollToBottom();
    }

    function addAIMessage(markdown, citations, confidence, confidenceLabel) {
        messageCount++;
        var msgId = 'msg-' + messageCount;

        var div = document.createElement('div');
        div.className = 'message-ai';
        div.id = msgId;

        // Header
        var header = document.createElement('div');
        header.className = 'ai-header';
        header.innerHTML =
            '<div class="ai-avatar">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="#00A67E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="12" cy="12" r="10"/>' +
            '<path d="M12 8v4M12 16h.01"/>' +
            '</svg>' +
            '</div>' +
            '<span class="ai-name">KankerWijzer</span>';

        // Confidence badge next to name
        if (confidence !== null && confidence !== undefined) {
            var confBadge = document.createElement('span');
            confBadge.className = 'confidence-badge confidence-' + getConfidenceClass(confidenceLabel);
            var pct = Math.round(confidence * 100);
            confBadge.innerHTML =
                'Onderbouwing: ' + getConfidenceDisplayLabel(confidenceLabel) +
                ' <span class="conf-label">(' + pct + '% bronmatch)</span>';
            confBadge.title = 'Deze score vat bronmatch, dekking en citaatdichtheid samen. Het is geen medische zekerheid.';
            header.appendChild(confBadge);
        }

        // Bubble with content
        var bubble = document.createElement('div');
        bubble.className = 'bubble';

        var htmlContent = renderMarkdown(markdown);
        htmlContent = replaceSrcReferences(htmlContent, citations);
        bubble.innerHTML = htmlContent;

        // Convert option-like list items into clickable suggestion buttons
        addClickableOptions(bubble);

        // Citations section with per-source relevance
        if (citations.length > 0) {
            var citationsEl = renderCitations(citations);
            bubble.appendChild(citationsEl);
        }

        // Feedback
        var feedback = createFeedbackRow(msgId);

        div.appendChild(header);
        div.appendChild(bubble);
        div.appendChild(feedback);

        messagesEl.appendChild(div);
        scrollToBottom();
    }

    function getConfidenceClass(label) {
        if (label === 'zeer laag') return 'zeer-laag';
        return label || 'gemiddeld';
    }

    function getConfidenceDisplayLabel(label) {
        switch (label) {
            case 'hoog': return 'sterk';
            case 'gemiddeld': return 'redelijk';
            case 'laag': return 'beperkt';
            case 'zeer laag': return 'zwak';
            default: return 'onbekend';
        }
    }

    // ===== Clickable Options for Clarification =====
    function makeOptionBtn(container, rawText) {
        var text = rawText.replace(/^\s*[-*\u2022\u25CF\u25B8\u25BA]+\s*/, '').replace(/\*\*/g, '').trim();
        // Strip leading emojis
        text = text.replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}]+\s*/u, '').trim();
        if (text.length < 2) return;
        var btn = document.createElement('button');
        btn.className = 'clarification-btn';
        btn.textContent = text;
        btn.addEventListener('click', function () {
            userInput.value = text;
            onInputChange();
            onSend();
        });
        container.appendChild(btn);
    }

    function addClickableOptions(bubble) {
        // Strategy 1: <ul>/<ol> lists after a question
        var lists = bubble.querySelectorAll('ul, ol');
        lists.forEach(function (list) {
            var prev = list.previousElementSibling;
            var isAfterQuestion = prev && prev.textContent && prev.textContent.indexOf('?') !== -1;
            var items = list.querySelectorAll('li');
            var allShort = true;
            items.forEach(function (li) { if (li.textContent.length > 80) allShort = false; });
            if (isAfterQuestion && allShort && items.length >= 2 && items.length <= 12) {
                var optDiv = document.createElement('div');
                optDiv.className = 'clarification-options';
                items.forEach(function (li) { makeOptionBtn(optDiv, li.textContent); });
                list.replaceWith(optDiv);
            }
        });

        // Strategy 2: Emoji/bullet lines in paragraphs (🔹 Borstkanker, 🩺 Longkanker, etc.)
        var fullText = bubble.textContent || '';
        if (fullText.indexOf('?') === -1) return;

        // Collect all text nodes to find question + options pattern
        var allP = bubble.querySelectorAll('p');
        var questionSeen = false;
        var optionTexts = [];
        var elementsToReplace = [];

        allP.forEach(function (el) {
            var txt = el.textContent.trim();
            if (txt.indexOf('?') !== -1 && txt.length > 10) {
                questionSeen = true;
                optionTexts = [];
                elementsToReplace = [];
                return;
            }
            if (!questionSeen) return;

            // Split on <br> tags
            var lines = el.innerHTML.split(/<br\s*\/?>/);
            var found = [];
            lines.forEach(function (line) {
                var clean = line.replace(/<[^>]+>/g, '').trim();
                if (clean.length < 2 || clean.length > 80) return;
                // Detect option lines: start with emoji, bullet, dash, or are short capitalized words
                var isOption = /^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u2022\u25CF\u25B8\u25BA\-]/u.test(clean);
                if (!isOption && /^[A-Z\u00C0-\u024F]/.test(clean) && clean.length < 40) isOption = true;
                if (isOption) {
                    var label = clean.replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u2022\u25CF\u25B8\u25BA\-\s]+/u, '').replace(/\*\*/g, '').trim();
                    if (label.length >= 2) found.push(label);
                }
            });
            if (found.length >= 2) {
                optionTexts = optionTexts.concat(found);
                elementsToReplace.push(el);
            }
        });

        if (optionTexts.length >= 2 && optionTexts.length <= 15 && elementsToReplace.length > 0) {
            var optDiv2 = document.createElement('div');
            optDiv2.className = 'clarification-options';
            var seen = {};
            optionTexts.forEach(function (t) {
                if (seen[t]) return;
                seen[t] = true;
                makeOptionBtn(optDiv2, t);
            });
            elementsToReplace[0].replaceWith(optDiv2);
            for (var k = 1; k < elementsToReplace.length; k++) {
                elementsToReplace[k].remove();
            }
        }
    }

    function addRefusalMessage(reason, contacts, severity) {
        messageCount++;
        contacts = contacts || [];
        severity = severity || 'info';

        var div = document.createElement('div');
        div.className = 'message-ai';

        var header = document.createElement('div');
        header.className = 'ai-header';
        header.innerHTML =
            '<div class="ai-avatar">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="#00A67E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="12" cy="12" r="10"/>' +
            '<path d="M12 8v4M12 16h.01"/>' +
            '</svg>' +
            '</div>' +
            '<span class="ai-name">KankerWijzer</span>';

        // Refusal box with severity-based styling
        var box = document.createElement('div');
        box.className = 'refusal-box refusal-' + severity;

        var severityIcon = severity === 'critical' ? '\u{1F6A8}' :
                          severity === 'urgent' ? '\u{1F49C}' : '\u26A0\uFE0F';
        box.innerHTML =
            '<div class="refusal-heading">' + getSeverityLabel(severity) + '</div>' +
            '<div><span class="refusal-icon">' + severityIcon + '</span> ' + escapeHtml(reason) + '</div>';

        div.appendChild(header);
        div.appendChild(box);

        // Render contact cards if present
        if (contacts.length > 0) {
            var contactsSection = document.createElement('div');
            contactsSection.className = 'contacts-section';

            var contactsTitle = document.createElement('div');
            contactsTitle.className = 'contacts-title';
            contactsTitle.textContent = 'Direct contact opnemen:';
            contactsSection.appendChild(contactsTitle);

            contacts.forEach(function (contact) {
                var card = document.createElement('div');
                card.className = 'contact-card contact-' + (contact.icon || 'support');

                var cardIcon = getContactIcon(contact.icon);
                var cardContent = '<div class="contact-icon">' + cardIcon + '</div>';
                cardContent += '<div class="contact-info">';
                cardContent += '<div class="contact-name">' + escapeHtml(contact.name) + '</div>';

                if (contact.description) {
                    cardContent += '<div class="contact-desc">' + escapeHtml(contact.description) + '</div>';
                }

                cardContent += '<div class="contact-actions">';

                if (contact.phone) {
                    var cleanPhone = contact.phone.replace(/[\s-]/g, '');
                    cardContent += '<a href="tel:' + cleanPhone + '" class="contact-btn contact-btn-phone">' +
                        'Bel ' + escapeHtml(contact.phone) + '</a>';
                }

                if (contact.email) {
                    cardContent += '<a href="mailto:' + escapeAttr(contact.email) + '" class="contact-btn contact-btn-email">' +
                        'Mail ' + escapeHtml(contact.email) + '</a>';
                }

                if (contact.url) {
                    cardContent += '<a href="' + escapeAttr(contact.url) + '" target="_blank" rel="noopener" class="contact-btn contact-btn-web">' +
                        'Open website</a>';
                }

                cardContent += '</div></div>';
                card.innerHTML = cardContent;

                contactsSection.appendChild(card);
            });

            div.appendChild(contactsSection);
        }

        messagesEl.appendChild(div);
        scrollToBottom();
    }

    function getSeverityLabel(severity) {
        switch (severity) {
            case 'critical': return 'Direct handelen';
            case 'urgent': return 'Direct steun inschakelen';
            default: return 'Bespreek dit met een zorgverlener';
        }
    }

    function getContactIcon(iconType) {
        switch (iconType) {
            case 'emergency': return '112';
            case 'crisis': return '113';
            case 'medical': return 'Arts';
            case 'support': return 'Hulp';
            default: return 'Info';
        }
    }

    function addErrorMessage(text) {
        var div = document.createElement('div');
        div.className = 'message-ai';

        var box = document.createElement('div');
        box.className = 'error-box';
        box.textContent = text;

        div.appendChild(box);
        messagesEl.appendChild(div);
        scrollToBottom();
    }

    function addLoadingIndicator() {
        var div = document.createElement('div');
        div.className = 'message-ai loading-message';
        div.innerHTML =
            '<div class="ai-header">' +
            '<div class="ai-avatar">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="#00A67E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<circle cx="12" cy="12" r="10"/>' +
            '<path d="M12 8v4M12 16h.01"/>' +
            '</svg>' +
            '</div>' +
            '<span class="ai-name">KankerWijzer</span>' +
            '</div>' +
            '<div class="loading-indicator">' +
            '<div class="loading-dots"><span></span><span></span><span></span></div>' +
            '<span class="loading-text">Bezig met zoeken in betrouwbare bronnen...</span>' +
            '</div>';
        messagesEl.appendChild(div);
        scrollToBottom();
        return div;
    }

    // ===== Markdown Rendering =====
    function renderMarkdown(text) {
        if (!text) return '';

        var html = escapeHtml(text);

        // Headers: ### Header
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');

        // Bold: **text**
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Italic: *text*
        html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

        // Unordered lists
        html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

        // Ordered lists
        html = html.replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>');
        // Wrap consecutive <li> not inside <ul> into <ol>
        html = html.replace(/(<li>(?:(?!<\/?[uo]l>).)*<\/li>(?:\n<li>(?:(?!<\/?[uo]l>).)*<\/li>)*)/g, function(match) {
            if (match.indexOf('<ul>') === -1) {
                // Check if it's already wrapped
                return '<ol>' + match + '</ol>';
            }
            return match;
        });

        // Line breaks: double newline = paragraph break
        html = html.replace(/\n\n/g, '</p><p>');
        // Single newlines (not inside lists)
        html = html.replace(/\n(?!<)/g, '<br>');

        // Wrap in paragraph
        html = '<p>' + html + '</p>';

        // Clean up empty paragraphs
        html = html.replace(/<p>\s*<\/p>/g, '');
        // Remove <p> wrapping around block elements
        html = html.replace(/<p>(<[huo])/g, '$1');
        html = html.replace(/(<\/[huo]l>|<\/h3>)<\/p>/g, '$1');

        return html;
    }

    // ===== Source References =====
    function replaceSrcReferences(html, citations) {
        return html.replace(/\[SRC-(\d+)\]/g, function (match, num) {
            var idx = parseInt(num, 10) - 1;
            if (idx >= 0 && idx < citations.length) {
                var cite = citations[idx];
                var url = cite.url || '#';
                var title = cite.title || 'Bron ' + num;
                return (
                    '<a class="src-ref" href="' + escapeAttr(url) + '" target="_blank" rel="noopener" ' +
                    'title="' + escapeAttr(title) + '">' +
                    num + '</a>'
                );
            }
            return match;
        });
    }

    // ===== Citations Section =====
    function renderCitations(citations) {
        var section = document.createElement('div');
        section.className = 'citations-section';

        var title = document.createElement('div');
        title.className = 'citations-title';
        title.textContent = 'Bronnen en onderbouwing';
        section.appendChild(title);

        var list = document.createElement('div');
        list.className = 'citations-list';

        citations.forEach(function (cite, index) {
            var item = document.createElement('div');
            item.className = 'citation-item';

            var sourceId = cite.source_id || 'unknown';
            var color = getSourceColor(sourceId);
            var label = getSourceLabel(sourceId);
            var num = index + 1;

            var badge = document.createElement('div');
            badge.className = 'citation-badge';
            badge.style.background = color;
            badge.textContent = num;

            var info = document.createElement('div');
            info.className = 'citation-info';

            var titleEl = document.createElement('div');
            titleEl.className = 'title';
            titleEl.textContent = cite.title || 'Bron ' + num;

            var sourceLabelEl = document.createElement('div');
            sourceLabelEl.className = 'source-label';
            sourceLabelEl.textContent = label + (cite.publisher ? ' \u2014 ' + cite.publisher : '');

            info.appendChild(titleEl);
            info.appendChild(sourceLabelEl);

            var contextParts = [];
            if (cite.page_number !== null && cite.page_number !== undefined) {
                contextParts.push('Pagina ' + cite.page_number);
            }
            if (cite.section) {
                contextParts.push('Sectie ' + cite.section);
            }
            if (cite.fetched_at) {
                var formattedDate = formatDate(cite.fetched_at);
                if (formattedDate) {
                    contextParts.push('Vastgelegd ' + formattedDate);
                }
            }
            if (contextParts.length > 0) {
                var metaEl = document.createElement('div');
                metaEl.className = 'citation-meta';
                metaEl.textContent = contextParts.join(' • ');
                info.appendChild(metaEl);
            }

            // Per-source relevance score bar
            if (cite.relevance_score !== null && cite.relevance_score !== undefined) {
                var scoreBar = document.createElement('div');
                scoreBar.className = 'relevance-bar-container';
                var pct = Math.round(cite.relevance_score * 100);
                var barColor = pct >= 75 ? '#4CAF50' : pct >= 50 ? '#FF9800' : '#f44336';
                scoreBar.innerHTML =
                    '<span class="relevance-label">Relevantie: ' + pct + '%</span>' +
                    '<div class="relevance-bar"><div class="relevance-fill" style="width:' + pct + '%;background:' + barColor + '"></div></div>';
                info.appendChild(scoreBar);
            }

            if (cite.excerpt) {
                var excerptEl = document.createElement('div');
                excerptEl.className = 'citation-excerpt';
                excerptEl.textContent = cite.excerpt;
                info.appendChild(excerptEl);
            }

            var policyNote = getSourcePolicyNote(sourceId);
            if (policyNote) {
                var noteEl = document.createElement('div');
                noteEl.className = 'citation-note';
                noteEl.textContent = policyNote;
                info.appendChild(noteEl);
            }

            var citationUrl = getPrimaryCitationUrl(cite);
            if (citationUrl) {
                var actionsEl = document.createElement('div');
                actionsEl.className = 'citation-actions';

                var urlEl = document.createElement('a');
                urlEl.className = 'citation-link';
                urlEl.href = citationUrl;
                urlEl.target = '_blank';
                urlEl.rel = 'noopener';
                urlEl.textContent = 'Open bron';

                actionsEl.appendChild(urlEl);
                info.appendChild(actionsEl);
            }

            item.appendChild(badge);
            item.appendChild(info);

            // Make entire item clickable if URL exists
            if (citationUrl) {
                item.style.cursor = 'pointer';
                item.addEventListener('click', function (e) {
                    if (e.target.tagName !== 'A') {
                        window.open(citationUrl, '_blank', 'noopener');
                    }
                });
            }

            list.appendChild(item);
        });

        section.appendChild(list);
        return section;
    }

    function getSourceColor(sourceId) {
        // Try exact match first
        if (SOURCE_COLORS[sourceId]) return SOURCE_COLORS[sourceId];
        // Try partial match
        for (var key in SOURCE_COLORS) {
            if (sourceId.indexOf(key) !== -1 || key.indexOf(sourceId) !== -1) {
                return SOURCE_COLORS[key];
            }
        }
        return '#607D8B'; // default gray
    }

    function getSourceLabel(sourceId) {
        if (SOURCE_LABELS[sourceId]) return SOURCE_LABELS[sourceId];
        for (var key in SOURCE_LABELS) {
            if (sourceId.indexOf(key) !== -1 || key.indexOf(sourceId) !== -1) {
                return SOURCE_LABELS[key];
            }
        }
        return sourceId;
    }

    function getSourcePolicyNote(sourceId) {
        if (sourceId === 'richtlijnendatabase') {
            return 'Deze richtlijn is opgesteld door de Federatie Medisch Specialisten en niet door IKNL.';
        }
        return '';
    }

    function getPrimaryCitationUrl(cite) {
        return cite.canonical_url || cite.url || '';
    }

    function formatDate(value) {
        if (!value) return '';
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleDateString('nl-NL', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    }

    // ===== Feedback =====
    function createFeedbackRow(msgId) {
        var row = document.createElement('div');
        row.className = 'feedback-row';

        var thumbsUp = createFeedbackButton('\u{1F44D}', 'Nuttig', 'positive', msgId);
        var thumbsDown = createFeedbackButton('\u{1F44E}', 'Niet nuttig', 'negative', msgId);
        var missing = createFeedbackButton('\u2753', 'Informatie ontbreekt', 'missing', msgId);

        row.appendChild(thumbsUp);
        row.appendChild(thumbsDown);
        row.appendChild(missing);

        return row;
    }

    function createFeedbackButton(icon, label, type, msgId) {
        var btn = document.createElement('button');
        btn.className = 'feedback-btn';
        btn.setAttribute('data-type', type);
        btn.setAttribute('data-msg', msgId);
        btn.innerHTML = icon + ' ' + label;

        btn.addEventListener('click', function () {
            // Toggle selection
            var siblings = btn.parentNode.querySelectorAll('.feedback-btn');
            siblings.forEach(function (s) { s.classList.remove('selected'); });
            btn.classList.add('selected');

            // Map button types to API feedback_type values
            var feedbackTypeMap = {
                'positive': 'helpful',
                'negative': 'incorrect',
                'missing': 'missing_info',
            };
            var feedbackType = feedbackTypeMap[type] || 'helpful';
            var isHelpful = type === 'positive';

            // Find the original query for this message (search backwards)
            var msgEl = document.getElementById(msgId);
            var queryText = 'unknown';
            if (msgEl) {
                var prevEl = msgEl.previousElementSibling;
                while (prevEl) {
                    if (prevEl.classList.contains('message-user')) {
                        var bubble = prevEl.querySelector('.bubble');
                        if (bubble) queryText = bubble.textContent;
                        break;
                    }
                    prevEl = prevEl.previousElementSibling;
                }
            }

            // Send feedback to backend
            fetch(API_BASE + '/feedback/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query_text: queryText,
                    feedback_type: feedbackType,
                    is_helpful: isHelpful,
                    message_index: parseInt(msgId.replace('msg-', ''), 10),
                }),
            }).catch(function (err) {
                console.warn('Feedback submission failed:', err);
            });
        });

        return btn;
    }

    // ===== Chat Management =====
    function resetChat() {
        messagesEl.innerHTML = '';
        welcomeScreen.classList.remove('hidden');
        messageCount = 0;
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;
        userInput.focus();
        closeSidebar();
    }

    // ===== Sidebar =====
    function toggleSidebar() {
        sidebar.classList.toggle('open');
        sidebarOverlay.classList.toggle('visible');
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('visible');
    }

    // ===== Scroll =====
    function scrollToBottom() {
        requestAnimationFrame(function () {
            chatArea.scrollTop = chatArea.scrollHeight;
        });
    }

    // ===== Utilities =====
    function escapeHtml(text) {
        var map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, function (c) { return map[c]; });
    }

    function escapeAttr(text) {
        return String(text)
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // ===== Start =====
    init();
})();
