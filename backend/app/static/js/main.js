document.addEventListener('DOMContentLoaded', () => {
    const statusApiUrl = '/api/v1/status';
    const ideasApiUrl = '/api/v1/ideas';
    const sourcingApiUrl = '/api/v1/sourcing/start';

    const apiStatusText = document.getElementById('api-status').querySelector('.status-text');
    const apiStatusLight = document.getElementById('api-status').querySelector('.status-light');
    const dbStatusText = document.getElementById('db-status').querySelector('.status-text');
    const dbStatusLight = document.getElementById('db-status').querySelector('.status-light');
    const redisStatusText = document.getElementById('redis-status').querySelector('.status-text');
    const redisStatusLight = document.getElementById('redis-status').querySelector('.status-light');

    const ideaQueue = document.getElementById('idea-queue');
    const startCycleBtn = document.getElementById('start-cycle-btn');
    const logViewer = document.getElementById('log-viewer');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');

    // Clear the placeholder template from the HTML
    const placeholder = document.getElementById('idea-template-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    function addLogMessage(message) {
        const logEntry = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        logEntry.textContent = `[${timestamp}] ${message}`;
        logViewer.appendChild(logEntry);
        logViewer.scrollTop = logViewer.scrollHeight;
    }

    function updateStatus(light, text, status) {
        light.className = 'status-light';
        if (status === 'ok' || status === 'online') {
            light.classList.add('green');
            text.textContent = 'Online';
        } else {
            light.classList.add('red');
            text.textContent = 'Error';
        }
    }

    async function checkSystemStatus() {
        try {
            const response = await fetch(statusApiUrl);
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            updateStatus(apiStatusLight, apiStatusText, data.api_status);
            updateStatus(dbStatusLight, dbStatusText, data.database_status);
            updateStatus(redisStatusLight, redisStatusText, data.redis_status);
        } catch (error) {
            addLogMessage(`Error fetching system status: ${error.message}`);
            updateStatus(apiStatusLight, apiStatusText, 'error');
            updateStatus(dbStatusLight, dbStatusText, 'error');
            updateStatus(redisStatusLight, redisStatusText, 'error');
        }
    }

    function createIdeaCard(idea) {
        const card = document.createElement('div');
        card.className = 'idea-card';
        card.id = `idea-${idea.id}`;
        card.dataset.status = idea.status;

        const createSwotList = (items) => {
            if (!items || !Array.isArray(items)) return '<li>No data.</li>';
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

    async function fetchAndDisplayIdeas() {
        try {
            const response = await fetch(ideasApiUrl);
            if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
            const ideas = await response.json();
            ideaQueue.innerHTML = '';
            if (ideas.length === 0) {
                ideaQueue.innerHTML = '<p id="loading-message">The review queue is empty. Run a discovery cycle to find new ideas.</p>';
            } else {
                ideas.forEach(idea => ideaQueue.appendChild(createIdeaCard(idea)));
            }
        } catch (error) {
            addLogMessage(`Error fetching ideas: ${error.message}`);
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
            const response = await fetch(sourcingApiUrl, { method: 'POST' });
            if (!response.ok) throw new Error(`Server responded with status: ${response.status}`);
            const data = await response.json();
            addLogMessage(`Cycle initiated successfully: ${data.message}`);
        } catch (error) {
            addLogMessage(`Error starting cycle: ${error.message}`);
            startCycleBtn.disabled = false;
            startCycleBtn.classList.remove('loading');
        }
    }

    // --- CEO Actions using Event Delegation ---
    ideaQueue.addEventListener('click', async (event) => {
        const target = event.target;
        const isApprove = target.classList.contains('approve-btn');
        const isReject = target.classList.contains('reject-btn');

        if (!isApprove && !isReject) return;

        const ideaId = target.dataset.id;
        const card = target.closest('.idea-card');
        const feedbackTextarea = card.querySelector('.feedback-textarea');
        const feedback = feedbackTextarea.value.trim();

        const endpoint = isApprove ? `/api/v1/ideas/${ideaId}/approve` : `/api/v1/ideas/${ideaId}/reject`;
        const action = isApprove ? 'Approving' : 'Rejecting';

        card.querySelectorAll('.btn').forEach(button => button.disabled = true);
        addLogMessage(`${action} idea ${ideaId}...`);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ceo_feedback: feedback }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Server responded with status: ${response.status}`);
            }
            const result = await response.json();
            addLogMessage(result.message);
            // The socket 'idea_update' event will handle re-rendering the card with the new status.
        } catch (error) {
            addLogMessage(`Error ${action.toLowerCase()} idea ${ideaId}: ${error.message}`);
            card.querySelectorAll('.btn').forEach(button => button.disabled = false);
        }
    });

    // --- Socket.IO Event Handling ---
    const socket = io({ transports: ['websocket'] });
    socket.on('connect', () => addLogMessage('Real-time connection established.'));
    socket.on('disconnect', () => addLogMessage('Real-time connection lost.'));
    socket.on('log_message', (msg) => addLogMessage(msg.data));

    socket.on('idea_update', (data) => {
        addLogMessage(`Received update for Idea ${data.idea.id}. Status: ${data.idea.status}`);
        const idea = data.idea;
        const existingCard = document.getElementById(`idea-${idea.id}`);
        const newCard = createIdeaCard(idea);

        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) loadingMessage.remove();

        if (existingCard) {
            existingCard.replaceWith(newCard);
        } else {
            ideaQueue.prepend(newCard);
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

    startCycleBtn.addEventListener('click', startDiscoveryCycle);

    // --- Initial Load ---
    checkSystemStatus();
    setInterval(checkSystemStatus, 30000);
    fetchAndDisplayIdeas();
});
