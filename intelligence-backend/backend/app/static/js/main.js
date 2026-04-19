document.addEventListener('DOMContentLoaded', () => {
    const statusApiUrl = '/api/v1/status';
    const ideasApiUrl = '/api/v1/ideas';

    const apiStatusText = document.getElementById('api-status').querySelector('.status-text');
    const apiStatusLight = document.getElementById('api-status').querySelector('.status-light');
    const dbStatusText = document.getElementById('db-status').querySelector('.status-text');
    const dbStatusLight = document.getElementById('db-status').querySelector('.status-light');
    const redisStatusText = document.getElementById('redis-status').querySelector('.status-text');
    const redisStatusLight = document.getElementById('redis-status').querySelector('.status-light');

    const ideaQueue = document.getElementById('idea-queue');
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

        const h3 = document.createElement('h3');
        h3.textContent = idea.ai_title || 'Analysis In Progress...';

        // Summary Section
        const pSummaryLabel = document.createElement('p');
        pSummaryLabel.innerHTML = '<strong>AI-Generated Summary:</strong>';
        const descBox = document.createElement('div');
        descBox.className = 'description-box';
        descBox.textContent = idea.ai_summary || 'AI-generated summary will appear here.';

        // Competition Analysis Section
        const pCompLabel = document.createElement('p');
        pCompLabel.innerHTML = '<strong>Competition Analysis:</strong>';
        const compBox = document.createElement('div');
        compBox.className = 'competition-box';
        compBox.textContent = idea.competition_analysis || 'Competition analysis pending...';

        // SWOT Analysis Section
        const pSwotLabel = document.createElement('p');
        pSwotLabel.innerHTML = '<strong>SWOT Analysis:</strong>';
        const swotGrid = document.createElement('div');
        swotGrid.className = 'swot-grid';

        if (idea.swot_analysis && Object.keys(idea.swot_analysis).length > 0) {
            const categories = ['strengths', 'weaknesses', 'opportunities', 'threats'];
            categories.forEach(cat => {
                const section = document.createElement('div');
                section.className = 'swot-section';
                
                const h4 = document.createElement('h4');
                h4.textContent = cat;
                
                const ul = document.createElement('ul');
                const items = idea.swot_analysis[cat] || [];
                
                if (items.length > 0) {
                    items.forEach(item => {
                        const li = document.createElement('li');
                        li.textContent = item;
                        ul.appendChild(li);
                    });
                } else {
                    const li = document.createElement('li');
                    li.textContent = 'None identified.';
                    ul.appendChild(li);
                }
                
                section.appendChild(h4);
                section.appendChild(ul);
                swotGrid.appendChild(section);
            });
        } else {
            swotGrid.className = 'pending-text';
            swotGrid.textContent = 'SWOT analysis pending...';
        }

        // Source Section
        const pSource = document.createElement('p');
        pSource.className = 'source-info';
        pSource.innerHTML = '<strong>Source: </strong>';
        const aSource = document.createElement('a');
        if (idea.source_url && idea.source_url.startsWith('devvit://')) {
            aSource.href = idea.source_url;
        }
        aSource.target = '_blank';
        aSource.rel = 'noopener noreferrer';
        aSource.textContent = idea.source_name;
        pSource.appendChild(aSource);

        // Status Section
        const divStatus = document.createElement('div');
        divStatus.className = 'idea-status';
        divStatus.innerHTML = `Status: <span>${idea.status}</span>`;

        // Append all elements to the card
        card.appendChild(h3);
        card.appendChild(pSummaryLabel);
        card.appendChild(descBox);
        card.appendChild(pCompLabel);
        card.appendChild(compBox);
        card.appendChild(pSwotLabel);
        card.appendChild(swotGrid);
        card.appendChild(pSource);
        card.appendChild(divStatus);

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



    const socket = io({ transports: ['websocket'] });
    socket.on('connect', () => addLogMessage('Real-time connection established.'));
    socket.on('disconnect', () => addLogMessage('Real-time connection lost.'));
    socket.on('log_message', (msg) => addLogMessage(msg.data));
    socket.on('idea_update', (data) => {
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
            }, 2000);
        }
    });


    checkSystemStatus();
    setInterval(checkSystemStatus, 30000);
    fetchAndDisplayIdeas();
});