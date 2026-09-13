// zk-KYC Issuer Single-Page Application Logic

// DOM Elements
const elements = {
  // Screens
  screenStart: document.getElementById('screen-start'),
  screenCapture: document.getElementById('screen-capture'),
  screenResult: document.getElementById('screen-result'),

  // Header & Health
  btnToggleHealth: document.getElementById('btn-toggle-health'),
  globalStatusDot: document.getElementById('global-status-dot'),
  globalStatusText: document.getElementById('global-status-text'),
  btnToggleConfig: document.getElementById('btn-toggle-config'),
  configDrawer: document.getElementById('config-drawer'),
  apiBaseUrlInput: document.getElementById('api-base-url'),
  btnSaveConfig: document.getElementById('btn-save-config'),
  healthPanel: document.getElementById('health-panel'),
  btnRefreshHealth: document.getElementById('btn-refresh-health'),
  healthPassive: document.getElementById('health-passive'),
  healthDoc: document.getElementById('health-doc'),
  healthHead: document.getElementById('health-head'),
  healthSpeech: document.getElementById('health-speech'),
  healthSigner: document.getElementById('health-signer'),
  issuanceBanner: document.getElementById('issuance-banner'),
  issuanceBannerText: document.getElementById('issuance-banner-text'),

  // Start Screen
  btnBegin: document.getElementById('btn-begin-verification'),

  // Capture Screen
  sessionIdDisplay: document.getElementById('session-id-display'),
  sessionTimerPill: document.getElementById('session-timer-pill'),
  sessionTimerText: document.getElementById('session-timer-text'),
  challengePrompt: document.getElementById('challenge-prompt'),
  headTurnWidget: document.getElementById('head-turn-widget'),
  headTurnDirection: document.getElementById('head-turn-direction'),
  headTurnArrow: document.getElementById('head-turn-arrow'),
  speechWidget: document.getElementById('speech-widget'),
  digitsContainer: document.getElementById('digits-container'),
  audioBarFill: document.getElementById('audio-bar-fill'),

  // ID Photo Section
  idStatusBadge: document.getElementById('id-status-badge'),
  idDropzone: document.getElementById('id-dropzone'),
  idFileInput: document.getElementById('id-file-input'),
  idPreviewBox: document.getElementById('id-preview-box'),
  idPreviewImg: document.getElementById('id-preview-img'),
  photoFilename: document.getElementById('photo-filename'),
  btnRemovePhoto: document.getElementById('btn-remove-photo'),

  // Video Recording Section
  livenessStatusBadge: document.getElementById('liveness-status-badge'),
  docStatusBadge: document.getElementById('doc-status-badge'),
  tabLivenessClip: document.getElementById('tab-liveness-clip'),
  tabDocClip: document.getElementById('tab-doc-clip'),
  webcamVideo: document.getElementById('webcam-video'),
  recordingOverlay: document.getElementById('recording-overlay'),
  recTimerText: document.getElementById('rec-timer-text'),
  recTargetLabel: document.getElementById('rec-target-label'),
  codecBadge: document.getElementById('codec-badge'),
  recProgressBar: document.getElementById('rec-progress-bar'),
  btnStartRecordLiveness: document.getElementById('btn-start-record-liveness'),
  btnStartRecordDoc: document.getElementById('btn-start-record-doc'),
  btnStopRecord: document.getElementById('btn-stop-record'),
  btnPlayPreviewLiveness: document.getElementById('btn-play-preview-liveness'),
  btnPlayPreviewDoc: document.getElementById('btn-play-preview-doc'),

  // Submission & Pipeline
  submitIdleState: document.getElementById('submit-idle-state'),
  submitValidationHint: document.getElementById('submit-validation-hint'),
  btnSubmit: document.getElementById('btn-submit-verification'),
  submitPipelineState: document.getElementById('submit-pipeline-state'),
  pipeUpload: document.getElementById('pipe-upload'),
  pipePassive: document.getElementById('pipe-passive'),
  pipeActive: document.getElementById('pipe-active'),
  pipeOcr: document.getElementById('pipe-ocr'),
  pipeDoc: document.getElementById('pipe-doc'),
  pipeSign: document.getElementById('pipe-sign'),

  // Result Screen: Success
  resultSuccessContainer: document.getElementById('result-success-container'),
  credSchema: document.getElementById('cred-schema'),
  credDobFormatted: document.getElementById('cred-dob-formatted'),
  credIssuerId: document.getElementById('cred-issuer-id'),
  credIssuedAt: document.getElementById('cred-issued-at'),
  credHolderSecret: document.getElementById('cred-holder-secret'),
  btnToggleSecret: document.getElementById('btn-toggle-secret'),
  credIssuerPub: document.getElementById('cred-issuer-pub'),
  credSig: document.getElementById('cred-sig'),
  btnDownloadJson: document.getElementById('btn-download-json'),
  btnRestartSuccess: document.getElementById('btn-restart-success'),

  // Interactive ZK Prover & Verifier
  btnGenerateProof: document.getElementById('btn-generate-proof'),
  btnGenerateProofSpinner: document.getElementById('btn-generate-proof-spinner'),
  btnGenerateProofText: document.getElementById('btn-generate-proof-text'),
  btnVerifyProof: document.getElementById('btn-verify-proof'),
  btnVerifyProofSpinner: document.getElementById('btn-verify-proof-spinner'),
  btnVerifyProofText: document.getElementById('btn-verify-proof-text'),
  btnDownloadProof: document.getElementById('btn-download-proof'),
  provingStatusBox: document.getElementById('proving-status-box'),
  provingStatusText: document.getElementById('proving-status-text'),
  proofResultBox: document.getElementById('proof-result-box'),
  proofSignalAxAy: document.getElementById('proof-signal-axay'),
  proofSignalRef: document.getElementById('proof-signal-ref'),
  verificationResultBanner: document.getElementById('verification-result-banner'),
  verificationBannerTitle: document.getElementById('verification-banner-title'),
  verificationBannerDesc: document.getElementById('verification-banner-desc'),

  // Result Screen: Failure
  resultFailureContainer: document.getElementById('result-failure-container'),
  errCodeBadge: document.getElementById('err-code-badge'),
  errDetailsDump: document.getElementById('err-details-dump'),
  errTroubleshootingText: document.getElementById('err-troubleshooting-text'),
  btnRestartError: document.getElementById('btn-restart-error'),
};

