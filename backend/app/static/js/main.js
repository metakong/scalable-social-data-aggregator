document.addEventListener('DOMContentLoaded', () => {
    // --- Constants and DOM Elements ---
    const API_BASE_URL = '/api/v1';
    const ideaQueue = document.getElementById('idea-queue');
    const startCycleBtn = document.getElementById('start-cycle-btn');
    const logViewer = document.getElementById('log-viewer');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    // --- Utility Functions ---
    function addLogMessage(message, type = 'info') {
        const logEntry = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        logEntry.className = `log-${type}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        logViewer.appendChild(logEntry);
        logViewer.scrollTop = logViewer.scrollHeight;
    }

    function updateStatusLight(elementId, status) {
        const light = document.getElementById(elementId)?.querySelector('.status-light');
        const text = document.getElementById(elementId)?.querySelector('.status-text');
        if (!light || !text) return;

        light.className = 'status-light'; // Reset classes
        if (status === 'ok' || status === 'online') {
            light.classList.add('green');
            text.textContent = 'Online';
        } else {
            light.classList.add('red');
            text.textContent = 'Error';
        }
    }

    // --- Core UI Function ---
    function createIdeaCard(idea) {
        const card = document.createElement('div');
        card.className = 'idea-card';
        card.id = `idea-${idea.id}`;
        card.dataset.status = idea.status;

        const createSwotList = (items) => {
            if (!items || !Array.isArray(items) || items.length === 0) {
                return '<li>No data provided.</li>';
            }
            return items.map(item => `<li>${item}</li>`).join('');
        };

        const swot = idea.swot_analysis || {};

        card.innerHTML = `
            <h3>${idea.ai_title || 'Analysis In Progress...'}</h3>
            <div class="idea-status">Status: <span>${idea.status}</span></div>
            <p class="source-info"><strong>Source:</strong> <a href="${idea.source_url}" target="_blank" rel="noopener noreferrer">${idea.source_name}</a></p>

            <h4>AI-Generated Summary</h4>
            <div class="description-box">
                ${idea.ai_summary ? idea.ai_summary.replace(/\n/g, '<br>') : 'AI-generated summary will appear here.'}
            </div>

            <h4>Competition Analysis</h4>
            <div class="analysis-box">
                ${idea.competition_analysis || 'Competition analysis will appear here.'}
            </div>

            <h4>SWOT Analysis</h4>
            <div class="swot-grid">
                <div class="swot-item strengths">
                    <h5>Strengths</h5>
                    <ul class="swot-list">${createSwotList(swot.strengths)}</ul>
                </div>
                <div class="swot-item weaknesses">
                    <h5>Weaknesses</h5>
                    <ul class="swot-list">${createSwotList(swot.weaknesses)}</ul>
                </div>
                <div class="swot-item opportunities">
                    <h5>Opportunities</h5>
                    <ul class="swot-list">${createSwotList(swot.opportunities)}</ul>
                </div>
                <div class="swot-item threats">
                    <h5>Threats</h5>
                    <ul class="swot-list">${createSwotList(swot.threats)}</ul>
                </div>
            </div>

            <div class="ceo-action-panel">
                <h4>CEO Review & Action</h4>
                <textarea class="feedback-textarea" placeholder="Provide feedback for rejection or revision...">${idea.ceo_feedback || ''}</textarea>
                <div class="action-buttons">
                    <button class="btn reject-btn" data-id="${idea.id}">Reject</button>
                    <button class="btn approve-btn" data-id="${idea.id}">Approve for Dev</button>
                </div>
            </div>
        `;
        return card;
    }

    // --- API Call Functions ---
    async function checkSystemStatus() {
        try {
            const response = await fetch(`${API_BASE_URL}/status`);
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            updateStatusLight('api-status', data.api_status);
            updateStatusLight('db-status', data.database_status);
            updateStatusLight('redis-status', data.redis_status);
        } catch (error) {
            addLogMessage(`Error fetching system status: ${error.message}`, 'error');
            updateStatusLight('api-status', 'error');
            updateStatusLight('db-status', 'error');
            updateStatusLight('redis-status', 'error');
        }
    }

    async function fetchAndDisplayIdeas() {
        try {
            const response = await fetch(`${API_BASE_URL}/ideas`);
            if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
            const ideas = await response.json();

            ideaQueue.innerHTML = ''; // Clear existing ideas

            // Filter for only ideas awaiting CEO review
            const ideasForReview = ideas.filter(idea => idea.status === 'PENDING_CEO_APPROVAL');

            if (ideasForReview.length === 0) {
                ideaQueue.innerHTML = '<p id="loading-message">The review queue is empty. Run a discovery cycle to find new ideas.</p>';
            } else {
                ideasForReview.forEach(idea => ideaQueue.appendChild(createIdeaCard(idea)));
            }
        } catch (error) {
            addLogMessage(`Error fetching ideas: ${error.message}`, 'error');
            ideaQueue.innerHTML = '<p id="loading-message" style="color: var(--status-error);">Error loading ideas.</p>';
        }
    }

    async function startDiscoveryCycle() {
        startCycleBtn.disabled = true;
        startCycleBtn.classList.add('loading');
        logViewer.innerHTML = '';
        addLogMessage('Requesting new discovery cycle...');
        progressBar.style.width = '0%';
        progressText.textContent = 'Initializing...';
        try {
            const response = await fetch(`${API_BASE_URL}/sourcing/start`, { method: 'POST' });
            if (!response.ok) throw new Error(`Server responded with status: ${response.status}`);
            const data = await response.json();
            addLogMessage(`Cycle initiated successfully: ${data.message}`);
        } catch (error) {
            addLogMessage(`Error starting cycle: ${error.message}`, 'error');
            startCycleBtn.disabled = false;
            startCycleBtn.classList.remove('loading');
        }
    }

    async function handleCeoAction(action, ideaId, card) {
        const feedbackTextarea = card.querySelector('.feedback-textarea');
        const feedback = feedbackTextarea.value.trim();
        const endpoint = `${API_BASE_URL}/ideas/${ideaId}/${action}`;

        card.querySelectorAll('.btn').forEach(button => button.disabled = true);
        card.style.opacity = '0.5';
        addLogMessage(`Requesting to ${action} idea ${ideaId}...`);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ceo_feedback: feedback }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || `Server responded with status: ${response.status}`);
            }
            addLogMessage(result.message);
            // UI update will be handled by the 'idea_update' socket event
        } catch (error) {
            addLogMessage(`Error ${action}ing idea ${ideaId}: ${error.message}`, 'error');
            card.querySelectorAll('.btn').forEach(button => button.disabled = false);
            card.style.opacity = '1';
        }
    }

    // --- Event Listeners ---
    startCycleBtn.addEventListener('click', startDiscoveryCycle);

    ideaQueue.addEventListener('click', (event) => {
        const button = event.target.closest('.btn');
        if (!button) return;

        const ideaId = button.dataset.id;
        const card = document.getElementById(`idea-${ideaId}`);

        if (button.classList.contains('approve-btn')) {
            handleCeoAction('approve', ideaId, card);
        } else if (button.classList.contains('reject-btn')) {
            handleCeoAction('reject', ideaId, card);
        }
    });

    // --- Socket.IO Setup ---
    const socket = io({ transports: ['websocket'] });

    socket.on('connect', () => addLogMessage('Real-time connection established.'));
    socket.on('disconnect', () => addLogMessage('Real-time connection lost.', 'error'));
    socket.on('log_message', (msg) => addLogMessage(msg.data));

    socket.on('idea_update', (data) => {
        const idea = data.idea;
        addLogMessage(`Received update for Idea ${idea.id}. Status: ${idea.status}`);
        const existingCard = document.getElementById(`idea-${idea.id}`);

        // If the idea is no longer for CEO approval, remove it. Otherwise, update it.
        if (idea.status !== 'PENDING_CEO_APPROVAL' && existingCard) {
            existingCard.remove();
        } else if (existingCard) {
            existingCard.replaceWith(createIdeaCard(idea));
        } else if (idea.status === 'PENDING_CEO_APPROVAL') {
            // This handles the case where a new idea reaches the approval state
            const loadingMessage = document.getElementById('loading-message');
            if (loadingMessage) loadingMessage.remove();
            ideaQueue.prepend(createIdeaCard(idea));
        }
    });

    socket.on('progress_update', (data) => {
        const current = data.current || 0;
        const total = data.total || 1;
        const percentage = Math.min(100, Math.round((current / total) * 100));
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `Processing... ${current} of ${total} (${percentage}%)`;

        if (current >= total && total > 0) {
            setTimeout(() => {
                progressText.textContent = 'Cycle Complete';
                startCycleBtn.disabled = false;
                startCycleBtn.classList.remove('loading');
            }, 2000);
        }
    });

    // --- Initial Load ---
    function initialize() {
        const placeholder = document.getElementById('idea-template-placeholder');
        if (placeholder) placeholder.remove();

        checkSystemStatus();
        setInterval(checkSystemStatus, 30000);
        fetchAndDisplayIdeas();
    }

    initialize();
});