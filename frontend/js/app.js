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

        // Lastmeter placeholder
        lastmeterBtn.addEventListener('click', function () {
            alert('De Lastmeter functionaliteit wordt binnenkort toegevoegd.');
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
            addRefusalMessage(data.refusal_reason);
            return;
        }

        var answer = data.answer_markdown || 'Geen antwoord ontvangen.';
        var citations = data.citations || [];
        addAIMessage(answer, citations);
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

    function addAIMessage(markdown, citations) {
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

        // Bubble with content
        var bubble = document.createElement('div');
        bubble.className = 'bubble';

        var htmlContent = renderMarkdown(markdown);
        htmlContent = replaceSrcReferences(htmlContent, citations);
        bubble.innerHTML = htmlContent;

        // Citations section
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

    function addRefusalMessage(reason) {
        messageCount++;
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

        var box = document.createElement('div');
        box.className = 'refusal-box';
        box.innerHTML =
            '<span class="refusal-icon">&#9888;</span> ' + escapeHtml(reason);

        div.appendChild(header);
        div.appendChild(box);
        messagesEl.appendChild(div);
        scrollToBottom();
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
        title.textContent = 'Bronnen';
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

            if (cite.url) {
                var urlEl = document.createElement('a');
                urlEl.className = 'url';
                urlEl.href = cite.url;
                urlEl.target = '_blank';
                urlEl.rel = 'noopener';
                urlEl.textContent = cite.url;
                info.appendChild(urlEl);
            }

            item.appendChild(badge);
            item.appendChild(info);

            // Make entire item clickable if URL exists
            if (cite.url) {
                item.style.cursor = 'pointer';
                item.addEventListener('click', function (e) {
                    if (e.target.tagName !== 'A') {
                        window.open(cite.url, '_blank', 'noopener');
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

            // In a real app, send feedback to API
            console.log('Feedback:', { messageId: msgId, type: type });
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
        return text.replace(/[&<>"']/g, function (c) { return map[c]; });
    }

    function escapeAttr(text) {
        return text.replace(/"/g, '&quot;').replace(/'/g, '&#039;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ===== Start =====
    init();
})();
