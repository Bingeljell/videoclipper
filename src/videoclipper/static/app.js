/**
 * Video Clipper - Web UI JavaScript
 */

// DOM Elements
const urlInput = document.getElementById('urlInput');
const getInfoBtn = document.getElementById('getInfoBtn');
const infoPanel = document.getElementById('infoPanel');
const infoTitle = document.getElementById('infoTitle');
const infoChannel = document.getElementById('infoChannel');
const infoDuration = document.getElementById('infoDuration');
const infoHeights = document.getElementById('infoHeights');

const qualitySelect = document.getElementById('qualitySelect');
const customHeight = document.getElementById('customHeight');
const formatSelect = document.getElementById('formatSelect');
const modeSelect = document.getElementById('modeSelect');

const addClipBtn = document.getElementById('addClipBtn');
const clipsContainer = document.getElementById('clipsContainer');

const outdirInput = document.getElementById('outdirInput');
const browseBtn = document.getElementById('browseBtn');
const prefixInput = document.getElementById('prefixInput');

const generateBtn = document.getElementById('generateBtn');
const downloadAudioBtn = document.getElementById('downloadAudioBtn');
const audioFormatSelect = document.getElementById('audioFormatSelect');
const progressContainer = document.getElementById('progressContainer');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');

const overlayVideoInput = document.getElementById('overlayVideoInput');
const overlayAudioInput = document.getElementById('overlayAudioInput');
const overlayFadeInput = document.getElementById('overlayFadeInput');
const overlayFadeValue = document.getElementById('overlayFadeValue');
const overlayBtn = document.getElementById('overlayBtn');

const resultsSection = document.getElementById('resultsSection');
const resultsList = document.getElementById('resultsList');

// WebSocket
let ws = null;
let currentJobId = null;

// Initialize
function init() {
    setupEventListeners();
    setupQualityToggle();
    setupClipsContainer();
}

function setupEventListeners() {
    getInfoBtn.addEventListener('click', handleGetInfo);
    addClipBtn.addEventListener('click', addClipRow);
    generateBtn.addEventListener('click', handleGenerate);
    downloadAudioBtn.addEventListener('click', handleDownloadAudio);
    browseBtn.addEventListener('click', handleBrowse);
    
    // Overlay events
    overlayFadeInput.addEventListener('input', (e) => {
        overlayFadeValue.textContent = e.target.value + 's';
    });
    overlayBtn.addEventListener('click', handleOverlay);
}

function setupQualityToggle() {
    qualitySelect.addEventListener('change', () => {
        if (qualitySelect.value === 'custom') {
            customHeight.classList.remove('hidden');
            customHeight.focus();
        } else {
            customHeight.classList.add('hidden');
        }
    });
}

function setupClipsContainer() {
    clipsContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-clip')) {
            const row = e.target.closest('.clip-row');
            const rows = clipsContainer.querySelectorAll('.clip-row');
            if (rows.length > 1) {
                row.remove();
            } else {
                // Clear inputs instead of removing last row
                row.querySelector('.start-time').value = '';
                row.querySelector('.end-time').value = '';
            }
        }
    });
}

function addClipRow() {
    const row = document.createElement('div');
    row.className = 'clip-row';
    row.innerHTML = `
        <div class="time-input">
            <label>Start</label>
            <input type="text" class="start-time" placeholder="mm:ss or seconds" />
        </div>
        <div class="time-input">
            <label>End</label>
            <input type="text" class="end-time" placeholder="mm:ss or seconds" />
        </div>
        <button class="btn icon remove-clip" title="Remove clip">×</button>
    `;
    clipsContainer.appendChild(row);
}

async function handleGetInfo() {
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a URL');
        return;
    }

    getInfoBtn.disabled = true;
    getInfoBtn.textContent = 'Loading...';

    try {
        const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
        const data = await response.json();

        if (data.success) {
            infoTitle.textContent = data.title || 'Unknown';
            infoChannel.textContent = data.channel || 'Unknown';
            infoDuration.textContent = data.duration_text || 'Unknown';
            infoHeights.textContent = data.h264_heights?.join(', ') || 'None';
            infoPanel.classList.remove('hidden');
        } else {
            showError(data.error || 'Failed to get info');
        }
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        getInfoBtn.disabled = false;
        getInfoBtn.textContent = 'Get Info';
    }
}

function getQualityHeight() {
    if (qualitySelect.value === 'custom') {
        const height = parseInt(customHeight.value, 10);
        return isNaN(height) || height < 1 ? 480 : height;
    }
    return parseInt(qualitySelect.value, 10);
}

function collectClips() {
    const rows = clipsContainer.querySelectorAll('.clip-row');
    const clips = [];
    
    rows.forEach(row => {
        const start = row.querySelector('.start-time').value.trim();
        const end = row.querySelector('.end-time').value.trim();
        if (start && end) {
            clips.push(`${start}-${end}`);
        }
    });
    
    return clips.join(',');
}

