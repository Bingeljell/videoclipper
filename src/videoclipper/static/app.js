/**
 * Video Clipper - Web UI JavaScript
 */

// DOM Elements
const urlInput = document.getElementById('urlInput');
const getInfoBtn = document.getElementById('getInfoBtn');
const getLocalInfoBtn = document.getElementById('getLocalInfoBtn');
const infoPanel = document.getElementById('infoPanel');
const infoTitle = document.getElementById('infoTitle');
const infoChannel = document.getElementById('infoChannel');
const infoDuration = document.getElementById('infoDuration');
const infoHeights = document.getElementById('infoHeights');
const statusPill = document.getElementById('statusPill');
const jobCard = document.getElementById('status');
const jobMessage = document.getElementById('jobMessage');
const jobPill = document.getElementById('jobPill');
const localFileInput = document.getElementById('localFileInput');
const localPathInput = document.getElementById('localPathInput');
const urlSource = document.getElementById('urlSource');
const localSource = document.getElementById('localSource');

const qualitySelect = document.getElementById('qualitySelect');
const customHeight = document.getElementById('customHeight');
const formatSelect = document.getElementById('formatSelect');
const modeSelect = document.getElementById('modeSelect');
const cookiesBrowserSelect = document.getElementById('cookiesBrowserSelect');

const addClipBtn = document.getElementById('addClipBtn');
const clipsContainer = document.getElementById('clipsContainer');

const outdirInput = document.getElementById('outdirInput');
const browseBtn = document.getElementById('browseBtn');
const prefixInput = document.getElementById('prefixInput');

const generateBtn = document.getElementById('generateBtn');
const downloadVideoBtn = document.getElementById('downloadVideoBtn');
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

const denoiseVideoInput = document.getElementById('denoiseVideoInput');
const denoiseStrengthInput = document.getElementById('denoiseStrengthInput');
const denoiseStrengthValue = document.getElementById('denoiseStrengthValue');
const denoiseBtn = document.getElementById('denoiseBtn');

const captionsVideoInput = document.getElementById('captionsVideoInput');
const captionsSubtitleInput = document.getElementById('captionsSubtitleInput');
const captionsFontSizeInput = document.getElementById('captionsFontSizeInput');
const captionsFontSizeValue = document.getElementById('captionsFontSizeValue');
const captionsBgColorInput = document.getElementById('captionsBgColorInput');
const captionsPositionInput = document.getElementById('captionsPositionInput');
const captionsBtn = document.getElementById('captionsBtn');

const compressVideoInput = document.getElementById('compressVideoInput');
const compressPathInput = document.getElementById('compressPathInput');
const compressCrfInput = document.getElementById('compressCrfInput');
const compressCrfValue = document.getElementById('compressCrfValue');
const compressPresetSelect = document.getElementById('compressPresetSelect');
const compressHeightInput = document.getElementById('compressHeightInput');
const compressOutdirInput = document.getElementById('compressOutdirInput');
const compressBtn = document.getElementById('compressBtn');

const resultsSection = document.getElementById('results');
const resultsList = document.getElementById('resultsList');

// WebSocket
let ws = null;
let currentJobId = null;

// Initialize
function init() {
    setupEventListeners();
    setupQualityToggle();
    setupClipsContainer();
    setupSourceToggle();
    setStatus('idle', 'Ready');
}

function setupEventListeners() {
    getInfoBtn.addEventListener('click', handleGetInfo);
    if (getLocalInfoBtn) {
        getLocalInfoBtn.addEventListener('click', handleGetInfo);
    }
    addClipBtn.addEventListener('click', addClipRow);
    generateBtn.addEventListener('click', handleGenerate);
    downloadVideoBtn.addEventListener('click', handleDownloadVideo);
    downloadAudioBtn.addEventListener('click', handleDownloadAudio);
    browseBtn.addEventListener('click', handleBrowse);
    
    // Overlay events
    overlayFadeInput.addEventListener('input', (e) => {
        overlayFadeValue.textContent = e.target.value + 's';
    });
    overlayBtn.addEventListener('click', handleOverlay);
    
    // De-noise events
    denoiseStrengthInput.addEventListener('input', (e) => {
        denoiseStrengthValue.textContent = e.target.value + '%';
    });
    denoiseBtn.addEventListener('click', handleDenoise);
    
    // Captions events
    captionsFontSizeInput.addEventListener('input', (e) => {
        captionsFontSizeValue.textContent = e.target.value + 'px';
    });
    captionsBtn.addEventListener('click', handleCaptions);

    if (compressCrfInput) {
        compressCrfInput.addEventListener('input', (e) => {
            compressCrfValue.textContent = e.target.value;
        });
    }
    if (compressBtn) {
        compressBtn.addEventListener('click', handleCompress);
    }
}

