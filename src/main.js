import './styles.css';
import { AudioAnalyzer } from './audio/analyzer.js';
import { VISUALIZER_MODES, createVisualizerState, renderVisualizer, resetVisualizerState } from './visualizers/index.js';

const modeOptions = Object.entries(VISUALIZER_MODES)
  .map(([value, config]) => `<option value="${value}">${config.label}</option>`)
  .join('');

const params = new URLSearchParams(window.location.search);
const channelName = params.get('channel') || 'bard-visualizer-default';
const displayMode = params.get('display');
const startInObsMode = displayMode === 'obs';
const startInViewerMode = displayMode === 'viewer';
const relayUrl = `/api/visualizer-state?channel=${encodeURIComponent(channelName)}`;

const createEmptyFrame = () => ({
  frequencyData: new Uint8Array(128),
  timeDomainData: new Uint8Array(256),
  level: 0,
});

const serializeFrame = (frame) => ({
  frequencyData: Array.from(frame.frequencyData),
  timeDomainData: Array.from(frame.timeDomainData),
  level: frame.level,
});

const deserializeFrame = (payload) => {
  if (!payload) {
    return null;
  }

  return {
    frequencyData: Uint8Array.from(payload.frequencyData),
    timeDomainData: Uint8Array.from(payload.timeDomainData),
    level: payload.level,
  };
};

const app = document.querySelector('#app');

app.innerHTML = `
  <div class="app-shell">
    <aside class="control-panel">
      <div class="panel-header">
        <h1>Bard Music Visualizer</h1>
        <p>Version 1 focuses on one audio source, five visualizer modes, and an OBS-friendly browser source workflow.</p>
      </div>

      <div class="button-row">
        <button class="primary-button" id="connect-button">Connect audio</button>
        <button class="secondary-button" id="obs-toggle-button">Toggle OBS mode</button>
      </div>

      <p class="status-text" id="status-text">Choose an audio source to begin.</p>
      <p class="hint-text">For system or OBS output capture on Windows, a loopback or virtual cable route may be needed depending on your device setup.</p>

      <div class="control-group">
        <label for="mode-select">Visualizer mode</label>
        <select id="mode-select">${modeOptions}</select>
      </div>

      <div class="control-group">
        <label for="sensitivity-range">Sensitivity</label>
        <input id="sensitivity-range" type="range" min="0.5" max="2.5" value="1" step="0.05" />
        <span class="range-value" id="sensitivity-value">1.00x</span>
      </div>

      <div class="control-group">
        <label for="smoothing-range">Smoothing</label>
        <input id="smoothing-range" type="range" min="0.1" max="0.98" value="0.82" step="0.01" />
        <span class="range-value" id="smoothing-value">0.82</span>
      </div>

      <div class="control-group">
        <label for="fft-select">FFT size</label>
        <select id="fft-select">
          <option value="512">512</option>
          <option value="1024">1024</option>
          <option value="2048" selected>2048</option>
          <option value="4096">4096</option>
          <option value="8192">8192</option>
        </select>
      </div>

      <div class="control-group">
        <label for="primary-color">Primary color</label>
        <input id="primary-color" type="color" value="#7c5cff" />
      </div>

      <div class="control-group">
        <label for="accent-color">Accent color</label>
        <input id="accent-color" type="color" value="#17d9ff" />
      </div>

      <div class="control-group">
        <label for="transparent-toggle">Transparent background</label>
        <input id="transparent-toggle" type="checkbox" />
      </div>
    </aside>

    <main class="preview-area">
      <canvas class="visualizer-canvas" id="visualizer-canvas"></canvas>
      <div class="overlay">
        <strong id="overlay-mode">Bars</strong>
        <span id="overlay-level">Waiting for audio</span>
      </div>
    </main>
  </div>
`;

const analyzer = new AudioAnalyzer();
const visualizerState = createVisualizerState();
let mirroredFrame = null;
let mirroredSettings = null;
let lastRelayUpdate = 0;
let relayWriteInFlight = false;

const connectButton = document.querySelector('#connect-button');
const obsToggleButton = document.querySelector('#obs-toggle-button');
const statusText = document.querySelector('#status-text');
const modeSelect = document.querySelector('#mode-select');
const sensitivityRange = document.querySelector('#sensitivity-range');
const sensitivityValue = document.querySelector('#sensitivity-value');
const smoothingRange = document.querySelector('#smoothing-range');
const smoothingValue = document.querySelector('#smoothing-value');
const fftSelect = document.querySelector('#fft-select');
const primaryColorInput = document.querySelector('#primary-color');
const accentColorInput = document.querySelector('#accent-color');
const transparentToggle = document.querySelector('#transparent-toggle');
const canvas = document.querySelector('#visualizer-canvas');
const overlayMode = document.querySelector('#overlay-mode');
const overlayLevel = document.querySelector('#overlay-level');
const ctx = canvas.getContext('2d');

const settings = {
  mode: 'bars',
  sensitivity: 1,
  smoothing: 0.82,
  fftSize: 2048,
  primaryColor: '#7c5cff',
  accentColor: '#17d9ff',
  transparentBackground: false,
};

const syncTransparentMode = () => {
  document.body.classList.toggle('transparent-mode', settings.transparentBackground);
};

const applySettingsToControls = () => {
  modeSelect.value = settings.mode;
  sensitivityRange.value = String(settings.sensitivity);
  sensitivityValue.textContent = `${settings.sensitivity.toFixed(2)}x`;
  smoothingRange.value = String(settings.smoothing);
  smoothingValue.textContent = settings.smoothing.toFixed(2);
  fftSelect.value = String(settings.fftSize);
  primaryColorInput.value = settings.primaryColor;
  accentColorInput.value = settings.accentColor;
  transparentToggle.checked = settings.transparentBackground;
  syncTransparentMode();
};