// Application State
const state = {
  apiBaseUrl: localStorage.getItem('zkkyc_api_base') || 'http://127.0.0.1:8000',
  currentSession: null,
  sessionExpiresAt: 0,
  sessionTimerInterval: null,

  // Media
  webcamStream: null,
  mediaRecorder: null,
  recordedChunks: [],
  recordedMimeType: '',
  recordingDuration: 0,
  recordingTimerInterval: null,
  isRecording: false,
  activeRecordTarget: null, // 'liveness' | 'doc'

  // Clips
  livenessBlob: null,
  docBlob: null,

  // Audio analysis
  audioContext: null,
  analyserNode: null,
  audioAnimFrame: null,

  // Files
  idPhotoFile: null,

  // Results
  issuedCredential: null,
  generatedProof: null,
  secretRevealed: false,
  isGeneratingProof: false,
  isVerifyingProof: false,
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  elements.apiBaseUrlInput.value = state.apiBaseUrl;
  bindEvents();
  fetchHealth();
});

// --- Event Binding ---
function bindEvents() {
  // Config & Health Toggles
  elements.btnToggleConfig.addEventListener('click', () => {
    elements.configDrawer.classList.toggle('hidden');
  });

  elements.btnSaveConfig.addEventListener('click', () => {
    let url = elements.apiBaseUrlInput.value.trim();
    if (url.endsWith('/')) url = url.slice(0, -1);
    state.apiBaseUrl = url;
    localStorage.setItem('zkkyc_api_base', url);
    elements.configDrawer.classList.add('hidden');
    fetchHealth();
  });

  elements.btnToggleHealth.addEventListener('click', () => {
    elements.healthPanel.classList.toggle('hidden');
  });

  elements.btnRefreshHealth.addEventListener('click', fetchHealth);

  // App Flow
  elements.btnBegin.addEventListener('click', startSessionFlow);

  // ID Photo Upload
  elements.idDropzone.addEventListener('click', () => elements.idFileInput.click());
  elements.idFileInput.addEventListener('change', (e) => handleIdFileSelect(e.target.files[0]));
  elements.idDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.idDropzone.classList.add('dragover');
  });
  elements.idDropzone.addEventListener('dragleave', () => {
    elements.idDropzone.classList.remove('dragover');
  });
  elements.idDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.idDropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleIdFileSelect(e.dataTransfer.files[0]);
    }
  });
  elements.btnRemovePhoto.addEventListener('click', clearIdPhoto);

  // Video Recording Controls
  elements.tabLivenessClip.addEventListener('click', () => switchActiveClipTab('liveness'));
  elements.tabDocClip.addEventListener('click', () => switchActiveClipTab('doc'));

  elements.btnStartRecordLiveness.addEventListener('click', () => startRecording('liveness', 7));
  elements.btnStartRecordDoc.addEventListener('click', () => startRecording('doc', 4));
  elements.btnStopRecord.addEventListener('click', stopRecording);
  elements.btnPlayPreviewLiveness.addEventListener('click', () => playRecordedClip('liveness'));
  elements.btnPlayPreviewDoc.addEventListener('click', () => playRecordedClip('doc'));

  // Submission
  elements.btnSubmit.addEventListener('click', submitVerification);

  // Result Actions
  elements.btnToggleSecret.addEventListener('click', toggleSecretMask);
  elements.btnDownloadJson.addEventListener('click', downloadCredentialJson);
  elements.btnRestartSuccess.addEventListener('click', resetToStartScreen);
  elements.btnRestartError.addEventListener('click', resetToStartScreen);

  // ZK Prover & Verifier Actions
  elements.btnGenerateProof.addEventListener('click', handleGenerateProof);
  elements.btnVerifyProof.addEventListener('click', handleVerifyProof);
  elements.btnDownloadProof.addEventListener('click', downloadProofJson);
}