function setupSourceToggle() {
    const radios = document.querySelectorAll('input[name="sourceType"]');
    radios.forEach(radio => {
        radio.addEventListener('change', () => {
            const sourceType = getSourceType();
            if (sourceType === 'local') {
                urlSource.classList.add('hidden');
                localSource.classList.remove('hidden');
            } else {
                localSource.classList.add('hidden');
                urlSource.classList.remove('hidden');
            }
        });
    });
}

function getSourceType() {
    const selected = document.querySelector('input[name="sourceType"]:checked');
    return selected ? selected.value : 'url';
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

function setStatus(state, message) {
    if (!statusPill || !jobPill || !jobMessage) return;
    statusPill.className = `status-pill ${state}`;
    jobPill.className = `job-pill ${state}`;
    statusPill.textContent = state === 'working' ? 'Working' : state === 'error' ? 'Error' : 'Idle';
    jobPill.textContent = statusPill.textContent;
    if (message) {
        jobMessage.textContent = message;
    }
}

function startTask(message) {
    if (jobCard) jobCard.classList.remove('hidden');
    if (progressContainer) progressContainer.classList.remove('hidden');
    progressFill.classList.remove('complete', 'error');
    updateProgress(5, message || 'Working...');
    setStatus('working', message || 'Working...');
}

function finishTask(message) {
    updateProgress(100, message || 'Complete');
    progressFill.classList.add('complete');
    setStatus('idle', 'Ready');
}

function failTask(message) {
    progressFill.classList.add('error');
    setStatus('error', message || 'Error');
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
    const sourceType = getSourceType();
    const button = sourceType === 'local' ? getLocalInfoBtn : getInfoBtn;
    if (button) {
        button.disabled = true;
        button.textContent = 'Loading...';
    }

    try {
        let response = null;
        if (sourceType === 'local') {
            const file = localFileInput?.files?.[0];
            const pathValue = localPathInput?.value?.trim() || '';
            if (!file && !pathValue) {
                showError('Please select a file or enter a local path');
                return;
            }
            const formData = new FormData();
            if (file) {
                formData.append('video', file);
            } else {
                formData.append('path', pathValue);
            }
            response = await fetch('/api/info_local', {
                method: 'POST',
                body: formData
            });
        } else {
            const url = urlInput.value.trim();
            if (!url) {
                showError('Please enter a URL');
                return;
            }
            const cookies = getCookiesFromBrowser();
            let infoUrl = `/api/info?url=${encodeURIComponent(url)}`;
            if (cookies) {
                infoUrl += `&cookies_from_browser=${encodeURIComponent(cookies)}`;
            }
            response = await fetch(infoUrl);
        }

        const data = await response.json();

        if (data.success) {
            infoTitle.textContent = data.title || 'Unknown';
            infoChannel.textContent = data.channel || 'Unknown';
            infoDuration.textContent = data.duration_text || 'Unknown';
            infoHeights.textContent = data.h264_heights?.join(', ') || 'None';
            infoPanel.classList.remove('hidden');
            setStatus('idle', 'Info loaded');
        } else {
            showError(data.error || 'Failed to get info');
        }
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = 'Get Info';
        }
    }
}

function getCookiesFromBrowser() {
    return cookiesBrowserSelect?.value?.trim() || '';
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
    const sourceType = getSourceType();

    const clips = collectClips();
    if (!clips) {
        showError('Please add at least one clip with start and end times');
        return;
    }

    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    setButtonsDisabled(true);
    generateBtn.textContent = 'Processing...';
    startTask('Preparing clips...');

    if (sourceType === 'local') {
        await handleGenerateLocal(clips);
        return;
    }

    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a URL');
        resetButtons();
        return;
    }

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
                format: formatSelect.value,
                cookies_from_browser: getCookiesFromBrowser()
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

