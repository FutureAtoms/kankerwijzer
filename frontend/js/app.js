/**
 * OncologieWijzer Chat Application
 * Frontend for the IKNL Medical-Grade Cancer Information System
 */

(function () {
    'use strict';

    // ===== Configuration =====
    const API_BASE = window.location.origin;
    const API_ENDPOINT = API_BASE + '/agent/answer';

    // ===== i18n Translations =====
    var currentLang = 'en';

    var TRANSLATIONS = {
        nl: {
            subtitle: 'Betrouwbare kankerinformatie van IKNL',
            header_trust: 'Alleen goedgekeurde bronnen',
            welcome_title: 'Welkom bij OncologieWijzer',
            welcome_desc: 'Stel uw vraag over kanker en ontvang informatie die wordt onderbouwd met goedgekeurde bronnen, duidelijke verwijzingen en veilige doorverwijzing bij spoed of persoonlijke zorgvragen.',
            trust_sources_title: 'Bronnen met herkomst',
            trust_sources_desc: 'Antwoorden verwijzen naar kanker.nl, NKR Cijfers, Kanker Atlas, richtlijnen en IKNL-publicaties.',
            trust_advice_title: 'Geen persoonlijk behandeladvies',
            trust_advice_desc: 'Bij diagnose-, spoed- of behandelbeslissingen verwijst OncologieWijzer direct door naar passende hulp.',
            trust_lastmeter_title: 'Ondersteuning bij klachten',
            trust_lastmeter_desc: 'Gebruik de Lastmeter om last en klachten te verkennen en relevante informatie mee te nemen naar uw zorgverlener.',
            audience_label: 'Doelgroep:',
            audience_patient: 'Patient',
            audience_professional: 'Zorgprofessional',
            disclaimer: 'Deze informatie is informatief en vervangt geen medisch advies. Raadpleeg altijd uw arts.',
            ex_breast: 'Wat is borstkanker?',
            ex_colon: 'Behandeling darmkanker',
            ex_fatigue: 'Vermoeidheid bij chemo',
            ex_survival: 'Overlevingscijfers longkanker',
            onboarding_welcome: '<strong>Welkom bij OncologieWijzer!</strong>',
            onboarding_intro: 'Bedankt dat u contact opneemt. Ik ben een AI-assistent van IKNL en help u betrouwbare informatie over kanker te vinden uit vertrouwde bronnen.',
            onboarding_important: 'Belangrijk om te weten:',
            onboarding_not_doctor: 'Ik ben <strong>geen arts</strong> \u2014 ik geef informatief advies, geen diagnose of behandelplan',
            onboarding_every_patient: 'Elke pati\u00EBnt is anders \u2014 bespreek alles met uw <strong>huisarts of specialist</strong>',
            onboarding_not_urgent: 'Deze chatbot is <strong>niet voor spoed</strong> \u2014 bel bij nood ',
            onboarding_help: 'Waar kan ik u mee helpen? U kunt mij vragen stellen over:',
            topic_cancer_type: 'Informatie over een kankersoort',
            topic_treatment: 'Behandelingen en bijwerkingen',
            topic_stats: 'Cijfers en statistieken',
            topic_lastmeter: 'Omgaan met klachten (Lastmeter)',
            topic_guidelines: 'Richtlijnen voor zorgprofessionals',
            sources_title: 'Bronnen',
            relevance_label: 'Relevantie',
            confidence_label_prefix: 'Betrouwbaarheid',
            contacts_title: 'Direct contact opnemen:',
            feedback_helpful: 'Nuttig',
            feedback_not_helpful: 'Niet nuttig',
            feedback_missing: 'Informatie ontbreekt',
        },
        en: {
            subtitle: 'Reliable cancer information from IKNL',
            header_trust: 'Approved sources only',
            welcome_title: 'Welcome to OncologieWijzer',
            welcome_desc: 'Ask your question about cancer and receive information backed by approved sources, clear references, and safe referrals for urgent or personal care questions.',
            trust_sources_title: 'Sources with provenance',
            trust_sources_desc: 'Answers reference kanker.nl, NKR Cijfers, Cancer Atlas, guidelines, and IKNL publications.',
            trust_advice_title: 'No personal treatment advice',
            trust_advice_desc: 'For diagnosis, emergency, or treatment decisions, OncologieWijzer refers you directly to appropriate care.',
            trust_lastmeter_title: 'Support for complaints',
            trust_lastmeter_desc: 'Use the Lastmeter to explore distress and complaints, and take relevant information to your healthcare provider.',
            audience_label: 'Audience:',
            audience_patient: 'Patient',
            audience_professional: 'Healthcare professional',
            disclaimer: 'This information is for informational purposes and does not replace medical advice. Always consult your doctor.',
            ex_breast: 'What is breast cancer?',
            ex_colon: 'Colorectal cancer treatment',
            ex_fatigue: 'Fatigue during chemo',
            ex_survival: 'Lung cancer survival rates',
            onboarding_welcome: '<strong>Welcome to OncologieWijzer!</strong>',
            onboarding_intro: 'Thank you for reaching out. I am an AI assistant from IKNL helping you find reliable cancer information from trusted sources.',
            onboarding_important: 'Important to know:',
            onboarding_not_doctor: 'I am <strong>not a doctor</strong> \u2014 I provide informational guidance, not diagnosis or treatment plans',
            onboarding_every_patient: 'Every patient is different \u2014 always discuss everything with your <strong>GP or specialist</strong>',
            onboarding_not_urgent: 'This chatbot is <strong>not for emergencies</strong> \u2014 call ',
            onboarding_help: 'How can I help you? You can ask me about:',
            topic_cancer_type: 'Information about a cancer type',
            topic_treatment: 'Treatments and side effects',
            topic_stats: 'Statistics and figures',
            topic_lastmeter: 'Coping with complaints (Lastmeter)',
            topic_guidelines: 'Guidelines for professionals',
            sources_title: 'Sources',
            relevance_label: 'Relevance',
            confidence_label_prefix: 'Confidence',
            contacts_title: 'Contact directly:',
            feedback_helpful: 'Helpful',
            feedback_not_helpful: 'Not helpful',
            feedback_missing: 'Missing info',
        },
    };

    function t(key) {
        return TRANSLATIONS[currentLang][key] || TRANSLATIONS.nl[key] || key;
    }

    function switchLanguage(lang) {
        currentLang = lang;

        // Update toggle buttons
        document.getElementById('lang-nl').classList.toggle('active', lang === 'nl');
        document.getElementById('lang-en').classList.toggle('active', lang === 'en');

        // Update all data-i18n elements
        document.querySelectorAll('[data-i18n]').forEach(function (el) {
            var key = el.getAttribute('data-i18n');
            var translated = t(key);
            if (el.tagName === 'OPTION') {
                el.textContent = translated;
            } else {
                el.innerHTML = translated;
            }
        });

        // Update placeholder
        var input = document.getElementById('user-input');
        input.placeholder = input.getAttribute('data-placeholder-' + lang) || input.placeholder;

        // Update example question buttons
        document.querySelectorAll('.example-q').forEach(function (btn) {
            var q = btn.getAttribute('data-question-' + lang);
            if (q) btn.setAttribute('data-question', q);
        });
    }

    // ===== PII Scrubber =====
    function scrubPII(text) {
        // Dutch BSN numbers (9 digits, standalone)
        text = text.replace(/\b\d{9}\b/g, '[REDACTED_PII]');
        // Dutch phone numbers: 06-12345678, +31612345678, 010 123 4567, etc.
        text = text.replace(/(\+31|0031|0)[1-9][\s\-]?(\d[\s\-]?){8}/g, '[REDACTED_PII]');
        // Email addresses
        text = text.replace(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g, '[REDACTED_PII]');
        return text;
    }

    // ===== Toast Notification =====
    function showToast(message, type) {
        var toast = document.createElement('div');
        toast.className = 'toast-notification toast-' + (type || 'info');
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.classList.add('visible'); }, 10);
        setTimeout(function () {
            toast.classList.remove('visible');
            setTimeout(function () { toast.remove(); }, 400);
        }, 3000);
    }

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
    // Pre-chat Lastmeter state (distress score + quick concerns)
    var lastmeterPreChat = {
        distressScore: 2,
        concerns: [],
    };

    // ===== Initialize =====
    function init() {
        // Input events
        userInput.addEventListener('input', onInputChange);
        userInput.addEventListener('keydown', onInputKeydown);
        sendBtn.addEventListener('click', onSend);

        // New chat
        newChatBtn.addEventListener('click', resetChat);

        // Download report
        document.getElementById('btn-download').addEventListener('click', downloadReport);

        // Example questions
        exampleButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var question = btn.getAttribute('data-question');
                userInput.value = question;
                onInputChange();
                onSend();
            });
        });

        // Language toggle
        document.getElementById('lang-nl').addEventListener('click', function () { switchLanguage('nl'); });
        document.getElementById('lang-en').addEventListener('click', function () { switchLanguage('en'); });

        // Mobile sidebar
        menuToggle.addEventListener('click', toggleSidebar);
        sidebarOverlay.addEventListener('click', closeSidebar);

        // Lastmeter - open the panel (handled by lastmeter.js)
        lastmeterBtn.addEventListener('click', function () {
            if (window.openLastmeter) {
                window.openLastmeter();
            }
        });

        // Welcome topic buttons
        initWelcomeTopics();

        // Apply default language to all UI text
        switchLanguage(currentLang);

        // Focus input
        userInput.focus();

        // Pre-chat Lastmeter wiring
        initPreChatLastmeter();
    }

    // ===== Pre-Chat Lastmeter =====
    function initPreChatLastmeter() {
        var panel = document.getElementById('prechat-lastmeter');
        var dismissBtn = document.getElementById('prechat-lm-dismiss');
        var slider = document.getElementById('prechat-distress');
        var scoreDisplay = document.getElementById('prechat-score-display');
        var scoreLabel = document.getElementById('prechat-score-label');
        var concernCbs = document.querySelectorAll('.prechat-concern-cb');

        if (!panel || !slider) return;

        function getScoreLabel(val) {
            if (val <= 2) return 'Laag';
            if (val <= 4) return 'Matig';
            if (val <= 6) return 'Hoog';
            if (val <= 8) return 'Zeer hoog';
            return 'Extreem';
        }

        slider.addEventListener('input', function () {
            var val = parseInt(this.value, 10);
            lastmeterPreChat.distressScore = val;
            scoreDisplay.textContent = val;
            scoreLabel.textContent = getScoreLabel(val);
            scoreDisplay.className = 'prechat-score-display prechat-score-' + (val >= 7 ? 'high' : val >= 4 ? 'medium' : 'low');
        });

        concernCbs.forEach(function (cb) {
            cb.addEventListener('change', function () {
                lastmeterPreChat.concerns = [];
                concernCbs.forEach(function (c) {
                    if (c.checked) lastmeterPreChat.concerns.push(c.value);
                });
            });
        });

        dismissBtn.addEventListener('click', function () {
            panel.style.display = 'none';
        });
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

    // ===== Welcome Topic Buttons =====
    // Wire the topic buttons in the welcome screen (they're in HTML now)
    function initWelcomeTopics() {
        var topicBtns = document.querySelectorAll('.welcome-topic-btn');
        topicBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var topic = btn.getAttribute('data-topic');
                if (topic === 'lastmeter') {
                    if (window.openLastmeter) window.openLastmeter();
                } else {
                    var question = btn.getAttribute('data-question-' + currentLang) || btn.textContent.trim();
                    userInput.value = question;
                    onInputChange();
                    onSend();
                }
            });
        });
    }

    // ===== External Send (used by Lastmeter and other components) =====
    window.sendChatMessage = function (message) {
        userInput.value = message;
        onInputChange();
        onSend();
    };

    // ===== Onboarding Welcome Message =====
    var onboardingShown = false;

    function showOnboardingMessage() {
        if (onboardingShown) return;
        onboardingShown = true;

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
            '<span class="ai-name">OncologieWijzer</span>';

        var bubble = document.createElement('div');
        bubble.className = 'bubble onboarding-bubble';
        bubble.innerHTML =
            '<p><strong>' + t('onboarding_welcome') + '</strong></p>' +
            '<p>' + t('onboarding_intro') + '</p>' +
            '<div class="onboarding-disclaimer">' +
            '<span class="disclaimer-icon">\u26A0\uFE0F</span>' +
            '<div>' +
            '<strong>' + t('onboarding_important') + '</strong>' +
            '<ul>' +
            '<li>' + t('onboarding_not_doctor') + '</li>' +
            '<li>' + t('onboarding_every_patient') + '</li>' +
            '<li>' + t('onboarding_not_urgent') + '<a href="tel:112" class="onboarding-phone">112</a></li>' +
            '</ul>' +
            '</div>' +
            '</div>' +
            '<p>' + t('onboarding_help') + '</p>';

        div.appendChild(header);
        div.appendChild(bubble);
        messagesEl.appendChild(div);
        scrollToBottom();
    }

    // ===== Caregiver Share Button =====
    function maybeCreateCaregiverButton(markdown) {
        var caregiverKeywords = ['actiepunten', 'mantelzorg', 'actionable tasks', 'caregiver', 'taken voor'];
        var lower = markdown.toLowerCase();
        var shouldShow = caregiverKeywords.some(function (kw) { return lower.indexOf(kw) !== -1; });
        if (!shouldShow) return null;

        var wrapper = document.createElement('div');
        wrapper.className = 'caregiver-share-wrapper';
        var shareText = encodeURIComponent('Informatie van OncologieWijzer:\n\n' + markdown.substring(0, 500));
        var btn = document.createElement('a');
        btn.className = 'caregiver-share-btn';
        btn.href = 'https://wa.me/?text=' + shareText;
        btn.target = '_blank';
        btn.rel = 'noopener noreferrer';
        btn.innerHTML =
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="white"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.613.613l4.458-1.495A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.39 0-4.592-.836-6.318-2.232l-.44-.362-3.266 1.095 1.095-3.266-.362-.44A9.953 9.953 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z"/></svg>' +
            'Deel met mantelzorger';
        wrapper.appendChild(btn);
        return wrapper;
    }

    // ===== Send Message =====
    function onSend() {
        var query = userInput.value.trim();
        if (!query || isLoading) return;

        // Hide welcome screen and show onboarding
        welcomeScreen.classList.add('hidden');
        showOnboardingMessage();

        // Apply PII scrubber before sending
        var scrubbedQuery = scrubPII(query);

        // Add user message (show original to user, send scrubbed to API)
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
            body: JSON.stringify({
                query: scrubbedQuery,
                audience: audience,
                lastmeter: lastmeterPreChat,
            }),
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
        var clarification = data.clarification || null;
        var graphContext = data.graph_context || null;
        addAIMessage(answer, citations, confidence, confidenceLabel, clarification, graphContext);
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

    function addAIMessage(markdown, citations, confidence, confidenceLabel, clarification, graphContext) {
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
            '<span class="ai-name">OncologieWijzer</span>';

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

        // Render structured clarification options if present
        if (clarification && clarification.options && clarification.options.length > 0) {
            renderClarificationButtons(bubble, clarification);
        }

        // Citations section with per-source relevance
        if (citations.length > 0) {
            var citationsEl = renderCitations(citations);
            bubble.appendChild(citationsEl);
        }

        // Caregiver share button (if message contains actionable/caregiver content)
        var caregiverBtn = maybeCreateCaregiverButton(markdown);
        if (caregiverBtn) {
            bubble.appendChild(caregiverBtn);
        }

        // Knowledge Graph context
        if (graphContext && graphContext.entities && graphContext.entities.length > 0) {
            var graphEl = renderGraphContext(graphContext);
            bubble.appendChild(graphEl);
        }

        // Feedback
        var feedback = createFeedbackRow(msgId);

        div.appendChild(header);
        div.appendChild(bubble);
        div.appendChild(feedback);

        messagesEl.appendChild(div);
        scrollToBottom();
        showDownloadButton();
    }

    /**
     * Render structured clarification options as clickable buttons.
     * Each button sends the option text as a new query to the orchestrator.
     */
    function renderClarificationButtons(bubble, clarification) {
        // Remove any heuristic-detected options to avoid duplicates
        var existing = bubble.querySelectorAll('.clarification-options');
        existing.forEach(function (el) { el.remove(); });

        var container = document.createElement('div');
        container.className = 'clarification-options';

        // Build context prefix from the clarification category
        var contextPrefix = '';
        switch (clarification.category) {
            case 'cancer_type':
                contextPrefix = currentLang === 'nl' ? 'Informatie over ' : 'Information about ';
                break;
            case 'treatment':
                contextPrefix = currentLang === 'nl' ? 'Behandeling bij ' : 'Treatment for ';
                break;
            case 'side_effects':
                contextPrefix = currentLang === 'nl' ? 'Bijwerkingen van ' : 'Side effects of ';
                break;
            case 'source_mismatch':
                contextPrefix = currentLang === 'nl' ? 'Informatie over ' : 'Information about ';
                break;
            default:
                contextPrefix = '';
        }

        clarification.options.forEach(function (option) {
            var btn = document.createElement('button');
            btn.className = 'clarification-btn';
            btn.textContent = option;
            btn.addEventListener('click', function () {
                // Send option with context so the query is specific enough
                userInput.value = contextPrefix + option;
                onInputChange();
                onSend();
            });
            container.appendChild(btn);
        });

        bubble.appendChild(container);
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
    function stripLeadingEmojisAndBullets(text) {
        // Remove leading emojis, bullets, dashes — safe for all browsers (no /u flag)
        var result = text.replace(/^\s*[-*\u2022\u25CF\u25B8\u25BA]+\s*/, '').replace(/\*\*/g, '').trim();
        // Strip leading non-ASCII symbols (emojis) by skipping chars with code > 127 at the start
        while (result.length > 0 && result.charCodeAt(0) > 127) {
            // Skip surrogate pairs (emojis are 2 chars in JS)
            if (result.charCodeAt(0) >= 0xD800 && result.charCodeAt(0) <= 0xDBFF) {
                result = result.substring(2);
            } else {
                result = result.substring(1);
            }
        }
        return result.trim();
    }

    function isEmojiOrBulletLine(text) {
        if (text.length < 2 || text.length > 80) return false;
        var firstChar = text.charCodeAt(0);
        // Dash, bullet chars
        if (text.charAt(0) === '-' || firstChar === 0x2022 || firstChar === 0x25CF || firstChar === 0x25B8 || firstChar === 0x25BA) return true;
        // High Unicode = likely emoji (surrogate pair or above ASCII)
        if (firstChar > 127) return true;
        return false;
    }

    function makeOptionBtn(container, rawText) {
        var text = stripLeadingEmojisAndBullets(rawText);
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

        // Strategy 2: Emoji/bullet lines in paragraphs
        var fullText = bubble.textContent || '';
        if (fullText.indexOf('?') === -1) return;

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

            var lines = el.innerHTML.split(/<br\s*\/?>/);
            var found = [];
            lines.forEach(function (line) {
                var clean = line.replace(/<[^>]+>/g, '').trim();
                if (isEmojiOrBulletLine(clean)) {
                    var label = stripLeadingEmojisAndBullets(clean);
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
            '<span class="ai-name">OncologieWijzer</span>';

        // Refusal box with severity-based styling
        var box = document.createElement('div');
        box.className = 'refusal-box refusal-' + severity;

        var severityIcon = severity === 'critical' ? '\uD83D\uDEA8' :
                          severity === 'urgent' ? '\uD83D\uDC9C' : '\u26A0\uFE0F';
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
        showDownloadButton();
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
            '<span class="ai-name">OncologieWijzer</span>' +
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

    // ===== Knowledge Graph Section =====
    function renderGraphContext(graphContext) {
        var section = document.createElement('div');
        section.className = 'graph-section';

        var titleRow = document.createElement('div');
        titleRow.className = 'graph-title';
        titleRow.innerHTML = '<span class="graph-icon">\uD83D\uDD17</span> ' +
            (currentLang === 'nl' ? 'Kennisgraaf' : 'Knowledge Graph') +
            ' <span class="graph-center">' + escapeHtml(graphContext.center || '') + '</span>';
        section.appendChild(titleRow);

        var graphVis = document.createElement('div');
        graphVis.className = 'graph-visual';

        // Center node
        var centerNode = document.createElement('div');
        centerNode.className = 'graph-node graph-node-center';
        centerNode.textContent = graphContext.center || '?';
        graphVis.appendChild(centerNode);

        // Group entities by type
        var byType = {};
        (graphContext.entities || []).forEach(function (ent) {
            var type = ent.type || ent.label || 'Other';
            if (!byType[type]) byType[type] = [];
            byType[type].push(ent);
        });

        // Relationship labels
        var relLabels = {};
        (graphContext.relationships || []).forEach(function (rel) {
            var target = (rel.target || rel.end || '').toLowerCase();
            relLabels[target] = rel.type || rel.label || '';
        });

        var typeColors = {
            'CancerType': '#e53935', 'Treatment': '#43A047', 'Symptom': '#FB8C00',
            'Stage': '#5E35B1', 'Diagnostic': '#1E88E5', 'RiskFactor': '#F4511E',
            'BodyPart': '#00897B', 'Guideline': '#8E24AA',
        };

        Object.keys(byType).forEach(function (type) {
            var group = document.createElement('div');
            group.className = 'graph-group';

            var groupLabel = document.createElement('div');
            groupLabel.className = 'graph-group-label';
            groupLabel.style.color = typeColors[type] || '#666';
            groupLabel.textContent = type;
            group.appendChild(groupLabel);

            var nodes = document.createElement('div');
            nodes.className = 'graph-nodes';

            byType[type].forEach(function (ent) {
                var name = ent.name || ent.id || '';
                var node = document.createElement('button');
                node.className = 'graph-node';
                node.style.borderColor = typeColors[type] || '#ccc';
                node.style.color = typeColors[type] || '#333';
                node.textContent = name;
                node.title = (relLabels[name.toLowerCase()] || type) + ': ' + name;
                node.addEventListener('click', function () {
                    var prefix = currentLang === 'nl' ? 'Informatie over ' : 'Information about ';
                    userInput.value = prefix + name;
                    onInputChange();
                    onSend();
                });
                nodes.appendChild(node);
            });

            group.appendChild(nodes);
            graphVis.appendChild(group);
        });

        section.appendChild(graphVis);
        return section;
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

        var thumbsUp = createFeedbackButton('\uD83D\uDC4D', t('feedback_helpful'), 'positive', msgId);
        var thumbsDown = createFeedbackButton('\uD83D\uDC4E', t('feedback_not_helpful'), 'negative', msgId);
        var missing = createFeedbackButton('\u2753', t('feedback_missing'), 'missing', msgId);

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
        document.getElementById('btn-download').style.display = 'none';
        userInput.focus();
        closeSidebar();
    }

    // ===== Download Chat Report =====
    function showDownloadButton() {
        document.getElementById('btn-download').style.display = '';
    }

    function downloadReport() {
        var messages = messagesEl.querySelectorAll('.message-user, .message-ai');
        if (messages.length === 0) return;

        var now = new Date();
        var dateStr = now.toLocaleDateString('en-GB', { year: 'numeric', month: 'long', day: 'numeric' });
        var timeStr = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

        var entries = [];

        messages.forEach(function (msg) {
            if (msg.classList.contains('message-user')) {
                var bubble = msg.querySelector('.bubble');
                if (bubble) {
                    entries.push({ role: 'patient', text: bubble.textContent.trim() });
                }
            } else if (msg.classList.contains('message-ai')) {
                var aiBubble = msg.querySelector('.bubble');
                var entry = { role: 'assistant', text: '', citations: [], confidence: '' };

                // Get confidence
                var confBadge = msg.querySelector('.confidence-badge');
                if (confBadge) entry.confidence = confBadge.textContent.trim();

                // Get answer text (exclude citations/graph sections)
                if (aiBubble) {
                    var clone = aiBubble.cloneNode(true);
                    // Remove citations, graph, clarification buttons from clone
                    clone.querySelectorAll('.citations-section, .graph-section, .clarification-options, .feedback-row').forEach(function (el) { el.remove(); });
                    entry.text = clone.textContent.trim();
                }

                // Get citations
                var citItems = msg.querySelectorAll('.citation-item');
                citItems.forEach(function (item) {
                    var title = item.querySelector('.title');
                    var url = item.querySelector('.url');
                    var relevance = item.querySelector('.relevance-label');
                    entry.citations.push({
                        title: title ? title.textContent.trim() : '',
                        url: url ? url.textContent.trim() : '',
                        relevance: relevance ? relevance.textContent.trim() : '',
                    });
                });

                // Check refusal
                var refusalBox = msg.querySelector('.refusal-box');
                if (refusalBox) {
                    entry.text = refusalBox.textContent.trim();
                    entry.isRefusal = true;
                }

                // Check contacts
                var contactCards = msg.querySelectorAll('.contact-card');
                if (contactCards.length > 0) {
                    entry.contacts = [];
                    contactCards.forEach(function (card) {
                        var name = card.querySelector('.contact-name');
                        var desc = card.querySelector('.contact-desc');
                        var phone = card.querySelector('.contact-btn-phone');
                        entry.contacts.push({
                            name: name ? name.textContent.trim() : '',
                            description: desc ? desc.textContent.trim() : '',
                            phone: phone ? phone.textContent.trim() : '',
                        });
                    });
                }

                entries.push(entry);
            }
        });

        // Build HTML report
        var html = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">' +
            '<title>OncologieWijzer Report - ' + dateStr + '</title>' +
            '<style>' +
            'body{font-family:Georgia,serif;max-width:700px;margin:40px auto;padding:20px;color:#333;line-height:1.6}' +
            'h1{color:#00A67E;border-bottom:3px solid #00A67E;padding-bottom:10px;font-size:1.5rem}' +
            '.meta{color:#666;font-size:0.9rem;margin-bottom:30px}' +
            '.disclaimer-box{background:#fff8e1;border-left:4px solid #ffa000;padding:12px 16px;margin:20px 0;font-size:0.85rem;border-radius:4px}' +
            '.exchange{margin:24px 0;page-break-inside:avoid}' +
            '.patient-q{background:#f0faf6;border-left:4px solid #00A67E;padding:10px 16px;border-radius:4px;font-weight:600;margin-bottom:8px}' +
            '.assistant-a{padding:0 16px}' +
            '.confidence{display:inline-block;background:#e8f5e9;color:#2e7d32;padding:2px 10px;border-radius:12px;font-size:0.75rem;margin-bottom:8px}' +
            '.refusal{background:#fff3e0;border-left:4px solid #ff9800;padding:10px 16px;border-radius:4px;color:#e65100}' +
            '.sources{margin-top:10px;padding-top:8px;border-top:1px solid #eee}' +
            '.sources h4{font-size:0.85rem;color:#666;margin:0 0 6px}' +
            '.source-item{font-size:0.8rem;color:#555;margin:4px 0}' +
            '.source-item a{color:#1976D2}' +
            '.contacts{margin-top:12px;padding:10px;background:#f5f5f5;border-radius:6px}' +
            '.contact{margin:6px 0;font-size:0.85rem}' +
            '.contact-phone{font-weight:700;color:#4CAF50}' +
            '.footer{margin-top:40px;padding-top:16px;border-top:2px solid #eee;font-size:0.8rem;color:#888}' +
            '@media print{body{margin:20px}h1{font-size:1.3rem}.exchange{page-break-inside:avoid}}' +
            '</style></head><body>' +
            '<h1>OncologieWijzer &mdash; Chat Report</h1>' +
            '<div class="meta">' +
            '<strong>Date:</strong> ' + dateStr + ' at ' + timeStr + '<br>' +
            '<strong>Purpose:</strong> For discussion with your healthcare provider (GP / specialist)<br>' +
            '<strong>Source:</strong> OncologieWijzer by IKNL &mdash; <em>iknl.nl</em>' +
            '</div>' +
            '<div class="disclaimer-box">' +
            '&#x26A0;&#xFE0F; <strong>Important:</strong> This report contains AI-generated information based on trusted IKNL sources. ' +
            'It is for informational purposes only and does not replace professional medical advice. ' +
            'Always discuss the content with your doctor.' +
            '</div>';

        entries.forEach(function (entry, idx) {
            if (entry.role === 'patient') {
                html += '<div class="exchange"><div class="patient-q">Patient: ' + escapeHtml(entry.text) + '</div>';
            } else {
                html += '<div class="assistant-a">';
                if (entry.confidence) {
                    html += '<span class="confidence">' + escapeHtml(entry.confidence) + '</span>';
                }
                if (entry.isRefusal) {
                    html += '<div class="refusal">' + escapeHtml(entry.text) + '</div>';
                } else {
                    html += '<div>' + escapeHtml(entry.text).replace(/\n/g, '<br>') + '</div>';
                }
                if (entry.citations && entry.citations.length > 0) {
                    html += '<div class="sources"><h4>Sources:</h4>';
                    entry.citations.forEach(function (c, i) {
                        html += '<div class="source-item">' + (i + 1) + '. ' + escapeHtml(c.title);
                        if (c.url) html += ' &mdash; <a href="' + escapeHtml(c.url) + '">' + escapeHtml(c.url) + '</a>';
                        if (c.relevance) html += ' (' + escapeHtml(c.relevance) + ')';
                        html += '</div>';
                    });
                    html += '</div>';
                }
                if (entry.contacts && entry.contacts.length > 0) {
                    html += '<div class="contacts"><strong>Emergency contacts:</strong>';
                    entry.contacts.forEach(function (c) {
                        html += '<div class="contact">' + escapeHtml(c.name);
                        if (c.phone) html += ' &mdash; <span class="contact-phone">' + escapeHtml(c.phone) + '</span>';
                        if (c.description) html += '<br><small>' + escapeHtml(c.description) + '</small>';
                        html += '</div>';
                    });
                    html += '</div>';
                }
                html += '</div></div>';
            }
        });

        html += '<div class="footer">' +
            'Generated by OncologieWijzer (IKNL) on ' + dateStr + ' at ' + timeStr + '.<br>' +
            'All information sourced from kanker.nl, NKR Cijfers, Cancer Atlas, Richtlijnendatabase, and IKNL publications.<br>' +
            'This report is not a medical document. Please discuss its contents with your healthcare provider.' +
            '</div></body></html>';

        // Trigger download
        var blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'oncologiewijzer-report-' + now.toISOString().slice(0, 10) + '.html';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
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
