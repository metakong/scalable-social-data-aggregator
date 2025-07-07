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
        const title = idea.ai_title || 'Analysis In Progress...';
        const description = idea.ai_summary || 'AI-generated summary will appear here.';

        card.innerHTML = `
            <h3>${title}</h3>
            <p><strong>AI-Generated Summary:</strong></p>
            <div class="description-box">${description.replace(/\n/g, '<br>')}</div>
            <p class="source-info"><strong>Source:</strong> <a href="${idea.source_url}" target="_blank" rel="noopener noreferrer">${idea.source_name}</a></p>
            <div class="idea-status">Status: <span>${idea.status}</span></div>`;
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

    const socket = io({ transports: ['websocket'] });
    socket.on('connect', () => addLogMessage('Real-time connection established.'));
    socket.on('disconnect', () => addLogMessage('Real-time connection lost.'));
    socket.on('log_message', (msg) => addLogMessage(msg.data));
    socket.on('new_idea', (data) => {
        const loadingMessage = document.getElementById('loading-message') || document.getElementById('no-ideas');
        if (loadingMessage) loadingMessage.remove();

        const existingCard = document.getElementById(`idea-${data.idea.id}`);
        if (existingCard) {
            existingCard.replaceWith(createIdeaCard(data.idea));
        } else {
            ideaQueue.prepend(createIdeaCard(data.idea));
        }
    });
    socket.on('progress_update', (data) => {
        const current = data.current || 0;
        const total = data.total || 1; // Avoid division by zero
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

    checkSystemStatus();
    setInterval(checkSystemStatus, 30000);
    fetchAndDisplayIdeas();
});