async function handleGenerateLocal(clips) {
    const file = localFileInput?.files?.[0];
    const pathValue = localPathInput?.value?.trim() || '';
    if (!file && !pathValue) {
        showError('Please select a file or enter a local path');
        resetButtons();
        return;
    }

    updateProgress(10, 'Preparing local clip...');

    try {
        const formData = new FormData();
        if (file) {
            formData.append('video', file);
        } else {
            formData.append('path', pathValue);
        }
        formData.append('clips', clips);
        formData.append('outdir', outdirInput.value.trim() || './clips');
        formData.append('reencode', modeSelect.value === 'precise');
        formData.append('output_format', formatSelect.value);

        updateProgress(30, 'Processing...');

        const response = await fetch('/api/clip_local', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.success) {
            finishTask('Complete');
            showResults(data.paths || []);
        } else {
            failTask(data.error || 'Failed to generate clips');
            showError(data.error || 'Failed to generate clips');
        }
    } catch (err) {
        failTask('Network error');
        showError('Network error: ' + err.message);
    } finally {
        resetButtons();
    }
}

async function handleDownloadVideo() {
    if (getSourceType() === 'local') {
        showError('Video download is only available for URL sources');
        return;
    }
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a URL');
        return;
    }

    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    setButtonsDisabled(true);
    downloadVideoBtn.textContent = 'Downloading...';
    startTask('Downloading video...');

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                outdir: outdirInput.value.trim() || './fullvideos',
                quality_height: getQualityHeight(),
                reencode: modeSelect.value === 'precise',
                cookies_from_browser: getCookiesFromBrowser()
            })
        });

        const data = await response.json();

        if (data.success) {
            finishTask('Complete');
            showResults([data.path]);
        } else {
            failTask(data.error || 'Failed to download video');
            showError(data.error || 'Failed to download video');
        }
    } catch (err) {
        failTask('Network error');
        showError('Network error: ' + err.message);
    } finally {
        resetButtons();
    }
}

async function handleDownloadAudio() {
    if (getSourceType() === 'local') {
        showError('Audio download is only available for URL sources');
        return;
    }
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
    setButtonsDisabled(true);
    downloadAudioBtn.textContent = 'Downloading...';
    startTask('Downloading audio...');

    try {
        const response = await fetch('/api/audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                outdir: outdirInput.value.trim() || './audio',
                format: audioFormat,
                cookies_from_browser: getCookiesFromBrowser()
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            finishTask('Complete');
            showResults([data.path]);
        } else {
            failTask(data.error || 'Failed to download audio');
            showError(data.error || 'Failed to download audio');
        }
    } catch (err) {
        failTask('Network error');
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
    overlayBtn.disabled = true;
    overlayBtn.textContent = 'Processing...';
    startTask('Uploading files...');
    
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
            finishTask('Complete');
            showResults([data.path]);
        } else {
            failTask(data.error || 'Failed to overlay audio');
            showError(data.error || 'Failed to overlay audio');
        }
    } catch (err) {
        failTask('Network error');
        showError('Network error: ' + err.message);
    } finally {
        overlayBtn.disabled = false;
        overlayBtn.textContent = '🎬 Overlay Audio';
    }
}

async function handleDenoise() {
    const videoFile = denoiseVideoInput.files[0];
    
    if (!videoFile) {
        showError('Please select a video file');
        return;
    }
    
    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    denoiseBtn.disabled = true;
    denoiseBtn.textContent = 'Processing...';
    startTask('Uploading video...');
    
    try {
        const formData = new FormData();
        formData.append('video', videoFile);
        // Convert percentage (0-100) to strength (0.0-1.0)
        formData.append('strength', (denoiseStrengthInput.value / 100).toString());
        
        updateProgress(30, 'De-noising audio...');
        
        const response = await fetch('/api/denoise', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            finishTask('Complete');
            showResults([data.path]);
        } else {
            failTask(data.error || 'Failed to de-noise video');
            showError(data.error || 'Failed to de-noise video');
        }
    } catch (err) {
        failTask('Network error');
        showError('Network error: ' + err.message);
    } finally {
        denoiseBtn.disabled = false;
        denoiseBtn.textContent = '🔇 De-noise Video';
    }
}