// --- Health Check ---
async function fetchHealth() {
  elements.globalStatusDot.className = 'status-dot';
  elements.globalStatusText.textContent = 'Connecting...';

  try {
    const res = await fetch(`${state.apiBaseUrl}/healthz`, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Update status items
    updateHealthItem(elements.healthPassive, data.passive_liveness);
    updateHealthItem(elements.healthDoc, data.document_presence);
    updateHealthItem(elements.healthHead, data.head_turn_challenge);
    updateHealthItem(elements.healthSpeech, data.speech_challenge);
    updateHealthItem(elements.healthSigner, data.signer);

    if (data.issuance_possible) {
      elements.globalStatusDot.className = 'status-dot ready';
      elements.globalStatusText.textContent = 'Issuer Ready';
      elements.issuanceBanner.className = 'issuance-status-banner possible';
      elements.issuanceBannerText.textContent = 'All critical components ready: issuance possible.';
    } else {
      elements.globalStatusDot.className = 'status-dot warning';
      elements.globalStatusText.textContent = 'Partial / Missing Components';
      elements.issuanceBanner.className = 'issuance-status-banner blocked';
      elements.issuanceBannerText.textContent = 'Issuance not possible: passive liveness, document-presence, or signer unavailable.';
    }
  } catch (err) {
    elements.globalStatusDot.className = 'status-dot error';
    elements.globalStatusText.textContent = 'Issuer Offline';
    elements.issuanceBanner.className = 'issuance-status-banner blocked';
    elements.issuanceBannerText.textContent = `Cannot reach issuer at ${state.apiBaseUrl} (${err.message}). Ensure signer & uvicorn are running.`;

    updateHealthItem(elements.healthPassive, 'offline');
    updateHealthItem(elements.healthDoc, 'offline');
    updateHealthItem(elements.healthHead, 'offline');
    updateHealthItem(elements.healthSpeech, 'offline');
    updateHealthItem(elements.healthSigner, 'offline');
  }
}

function updateHealthItem(el, val) {
  if (!el) return;
  const s = String(val || '').toLowerCase();
  if (s.startsWith('ready')) {
    el.className = 'health-item-status ready';
    el.textContent = 'Ready';
  } else {
    el.className = 'health-item-status missing';
    el.textContent = val || 'Missing';
  }
}

// --- Session Flow ---
async function startSessionFlow() {
  elements.btnBegin.disabled = true;
  elements.btnBegin.textContent = 'Creating Session...';

  try {
    const res = await fetch(`${state.apiBaseUrl}/v1/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.error?.code || `HTTP ${res.status}`);
    }

    const sess = await res.json();
    state.currentSession = sess;
    const ttl = sess.expires_in_seconds || 300;
    state.sessionExpiresAt = Date.now() + ttl * 1000;

    // Transition Screen
    showScreen('capture');

    // Populate Challenge Prompt
    elements.sessionIdDisplay.textContent = `Session: ${sess.session_id.slice(0, 8)}...`;
    
    // Read strictly from phases array
    setupPhasedChallengeUI(sess.challenge);
    startSessionTimer();

    // Start Webcam
    await initWebcam();

  } catch (err) {
    alert(`Failed to start session: ${err.message}. Please check that the issuer service is running.`);
  } finally {
    elements.btnBegin.disabled = false;
    elements.btnBegin.textContent = 'Begin Verification';
  }
}

// --- Dynamic Challenge UI ---
function setupPhasedChallengeUI(challenge) {
  const phases = challenge.phases || [challenge];
  const livenessPhase = phases[0] || {};
  const docPhase = phases[1] || {};

  elements.challengePrompt.textContent = challenge.prompt || `${livenessPhase.prompt || ''} ${docPhase.prompt || ''}`;

  if (livenessPhase.type === 'turn_head') {
    elements.headTurnWidget.classList.remove('hidden');
    elements.speechWidget.classList.add('hidden');

    const dir = (livenessPhase.direction || 'left').toUpperCase();
    elements.headTurnDirection.textContent = `TURN ${dir}`;
    elements.headTurnArrow.textContent = dir === 'LEFT' ? '←' : '→';

    stopAudioVisualizer();
  } else if (livenessPhase.type === 'speak_digits') {
    elements.speechWidget.classList.remove('hidden');
    elements.headTurnWidget.classList.add('hidden');

    elements.digitsContainer.innerHTML = '';
    const digits = livenessPhase.digits || [];
    digits.forEach((d) => {
      const pill = document.createElement('div');
      pill.className = 'digit-pill';
      pill.textContent = d;
      elements.digitsContainer.appendChild(pill);
    });

    if (state.webcamStream) {
      startAudioVisualizer(state.webcamStream);
    }
  } else {
    elements.headTurnWidget.classList.add('hidden');
    elements.speechWidget.classList.add('hidden');
  }
}

// --- Session Expiry Countdown ---
function startSessionTimer() {
  if (state.sessionTimerInterval) clearInterval(state.sessionTimerInterval);

  const update = () => {
    const remainingMs = state.sessionExpiresAt - Date.now();
    if (remainingMs <= 0) {
      clearInterval(state.sessionTimerInterval);
      elements.sessionTimerText.textContent = 'Session Expired';
      elements.sessionTimerPill.classList.add('expiring-soon');
      elements.btnSubmit.disabled = true;
      alert('Your verification session has expired. Please begin a new session.');
      resetToStartScreen();
      return;
    }

    const totalSeconds = Math.floor(remainingMs / 1000);
    const mins = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
    const secs = String(totalSeconds % 60).padStart(2, '0');
    elements.sessionTimerText.textContent = `Expires in: ${mins}:${secs}`;

    if (totalSeconds < 60) {
      elements.sessionTimerPill.classList.add('expiring-soon');
    } else {
      elements.sessionTimerPill.classList.remove('expiring-soon');
    }
  };

  update();
  state.sessionTimerInterval = setInterval(update, 1000);
}

// --- Webcam & MediaRecorder Setup ---
function pickSupportedVideoMimeType() {
  if (typeof MediaRecorder === 'undefined') return '';
  const preferred = [
    'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
    'video/mp4;codecs=avc1,opus',
    'video/mp4',
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm;codecs=h264,opus',
    'video/webm',
  ];

  for (const mime of preferred) {
    if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return '';
}

async function initWebcam() {
  try {
    if (state.webcamStream) {
      state.webcamStream.getTracks().forEach((t) => t.stop());
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'user',
      },
      audio: true,
    });

    state.webcamStream = stream;
    elements.webcamVideo.srcObject = stream;
    elements.webcamVideo.classList.remove('playback');
    elements.webcamVideo.muted = true;
    await elements.webcamVideo.play();

    const mime = pickSupportedVideoMimeType();
    state.recordedMimeType = mime;
    elements.codecBadge.textContent = mime ? `Codec: ${mime.split(';')[0]}` : 'Codec: default';

    const phases = state.currentSession?.challenge?.phases || [];
    if (phases[0]?.type === 'speak_digits') {
      startAudioVisualizer(stream);
    }

  } catch (err) {
    console.error('Webcam access error:', err);
    alert(`Could not access webcam/microphone: ${err.message}. Please allow camera & microphone permissions in your browser.`);
  }
}

function startAudioVisualizer(stream) {
  try {
    if (!window.AudioContext && !window.webkitAudioContext) return;
    stopAudioVisualizer();

    state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = state.audioContext.createMediaStreamSource(stream);
    state.analyserNode = state.audioContext.createAnalyser();
    state.analyserNode.fftSize = 256;
    source.connect(state.analyserNode);

    const bufferLength = state.analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      if (!state.analyserNode) return;
      state.analyserNode.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      const avg = sum / bufferLength;
      const pct = Math.min(100, Math.round((avg / 128) * 100));

      if (elements.audioBarFill) {
        elements.audioBarFill.style.width = `${pct}%`;
      }
      state.audioAnimFrame = requestAnimationFrame(draw);
    };

    draw();
  } catch (e) {
    console.warn('Audio meter init error:', e);
  }
}

function stopAudioVisualizer() {
  if (state.audioAnimFrame) {
    cancelAnimationFrame(state.audioAnimFrame);
    state.audioAnimFrame = null;
  }
  if (state.audioContext) {
    state.audioContext.close().catch(() => {});
    state.audioContext = null;
    state.analyserNode = null;
  }
  if (elements.audioBarFill) {
    elements.audioBarFill.style.width = '0%';
  }
}

// --- Clip Switching UI ---
function switchActiveClipTab(target) {
  if (state.isRecording) return;

  if (target === 'liveness') {
    elements.tabLivenessClip.classList.add('active');
    elements.tabDocClip.classList.remove('active');
    elements.btnStartRecordLiveness.classList.remove('hidden');
    elements.btnStartRecordDoc.classList.add('hidden');
  } else {
    elements.tabDocClip.classList.add('active');
    elements.tabLivenessClip.classList.remove('active');
    elements.btnStartRecordDoc.classList.remove('hidden');
    elements.btnStartRecordLiveness.classList.add('hidden');
  }
}

// --- Video Recording Handlers ---
function startRecording(target = 'liveness', targetDuration = 6) {
  if (!state.webcamStream) return;

  state.activeRecordTarget = target;
  state.recordedChunks = [];
  state.recordingDuration = 0;
  state.isRecording = true;

  const options = state.recordedMimeType ? { mimeType: state.recordedMimeType } : {};
  try {
    state.mediaRecorder = new MediaRecorder(state.webcamStream, options);
  } catch (e) {
    console.warn('Failed with selected mimeType, falling back to default', e);
    state.mediaRecorder = new MediaRecorder(state.webcamStream);
  }

  state.mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) {
      state.recordedChunks.push(e.data);
    }
  };

  state.mediaRecorder.onstop = () => {
    const mime = state.mediaRecorder.mimeType || state.recordedMimeType || 'video/webm';
    const blob = new Blob(state.recordedChunks, { type: mime });

    if (state.activeRecordTarget === 'liveness') {
      state.livenessBlob = blob;
      elements.livenessStatusBadge.textContent = 'Clip 1 (Face) Ready';
      elements.livenessStatusBadge.className = 'step-indicator-badge completed';
      elements.btnPlayPreviewLiveness.classList.remove('hidden');

      // Prompt to proceed to clip 2
      if (!state.docBlob) {
        switchActiveClipTab('doc');
      }
    } else {
      state.docBlob = blob;
      elements.docStatusBadge.textContent = 'Clip 2 (ID) Ready';
      elements.docStatusBadge.className = 'step-indicator-badge completed';
      elements.btnPlayPreviewDoc.classList.remove('hidden');
    }

    onRecordingComplete();
  };

  state.mediaRecorder.start(100);

  // UI Updates
  elements.btnStartRecordLiveness.classList.add('hidden');
  elements.btnStartRecordDoc.classList.add('hidden');
  elements.btnStopRecord.classList.remove('hidden');
  elements.recordingOverlay.classList.remove('hidden');
  elements.recTargetLabel.textContent = target === 'liveness' ? 'PHASE 1: FACE CHALLENGE' : 'PHASE 2: HOLD ID CARD';

  elements.recProgressBar.style.width = '0%';

  state.recordingTimerInterval = setInterval(() => {
    state.recordingDuration += 1;
    const mins = String(Math.floor(state.recordingDuration / 60)).padStart(2, '0');
    const secs = String(state.recordingDuration % 60).padStart(2, '0');
    elements.recTimerText.textContent = `REC ${mins}:${secs}`;

    const progressPct = Math.min(100, (state.recordingDuration / targetDuration) * 100);
    elements.recProgressBar.style.width = `${progressPct}%`;

    if (state.recordingDuration >= targetDuration + 1) {
      stopRecording();
    }
  }, 1000);
}

function stopRecording() {
  if (!state.isRecording || !state.mediaRecorder) return;
  state.isRecording = false;

  if (state.recordingTimerInterval) {
    clearInterval(state.recordingTimerInterval);
    state.recordingTimerInterval = null;
  }

  if (state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }

  elements.btnStopRecord.classList.add('hidden');
  elements.recordingOverlay.classList.add('hidden');
}

function onRecordingComplete() {
  if (!state.livenessBlob) {
    switchActiveClipTab('liveness');
  } else if (!state.docBlob) {
    switchActiveClipTab('doc');
  } else {
    elements.btnStartRecordDoc.classList.remove('hidden');
    elements.btnStartRecordLiveness.classList.remove('hidden');
  }

  validateSubmissionReadiness();
}

function playRecordedClip(target = 'liveness') {
  const blob = target === 'liveness' ? state.livenessBlob : state.docBlob;
  if (!blob) return;

  const url = URL.createObjectURL(blob);
  elements.webcamVideo.srcObject = null;
  elements.webcamVideo.src = url;
  elements.webcamVideo.classList.add('playback');
  elements.webcamVideo.muted = false;
  elements.webcamVideo.play();

  elements.webcamVideo.onended = () => {
    elements.webcamVideo.src = '';
    elements.webcamVideo.srcObject = state.webcamStream;
    elements.webcamVideo.classList.remove('playback');
    elements.webcamVideo.muted = true;
    elements.webcamVideo.play();
  };
}

// --- ID Photo Handling ---
function handleIdFileSelect(file) {
  if (!file) return;
  if (!file.type.startsWith('image/')) {
    alert('Please upload a valid image file (JPG or PNG).');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('ID photo is too large (maximum 10MB).');
    return;
  }

  state.idPhotoFile = file;

  const reader = new FileReader();
  reader.onload = (e) => {
    elements.idPreviewImg.src = e.target.result;
    elements.photoFilename.textContent = file.name;
    elements.idDropzone.classList.add('hidden');
    elements.idPreviewBox.classList.remove('hidden');
    elements.idStatusBadge.textContent = 'Uploaded';
    elements.idStatusBadge.className = 'step-indicator-badge completed';

    validateSubmissionReadiness();
  };
  reader.readAsDataURL(file);
}

function clearIdPhoto() {
  state.idPhotoFile = null;
  elements.idFileInput.value = '';
  elements.idPreviewBox.classList.add('hidden');
  elements.idDropzone.classList.remove('hidden');
  elements.idStatusBadge.textContent = 'Required';
  elements.idStatusBadge.className = 'step-indicator-badge';

  validateSubmissionReadiness();
}

// --- Submission Readiness ---
function validateSubmissionReadiness() {
  const hasPhoto = !!state.idPhotoFile;
  const hasLiveness = !!state.livenessBlob;
  const hasDoc = !!state.docBlob;

  if (hasPhoto && hasLiveness && hasDoc) {
    elements.btnSubmit.disabled = false;
    elements.submitValidationHint.textContent = 'ID photo and both verification clips ready. Click submit to process verification.';
    elements.submitValidationHint.style.color = 'var(--accent-green)';
  } else {
    elements.btnSubmit.disabled = true;
    if (!hasPhoto) {
      elements.submitValidationHint.textContent = 'Please upload your ID card photo.';
    } else if (!hasLiveness) {
      elements.submitValidationHint.textContent = 'Please record Clip 1 (Face Liveness Challenge).';
    } else if (!hasDoc) {
      elements.submitValidationHint.textContent = 'Please record Clip 2 (Hold Physical ID in Frame).';
    }
    elements.submitValidationHint.style.color = 'var(--text-secondary)';
  }
}

// --- Submission to Issuer Backend ---
async function submitVerification() {
  if (!state.currentSession || !state.idPhotoFile || !state.livenessBlob || !state.docBlob) return;

  if (state.sessionTimerInterval) {
    clearInterval(state.sessionTimerInterval);
  }

  elements.submitIdleState.classList.add('hidden');
  elements.submitPipelineState.classList.remove('hidden');

  const sid = state.currentSession.session_id;
  const formData = new FormData();

  formData.append('id_photo', state.idPhotoFile, state.idPhotoFile.name);

  const ext = state.recordedMimeType.includes('mp4') ? 'mp4' : 'webm';
  const liveFile = new File([state.livenessBlob], `liveness.${ext}`, {
    type: state.recordedMimeType || 'video/mp4',
  });
  const docFile = new File([state.docBlob], `doc.${ext}`, {
    type: state.recordedMimeType || 'video/mp4',
  });

  formData.append('liveness_video', liveFile);
  formData.append('video', liveFile); // backward compatibility
  formData.append('doc_video', docFile);

  animatePipelineSteps();

  try {
    const res = await fetch(`${state.apiBaseUrl}/v1/sessions/${sid}/submit`, {
      method: 'POST',
      body: formData,
    });

    const body = await res.json().catch(() => ({ error: { code: 'NON_JSON_RESPONSE' } }));

    if (res.ok && body.status === 'issued') {
      state.issuedCredential = body.credential;
      renderSuccessScreen(body.credential);
    } else {
      const err = body.error || body;
      renderFailureScreen(err, res.status);
    }

  } catch (err) {
    console.error('Submission network error:', err);
    renderFailureScreen({
      code: 'NETWORK_ERROR',
      detail: `Could not connect to issuer endpoint: ${err.message}`,
    }, 0);
  } finally {
    stopMediaTracks();
  }
}

function animatePipelineSteps() {
  const steps = [
    { el: elements.pipeUpload, delay: 0 },
    { el: elements.pipePassive, delay: 1500 },
    { el: elements.pipeActive, delay: 3500 },
    { el: elements.pipeOcr, delay: 5500 },
    { el: elements.pipeDoc, delay: 7500 },
    { el: elements.pipeSign, delay: 9500 },
  ];

  steps.forEach(({ el, delay }) => {
    setTimeout(() => {
      steps.forEach((s) => {
        if (s.el !== el && s.el.classList.contains('active')) {
          s.el.classList.remove('active');
          s.el.classList.add('completed');
          s.el.querySelector('.pipeline-step-icon').textContent = '✓';
        }
      });
      el.classList.add('active');
    }, delay);
  });
}

// --- Result Screen: Success ---
function renderSuccessScreen(credential) {
  showScreen('result');
  elements.resultSuccessContainer.classList.remove('hidden');
  elements.resultFailureContainer.classList.add('hidden');

  const dob = credential.subject?.dob || {};
  const dobString = `${dob.year}-${String(dob.month).padStart(2, '0')}-${String(dob.day).padStart(2, '0')}`;
  
  try {
    const d = new Date(dob.year, dob.month - 1, dob.day);
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    elements.credDobFormatted.textContent = `${dobString} (${d.toLocaleDateString(undefined, options)})`;
  } catch {
    elements.credDobFormatted.textContent = dobString;
  }

  elements.credSchema.textContent = `schema: ${credential.schema || 'zkkyc-credential-v1'}`;
  elements.credIssuerId.textContent = credential.issuer_id || 'did:zkkyc:issuer-1';
  
  if (credential.issued_at) {
    try {
      const localTime = new Date(credential.issued_at).toLocaleString();
      elements.credIssuedAt.textContent = `${credential.issued_at} (${localTime})`;
    } catch {
      elements.credIssuedAt.textContent = credential.issued_at;
    }
  }

  state.secretRevealed = false;
  elements.credHolderSecret.textContent = '••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••';
  elements.credHolderSecret.className = 'crypto-item-value secret-masked';
  elements.btnToggleSecret.textContent = 'Show secret';

  const pub = credential.issuer_pub || {};
  elements.credIssuerPub.textContent = `ax: ${pub.ax || '--'} | ay: ${pub.ay || '--'}`;

  const sig = credential.signature || {};
  elements.credSig.textContent = `R8x: ${sig.R8x || '--'} | R8y: ${sig.R8y || '--'} | S: ${sig.S || '--'}`;

  // Reset Prover state
  state.generatedProof = null;
  elements.btnGenerateProofText.textContent = 'Generate Proof';
  elements.btnGenerateProofSpinner.classList.add('hidden');
  elements.btnGenerateProof.disabled = false;
  elements.btnVerifyProof.classList.add('hidden');
  elements.btnDownloadProof.classList.add('hidden');
  elements.provingStatusBox.classList.add('hidden');
  elements.proofResultBox.classList.add('hidden');
  elements.verificationResultBanner.classList.add('hidden');
}

function toggleSecretMask() {
  if (!state.issuedCredential) return;
  state.secretRevealed = !state.secretRevealed;

  if (state.secretRevealed) {
    elements.credHolderSecret.textContent = state.issuedCredential.holder_secret || 'N/A';
    elements.credHolderSecret.className = 'crypto-item-value';
    elements.btnToggleSecret.textContent = 'Hide secret';
  } else {
    elements.credHolderSecret.textContent = '••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••';
    elements.credHolderSecret.className = 'crypto-item-value secret-masked';
    elements.btnToggleSecret.textContent = 'Show secret';
  }
}

function downloadCredentialJson() {
  if (!state.issuedCredential) return;
  const jsonStr = JSON.stringify(state.issuedCredential, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `credential-${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --- Interactive ZK Proof Prover & Verifier ---
async function handleGenerateProof() {
  if (!state.issuedCredential || state.isGeneratingProof) return;

  state.isGeneratingProof = true;
  elements.btnGenerateProof.disabled = true;
  elements.btnGenerateProofSpinner.classList.remove('hidden');
  elements.btnGenerateProofText.textContent = 'Generating Proof...';

  elements.provingStatusBox.classList.remove('hidden');
  elements.provingStatusBox.className = 'proving-status-box active';
  elements.provingStatusText.textContent = 'Computing SNARK witness & generating PLONK proof (CPU inference ~20s)...';

  elements.verificationResultBanner.classList.add('hidden');

  try {
    const res = await fetch(`${state.apiBaseUrl}/v1/proofs/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.issuedCredential),
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok && data.status === 'success' && data.proof) {
      state.generatedProof = data.proof;

      // Populate Proof Result Box
      const sigs = data.proof.publicSignals || [];
      const ax = sigs[0] ? `${sigs[0].slice(0, 10)}...${sigs[0].slice(-8)}` : '--';
      const ay = sigs[1] ? `${sigs[1].slice(0, 10)}...${sigs[1].slice(-8)}` : '--';
      elements.proofSignalAxAy.textContent = `ax: ${ax} | ay: ${ay}`;
      elements.proofSignalRef.textContent = sigs[2] || '--';

      elements.proofResultBox.classList.remove('hidden');
      elements.btnVerifyProof.classList.remove('hidden');
      elements.btnDownloadProof.classList.remove('hidden');

      elements.provingStatusBox.className = 'proving-status-box';
      elements.provingStatusText.textContent = 'Zero-knowledge proof generated successfully.';
      elements.btnGenerateProofText.textContent = 'Regenerate Proof';
    } else {
      const errDetail = data.error?.detail || data.error?.code || 'Proof generation failed';
      elements.provingStatusBox.className = 'proving-status-box';
      elements.provingStatusText.textContent = `Proving error: ${errDetail}`;
      alert(`Proof generation failed: ${errDetail}`);
    }
  } catch (err) {
    console.error('Proof generation network error:', err);
    elements.provingStatusBox.className = 'proving-status-box';
    elements.provingStatusText.textContent = `Network error during proof generation: ${err.message}`;
  } finally {
    state.isGeneratingProof = false;
    elements.btnGenerateProof.disabled = false;
    elements.btnGenerateProofSpinner.classList.add('hidden');
  }
}

async function handleVerifyProof() {
  if (!state.generatedProof || state.isVerifyingProof) return;

  state.isVerifyingProof = true;
  elements.btnVerifyProof.disabled = true;
  elements.btnVerifyProofSpinner.classList.remove('hidden');
  elements.btnVerifyProofText.textContent = 'Verifying...';

  try {
    const res = await fetch(`${state.apiBaseUrl}/v1/proofs/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.generatedProof),
    });

    const data = await res.json().catch(() => ({}));

    elements.verificationResultBanner.classList.remove('hidden');

    if (res.ok && data.ok) {
      elements.verificationResultBanner.className = 'verification-result-banner success';
      elements.verificationBannerTitle.textContent = 'Zero-Knowledge Proof Verified (Age >= 18)';
      const ref = data.details?.refPacked || state.generatedProof?.meta?.refPacked || 'today';
      elements.verificationBannerDesc.textContent = `Valid PLONK proof. Verified against pinned issuer trust anchor with reference cutoff ${ref}. The holder is proven to be >=18 without disclosing date of birth or secret witness.`;
    } else {
      elements.verificationResultBanner.className = 'verification-result-banner error';
      elements.verificationBannerTitle.textContent = 'Proof Verification Failed';
      const detail = data.error || data.stdout || data.error?.detail || 'Cryptographic verification check failed.';
      elements.verificationBannerDesc.textContent = `Verification rejected: ${detail}`;
    }
  } catch (err) {
    console.error('Verification network error:', err);
    elements.verificationResultBanner.classList.remove('hidden');
    elements.verificationResultBanner.className = 'verification-result-banner error';
    elements.verificationBannerTitle.textContent = 'Verification Network Error';
    elements.verificationBannerDesc.textContent = `Could not reach verification endpoint: ${err.message}`;
  } finally {
    state.isVerifyingProof = false;
    elements.btnVerifyProof.disabled = false;
    elements.btnVerifyProofSpinner.classList.add('hidden');
    elements.btnVerifyProofText.textContent = 'Verify Proof';
  }
}

function downloadProofJson() {
  if (!state.generatedProof) return;
  const jsonStr = JSON.stringify(state.generatedProof, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `zkkyc-proof-${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// --- Result Screen: Failure ---
function renderFailureScreen(errorObj, httpStatus) {
  showScreen('result');
  elements.resultSuccessContainer.classList.add('hidden');
  elements.resultFailureContainer.classList.remove('hidden');

  const code = errorObj.code || `HTTP_${httpStatus || 'UNKNOWN'}`;
  elements.errCodeBadge.textContent = code;
  elements.errDetailsDump.textContent = JSON.stringify(errorObj, null, 2);

  let guidance = '';
  if (code === 'MEDIA_UNREADABLE') {
    guidance = `Recording format not supported by backend: The video recorded in format "${state.recordedMimeType || 'unknown'}" could not be decoded by the server's OpenCV/ffmpeg pipeline. (Details: ${errorObj.detail || 'media unreadable'}). Try using Chrome/Firefox with MP4 or VP8 support.`;
  } else if (code === 'AUDIO_UNREADABLE') {
    guidance = `Audio track unreadable: The server's ffmpeg could not extract audio from the video recorded in format "${state.recordedMimeType || 'unknown'}". Ensure your microphone is connected and audible during recording.`;
  } else if (code === 'PASSIVE_LIVENESS_FAILED') {
    guidance = 'Passive anti-spoofing check failed. Ensure good frontal lighting, no reflections or glare from computer monitors, and do not present a printed photo or replay on a screen.';
  } else if (code === 'ACTIVE_LIVENESS_FAILED') {
    guidance = `Dynamic challenge verification failed (reason: ${errorObj.reason || 'challenge not matched'}). Make sure you follow the prompt continuously (e.g. turn head to correct direction or speak the exact numbers).`;
  } else if (code === 'DOCUMENT_PRESENCE_FAILED') {
    guidance = `Physical document presence check failed: ${errorObj.detail || 'no text detected'}. Please hold your physical ID card closer to the camera and steady with good lighting during Clip 2.`;
  } else if (code === 'DOB_EXTRACTION_FAILED') {
    guidance = `OCR Date of Birth extraction failed (${errorObj.detail || 'DOB not detected'}). Ensure your ID photo has clean, unblurred, glare-free birthdate text.`;
  } else if (code === 'TOO_FEW_FRAMES') {
    guidance = `Video was too short (minimum ${errorObj.min_required || 30} frames required). Please record for at least 4-8 seconds.`;
  } else if (code === 'SESSION_EXPIRED') {
    guidance = 'This verification session timed out. Sessions are valid for 5 minutes and are single-use.';
  } else if (code === 'SIGNER_UNAVAILABLE') {
    guidance = 'The issuer EdDSA signer server is offline or unreachable on localhost:7391. Start node issuer-service/signer/server.js.';
  } else {
    guidance = `Verification was rejected with code ${code}. Please inspect the raw API diagnostics above and try again.`;
  }

  elements.errTroubleshootingText.textContent = guidance;
}

// --- Navigation & Cleanup ---
function showScreen(name) {
  elements.screenStart.classList.add('hidden');
  elements.screenCapture.classList.add('hidden');
  elements.screenResult.classList.add('hidden');

  if (name === 'start') elements.screenStart.classList.remove('hidden');
  if (name === 'capture') elements.screenCapture.classList.remove('hidden');
  if (name === 'result') elements.screenResult.classList.remove('hidden');
}

function resetToStartScreen() {
  stopMediaTracks();

  state.currentSession = null;
  state.idPhotoFile = null;
  state.livenessBlob = null;
  state.docBlob = null;
  state.recordedChunks = [];
  state.issuedCredential = null;
  state.generatedProof = null;

  // Reset UI components
  elements.submitIdleState.classList.remove('hidden');
  elements.submitPipelineState.classList.add('hidden');
  elements.idPreviewBox.classList.add('hidden');
  elements.idDropzone.classList.remove('hidden');
  elements.idStatusBadge.textContent = 'Required';
  elements.idStatusBadge.className = 'step-indicator-badge';
  elements.livenessStatusBadge.textContent = 'Clip 1: Face';
  elements.livenessStatusBadge.className = 'step-indicator-badge';
  elements.docStatusBadge.textContent = 'Clip 2: ID';
  elements.docStatusBadge.className = 'step-indicator-badge';

  elements.btnPlayPreviewLiveness.classList.add('hidden');
  elements.btnPlayPreviewDoc.classList.add('hidden');
  elements.btnStopRecord.classList.add('hidden');
  switchActiveClipTab('liveness');

  elements.recProgressBar.style.width = '0%';
  elements.btnSubmit.disabled = true;

  // Reset pipeline icons
  [elements.pipeUpload, elements.pipePassive, elements.pipeActive, elements.pipeOcr, elements.pipeDoc, elements.pipeSign].forEach((p, idx) => {
    p.className = 'pipeline-step';
    p.querySelector('.pipeline-step-icon').textContent = String(idx + 1);
  });

  showScreen('start');
  fetchHealth();
}

function stopMediaTracks() {
  stopAudioVisualizer();

  if (state.sessionTimerInterval) {
    clearInterval(state.sessionTimerInterval);
    state.sessionTimerInterval = null;
  }
  if (state.recordingTimerInterval) {
    clearInterval(state.recordingTimerInterval);
    state.recordingTimerInterval = null;
  }
  if (state.webcamStream) {
    state.webcamStream.getTracks().forEach((track) => track.stop());
    state.webcamStream = null;
  }
  if (elements.webcamVideo) {
    elements.webcamVideo.srcObject = null;
    elements.webcamVideo.src = '';
  }
}