const publishRelayState = async (frame = null) => {
  if (startInObsMode || startInViewerMode || relayWriteInFlight) {
    return;
  }

  relayWriteInFlight = true;

  try {
    const response = await fetch(relayUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        settings,
        frame: frame ? serializeFrame(frame) : null,
      }),
    });

    if (response.ok) {
      lastRelayUpdate = Date.now();
    }
  } catch {
    return;
  } finally {
    relayWriteInFlight = false;
  }
};

const resizeCanvas = () => {
  const ratio = window.devicePixelRatio || 1;
  const bounds = canvas.getBoundingClientRect();
  canvas.width = Math.floor(bounds.width * ratio);
  canvas.height = Math.floor(bounds.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
};

const updateOverlay = (frame) => {
  overlayMode.textContent = VISUALIZER_MODES[settings.mode].label;

  if (!frame) {
    overlayLevel.textContent = 'Waiting for audio';
    return;
  }

  overlayLevel.textContent = `Level ${(frame.level * 100).toFixed(1)}%`;
};

const render = () => {
  const liveFrame = analyzer.getFrame();
  const frame = liveFrame ?? mirroredFrame;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  renderVisualizer(
    ctx,
    settings.mode,
    frame ?? createEmptyFrame(),
    settings,
    { width, height },
    visualizerState,
  );

  updateOverlay(frame);

  if (liveFrame) {
    publishRelayState(liveFrame);
  }

  window.requestAnimationFrame(render);
};

const updateStatus = (message) => {
  statusText.textContent = message;
};

const pollMirroredState = async () => {
  try {
    const response = await fetch(relayUrl, {
      cache: 'no-store',
    });

    if (!response.ok) {
      return;
    }

    const payload = await response.json();

    if (!payload || payload.updatedAt <= lastRelayUpdate) {
      return;
    }

    lastRelayUpdate = payload.updatedAt;

    if (payload.settings) {
      mirroredSettings = {
        settings: payload.settings,
        timestamp: payload.updatedAt,
      };
      applyMirroredSettings(payload.settings);
    }

    if (payload.frame) {
      mirroredFrame = {
        ...deserializeFrame(payload.frame),
        timestamp: payload.updatedAt,
      };
    }
  } catch {
    return;
  }
};

const applyMirroredSettings = (nextSettings) => {
  settings.mode = nextSettings.mode;
  settings.sensitivity = nextSettings.sensitivity;
  settings.smoothing = nextSettings.smoothing;
  settings.fftSize = nextSettings.fftSize;
  settings.primaryColor = nextSettings.primaryColor;
  settings.accentColor = nextSettings.accentColor;
  settings.transparentBackground = nextSettings.transparentBackground;
  applySettingsToControls();
};

const connectAudio = async () => {
  try {
    updateStatus('Requesting audio stream...');

    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        sampleRate: 48000,
      },
    });

    await analyzer.connectStream(stream);
    analyzer.setSmoothing(settings.smoothing);
    analyzer.setFftSize(settings.fftSize);
    resetVisualizerState(visualizerState);
    publishRelayState();
    updateStatus('Audio connected. If prompted, choose the screen/window/tab carrying your target audio output.');
  } catch (error) {
    updateStatus(`Audio connection failed: ${error.message}`);
  }
};

if (startInObsMode || startInViewerMode) {
  document.body.classList.add('obs-mode');
}

if (startInViewerMode) {
  connectButton.disabled = true;
  connectButton.textContent = 'Viewer mode';
  updateStatus(`Viewer mode is polling channel "${channelName}" for live audio-reactive frames.`);
} else if (startInObsMode) {
  updateStatus(`OBS mode is polling channel "${channelName}" for mirrored analyzer frames.`);
}

if (startInObsMode || startInViewerMode) {
  window.setInterval(pollMirroredState, 60);
  pollMirroredState();
}

applySettingsToControls();

connectButton.addEventListener('click', connectAudio);
obsToggleButton.addEventListener('click', () => {
  document.body.classList.toggle('obs-mode');
});
modeSelect.addEventListener('change', (event) => {
  settings.mode = event.target.value;
  resetVisualizerState(visualizerState);
  publishRelayState();
});
sensitivityRange.addEventListener('input', (event) => {
  settings.sensitivity = Number(event.target.value);
  sensitivityValue.textContent = `${settings.sensitivity.toFixed(2)}x`;
  publishRelayState();
});
smoothingRange.addEventListener('input', (event) => {
  settings.smoothing = Number(event.target.value);
  smoothingValue.textContent = settings.smoothing.toFixed(2);
  analyzer.setSmoothing(settings.smoothing);
  publishRelayState();
});
fftSelect.addEventListener('change', (event) => {
  settings.fftSize = Number(event.target.value);
  analyzer.setFftSize(settings.fftSize);
  resetVisualizerState(visualizerState);
  publishRelayState();
});
primaryColorInput.addEventListener('input', (event) => {
  settings.primaryColor = event.target.value;
  publishRelayState();
});
accentColorInput.addEventListener('input', (event) => {
  settings.accentColor = event.target.value;
  publishRelayState();
});
transparentToggle.addEventListener('change', (event) => {
  settings.transparentBackground = event.target.checked;
  syncTransparentMode();
  publishRelayState();
});
window.addEventListener('resize', resizeCanvas);

resizeCanvas();
render();