async function handleCaptions() {
    const videoFile = captionsVideoInput.files[0];
    const subtitleFile = captionsSubtitleInput.files[0];
    
    if (!videoFile) {
        showError('Please select a video file');
        return;
    }
    if (!subtitleFile) {
        showError('Please select a subtitle file (SRT, VTT, or ASS)');
        return;
    }
    
    // Reset UI
    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    captionsBtn.disabled = true;
    captionsBtn.textContent = 'Processing...';
    startTask('Uploading files...');
    
    try {
        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('subtitles', subtitleFile);
        formData.append('font_size', captionsFontSizeInput.value);
        formData.append('bg_color', captionsBgColorInput.value);
        formData.append('position', captionsPositionInput.value);
        
        updateProgress(30, 'Burning captions...');
        
        const response = await fetch('/api/captions', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            finishTask('Complete');
            showResults([data.path]);
        } else {
            failTask(data.error || 'Failed to add captions');
            showError(data.error || 'Failed to add captions');
        }
    } catch (err) {
        failTask('Network error');
        showError('Network error: ' + err.message);
    } finally {
        captionsBtn.disabled = false;
        captionsBtn.textContent = '💬 Add Captions';
    }
}

async function handleCompress() {
    const file = compressVideoInput?.files?.[0];
    const pathValue = compressPathInput?.value?.trim() || '';
    if (!file && !pathValue) {
        showError('Please select a file or enter a local path');
        return;
    }

    resultsSection.classList.add('hidden');
    resultsList.innerHTML = '';
    compressBtn.disabled = true;
    compressBtn.textContent = 'Processing...';
    startTask('Uploading video...');

    try {
        const formData = new FormData();
        if (file) {
            formData.append('video', file);
        } else {
            formData.append('path', pathValue);
        }
        formData.append('outdir', compressOutdirInput.value.trim() || './compressed');
        formData.append('crf', compressCrfInput.value);
        formData.append('preset', compressPresetSelect.value);
        if (compressHeightInput.value) {
            formData.append('height', compressHeightInput.value);
        }
        formData.append('output_format', 'mp4');

        updateProgress(30, 'Compressing...');

        const response = await fetch('/api/compress', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.success) {
            finishTask('Complete');
            showResults([data.path]);
        } else {
            failTask(data.error || 'Failed to compress video');
            showError(data.error || 'Failed to compress video');
        }
    } catch (err) {
        failTask('Network error');
        showError('Network error: ' + err.message);
    } finally {
        compressBtn.disabled = false;
        compressBtn.textContent = '📦 Compress Video';
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
            startTask('Starting...');
            break;
            
        case 'progress':
            updateProgress(data.progress, data.message);
            break;
            
        case 'complete':
            finishTask('Complete');
            showResults(data.outputs);
            resetButtons();
            break;
            
        case 'error':
            failTask(data.error);
            showError(data.error);
            resetButtons();
            break;
    }
}

function updateProgress(percent, message) {
    progressFill.style.width = `${percent}%`;
    progressText.textContent = message;
    if (message) {
        jobMessage.textContent = message;
    }
}

function showResults(outputs) {
    resultsSection.classList.remove('hidden');
    resultsList.innerHTML = outputs.map(path => {
        const parts = path.split('/');
        const filename = parts.pop();
        const directory = parts.join('/') || '.';
        return `
            <div class="result-item">
                <div>
                    <span class="filename">${escapeHtml(filename)}</span>
                    <span class="directory">in ${escapeHtml(directory)}</span>
                </div>
                <span class="status">✓ Created</span>
            </div>
        `;
    }).join('');
    
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function setButtonsDisabled(disabled) {
    generateBtn.disabled = disabled;
    downloadVideoBtn.disabled = disabled;
    downloadAudioBtn.disabled = disabled;
}

function resetButtons() {
    generateBtn.disabled = false;
    generateBtn.textContent = '🎬 Generate Clips';
    downloadVideoBtn.disabled = false;
    downloadVideoBtn.textContent = '⬇️ Download Video';
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
    setStatus('error', message);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Start
init();