async function handleGenerate() {
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a URL');
        return;
    }

    const clips = collectClips();
    if (!clips) {
        showError('Please add at least one clip with start and end times');
        return;
    }

    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    progressContainer.classList.remove('hidden');
    setButtonsDisabled(true);
    generateBtn.textContent = 'Processing...';

    // Connect WebSocket
    connectWebSocket();

    // Wait for connection then start job
    setTimeout(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            const params = {
                url: url,
                clips: clips,
                outdir: outdirInput.value.trim() || './clips',
                quality_height: getQualityHeight(),
                reencode: modeSelect.value === 'precise',
                format: formatSelect.value
            };
            
            ws.send(JSON.stringify({
                action: 'start_clip',
                params: params
            }));
        } else {
            showError('WebSocket not connected');
            resetButtons();
        }
    }, 500);
}

async function handleDownloadAudio() {
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a URL');
        return;
    }

    const audioFormat = audioFormatSelect.value;
    if (!audioFormat) {
        showError('Please select an audio format');
        return;
    }

    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    progressContainer.classList.remove('hidden');
    setButtonsDisabled(true);
    downloadAudioBtn.textContent = 'Downloading...';
    updateProgress(10, 'Downloading audio...');

    try {
        const response = await fetch('/api/audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                outdir: outdirInput.value.trim() || './audio',
                format: audioFormat
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateProgress(100, 'Complete!');
            progressFill.classList.add('complete');
            showResults([data.path]);
        } else {
            progressFill.classList.add('error');
            showError(data.error || 'Failed to download audio');
        }
    } catch (err) {
        progressFill.classList.add('error');
        showError('Network error: ' + err.message);
    } finally {
        resetButtons();
    }
}

async function handleOverlay() {
    const videoFile = overlayVideoInput.files[0];
    const audioFile = overlayAudioInput.files[0];
    
    if (!videoFile) {
        showError('Please select a video file');
        return;
    }
    if (!audioFile) {
        showError('Please select an audio file');
        return;
    }
    
    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    progressContainer.classList.remove('hidden');
    overlayBtn.disabled = true;
    overlayBtn.textContent = 'Processing...';
    updateProgress(10, 'Uploading files...');
    
    try {
        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('audio', audioFile);
        formData.append('fade', overlayFadeInput.value);
        
        updateProgress(30, 'Processing...');
        
        const response = await fetch('/api/overlay', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateProgress(100, 'Complete!');
            progressFill.classList.add('complete');
            showResults([data.path]);
        } else {
            progressFill.classList.add('error');
            showError(data.error || 'Failed to overlay audio');
        }
    } catch (err) {
        progressFill.classList.add('error');
        showError('Network error: ' + err.message);
    } finally {
        overlayBtn.disabled = false;
        overlayBtn.textContent = '🎬 Overlay Audio';
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        showError('WebSocket error');
        resetGenerateButton();
    };
    
    ws.onclose = () => {
        console.log('WebSocket closed');
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'job_started':
            currentJobId = data.job_id;
            updateProgress(0, 'Starting...');
            break;
            
        case 'progress':
            updateProgress(data.progress, data.message);
            break;
            
        case 'complete':
            updateProgress(100, 'Complete!');
            progressFill.classList.add('complete');
            showResults(data.outputs);
            resetButtons();
            break;
            
        case 'error':
            progressFill.classList.add('error');
            showError(data.error);
            resetButtons();
            break;
    }
}

function updateProgress(percent, message) {
    progressFill.style.width = `${percent}%`;
    progressText.textContent = message;
}

function showResults(outputs) {
    resultsSection.classList.remove('hidden');
    resultsList.innerHTML = outputs.map(path => {
        const filename = path.split('/').pop();
        return `
            <div class="result-item">
                <span class="filename">${escapeHtml(filename)}</span>
                <span class="status">✓ Created</span>
            </div>
        `;
    }).join('');
    
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function setButtonsDisabled(disabled) {
    generateBtn.disabled = disabled;
    downloadAudioBtn.disabled = disabled;
}

function resetButtons() {
    generateBtn.disabled = false;
    generateBtn.textContent = '🎬 Generate Clips';
    downloadAudioBtn.disabled = false;
    downloadAudioBtn.textContent = '🎵 Download Audio';
    if (ws) {
        ws.close();
        ws = null;
    }
}

function handleBrowse() {
    // Since we can't access the file system from the browser,
    // we'll use a simple prompt as a workaround
    const current = outdirInput.value;
    const newPath = prompt('Enter output directory path:', current);
    if (newPath !== null) {
        outdirInput.value = newPath;
    }
}

function showError(message) {
    // Remove existing errors
    const existing = document.querySelector('.error-message');
    if (existing) existing.remove();
    
    const error = document.createElement('div');
    error.className = 'error-message';
    error.textContent = message;
    
    // Insert after the action card or at the end of main
    const actionCard = document.querySelector('.action-card');
    if (actionCard) {
        actionCard.appendChild(error);
    } else {
        document.querySelector('main').appendChild(error);
    }
    
    // Auto-remove after 5 seconds
    setTimeout(() => error.remove(), 5000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Start
init();
