const $ = (id) => document.getElementById(id);
let sessionId = crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
let latestSources = [];
let requestInProgress = false;
let captureLocked = false;
let mediaRecorder = null;
let mediaStream = null;
let recordingChunks = [];
let recordingStartedAt = 0;
let recordingTimerId = null;
let recordedWavFile = null;
let recordingPreviewUrl = null;
let maxDurationReached = false;
const MAX_AUDIO_BYTES = 10 * 1024 * 1024;
const MAX_RECORDING_MS = 55_000;

function toast(message) {
  const el = $('toast'); el.textContent = message; el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3600);
}
function setVoiceStatus(message, kind = '') {
  const el = $('voiceStatus'); el.textContent = message; el.className = `voice-status ${kind}`.trim();
}
function releaseMediaStream() {
  if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop());
  mediaStream = null;
}
function formatDuration(ms) {
  const sec = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;
}
function syncControls() {
  const recording = !!mediaRecorder && mediaRecorder.state === 'recording';
  $('sendButton').disabled = requestInProgress || captureLocked;
  $('messageInput').disabled = requestInProgress || captureLocked;
  $('resetButton').disabled = requestInProgress || captureLocked;
  $('audioInput').disabled = requestInProgress || captureLocked;
  $('uploadAudioLabel').classList.toggle('is-disabled', requestInProgress || captureLocked);
  $('uploadAudioLabel').setAttribute('aria-disabled', String(requestInProgress || captureLocked));
  $('recordButton').disabled = requestInProgress || captureLocked;
  $('stopButton').disabled = requestInProgress || !recording;
  $('sendRecordingButton').disabled = requestInProgress || !recordedWavFile;
  $('discardRecordingButton').disabled = requestInProgress || !recordedWavFile;
}
function addMessage(text, role = 'assistant', meta = '') {
  const wrap = document.createElement('div'); wrap.className = `message ${role}`;
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
  const foot = document.createElement('div'); foot.className = 'msg-meta';
  foot.textContent = meta || (role === 'assistant' ? 'AI assistant' : 'You');
  wrap.append(bubble, foot); $('messages').appendChild(wrap);
  $('messages').scrollTop = $('messages').scrollHeight; return wrap;
}
function addAudioPlayer(audioUrl, label = 'Spoken reply') {
  const wrap = document.createElement('div'); wrap.className = 'message assistant';
  const bubble = document.createElement('div'); bubble.className = 'bubble';
  bubble.append(document.createTextNode(`${label} `));
  const player = document.createElement('audio'); player.controls = true;
  player.preload = 'metadata'; player.src = audioUrl; player.className = 'voice-player';
  player.setAttribute('aria-label', label);
  player.addEventListener('error', () => toast('The spoken audio could not be played. Try the request again.'), { once: true });
  bubble.appendChild(player); const meta = document.createElement('div');
  meta.className = 'msg-meta'; meta.textContent = 'Gnani.ai synthesized audio';
  wrap.append(bubble, meta); $('messages').appendChild(wrap);
  $('messages').scrollTop = $('messages').scrollHeight;
}
function showSources(sources = []) {
  const root = $('sources'); root.replaceChildren(); latestSources = sources;
  if (!sources.length) { root.className = 'sources-empty'; root.textContent = 'No document sources were returned for the latest response.'; return; }
  root.className = 'source-list';
  sources.forEach((s) => {
    const card = document.createElement('div'); card.className = 'source-card';
    const title = document.createElement('strong'); title.textContent = s.source || 'Knowledge base';
    const detail = document.createElement('div');
    detail.textContent = `Section: ${s.section_id || 'n/a'} · Effective: ${s.effective_from || 'n/a'} · Score: ${s.score ?? 'n/a'}`;
    const tag = document.createElement('span'); tag.className = 'source-type'; tag.textContent = s.doc_type || 'document';
    card.append(title, detail, tag); root.appendChild(card);
  });
}
async function statusCheck() {
  const box = $('configNotice');
  try {
    const r = await fetch('/health'); const d = await r.json();
    const missing = []; if (!d.dataset_configured) missing.push('dataset/index');
    if (!d.llm_configured) missing.push('LLM API'); if (!d.gnani_configured) missing.push('Gnani API');
    if (missing.length) { box.textContent = `Setup needed: ${missing.join(', ')}. Text answers and/or live voice may be unavailable until configured. See README.md.`; }
    else { box.className = 'notice ready'; box.textContent = 'Services configured. Answers are grounded in the supplied documents; order information requires verification.'; }
  } catch { box.textContent = 'Could not check service configuration. Make sure the backend is running.'; }
}
function releaseRecordingDraft() {
  recordedWavFile = null;
  if (recordingPreviewUrl) URL.revokeObjectURL(recordingPreviewUrl);
  recordingPreviewUrl = null; $('recordingPreview').removeAttribute('src');
  $('recordingPreview').hidden = true; $('recordingTimer').textContent = '00:00';
  $('recordingIndicator').closest('.voice-capture').classList.remove('is-recording');
  captureLocked = false; syncControls();
}
function encodeWavMono16(audioBuffer) {
  const channels = audioBuffer.numberOfChannels;
  const length = audioBuffer.length;
  const sampleRate = audioBuffer.sampleRate;
  const mono = new Float32Array(length);
  for (let ch = 0; ch < channels; ch += 1) {
    const samples = audioBuffer.getChannelData(ch);
    for (let i = 0; i < length; i += 1) mono[i] += samples[i] / channels;
  }
  const dataSize = length * 2;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);
  const ascii = (offset, value) => { for (let i = 0; i < value.length; i += 1) view.setUint8(offset + i, value.charCodeAt(i)); };
  ascii(0, 'RIFF'); view.setUint32(4, 36 + dataSize, true); ascii(8, 'WAVE');
  ascii(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); ascii(36, 'data'); view.setUint32(40, dataSize, true);
  let offset = 44;
  for (let i = 0; i < length; i += 1) {
    const clipped = Math.max(-1, Math.min(1, mono[i]));
    view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}
async function recordingBlobToWav(blob) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error('This browser cannot decode its recording format. Use Upload audio with a WAV, MP3, FLAC, M4A or OGG file.');
  const audioContext = new AudioContextClass();
  try {
    const bytes = await blob.arrayBuffer();
    const decoded = await audioContext.decodeAudioData(bytes.slice(0));
    if (!decoded.length || !Number.isFinite(decoded.duration) || decoded.duration <= 0) throw new Error('No usable speech audio was found. Please record again.');
    if (decoded.duration > 60) throw new Error('Recording exceeds Gnani STT’s 60-second input limit. Please record a shorter clip.');
    return encodeWavMono16(decoded);
  } finally {
    if (audioContext.state !== 'closed') await audioContext.close().catch(() => {});
  }
}
async function processVoiceFile(file, origin = 'uploaded') {
  if (requestInProgress) return false;
  if (!file || !file.size) { setVoiceStatus('The audio is empty. Record or choose another audio file.', 'error'); return false; }
  if (file.size > MAX_AUDIO_BYTES) { setVoiceStatus('Audio must be 10 MB or smaller. Record a shorter clip or choose another file.', 'error'); toast('Audio file is too large.'); return false; }
  requestInProgress = true; syncControls();
  addMessage(origin === 'recorded' ? 'Browser microphone recording submitted.' : `Voice message uploaded: ${file.name}`, 'user');
  const loading = addMessage('Sending audio to Gnani STT, running the support agent, and preparing Gnani TTS…', 'assistant', 'Voice processing');
  loading.querySelector('.bubble').classList.add('loading');
  let succeeded = false;
  const form = new FormData(); form.append('audio', file, file.name || 'recording.wav'); form.append('session_id', sessionId);
  try {
    const r = await fetch('/api/voice', { method: 'POST', body: form });
    const d = await r.json(); loading.remove();
    if (!r.ok) {
      const detail = d.detail || {};
      if (typeof detail === 'object' && detail.transcription) addMessage(`Transcription: ${detail.transcription}`, 'assistant', 'Gnani STT');
      if (typeof detail === 'object' && detail.response) addMessage(detail.response, 'assistant', 'Agent response (speech incomplete)');
      const errorText = typeof detail === 'string' ? detail : (detail.message || 'Voice processing failed. Check Gnani and LLM configuration.');
      addMessage(errorText, 'assistant', 'Voice error'); setVoiceStatus(errorText, 'error'); toast('Voice processing failed.');
    } else {
      const transcript = (d.transcription || '').trim();
      if (transcript) addMessage(`Transcription: ${transcript}`, 'assistant', 'Gnani STT');
      else addMessage('I could not detect clear speech in that recording. Please record the question again.', 'assistant', 'Gnani STT · no clear speech');
      addMessage(d.response, 'assistant', 'AI response · Gnani TTS');
      if (!d.audio_url) { setVoiceStatus('The text response was returned, but no playable speech file was provided.', 'error'); }
      else {
        addAudioPlayer(d.audio_url);
        setVoiceStatus(transcript ? 'Voice response completed. You can replay the spoken reply above.' : 'No clear speech was detected. The assistant asks you to try again; record a fresh clip.', transcript ? 'success' : 'error');
        succeeded = true;
      }
      showSources(d.sources || []);
    }
  } catch {
    loading.remove(); const msg = 'Could not reach voice processing. Check the backend connection and retry.';
    addMessage(msg, 'assistant', 'Connection error'); setVoiceStatus(msg, 'error'); toast('Unable to reach voice processing.');
  } finally {
    requestInProgress = false;
    if (origin === 'recorded' && succeeded) releaseRecordingDraft();
    else syncControls();
    if (origin === 'uploaded') $('audioInput').value = '';
  }
  return succeeded;
}
async function startRecording() {
  if (requestInProgress || captureLocked) return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setVoiceStatus('This browser does not support microphone recording. Use Upload audio instead.', 'error');
    toast('Microphone recording is not supported in this browser.'); return;
  }
  captureLocked = true; syncControls(); setVoiceStatus('Requesting microphone permission…');
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const candidates = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'];
    const supportedType = candidates.find((type) => MediaRecorder.isTypeSupported?.(type));
    mediaRecorder = supportedType ? new MediaRecorder(mediaStream, { mimeType: supportedType }) : new MediaRecorder(mediaStream);
    recordingChunks = []; maxDurationReached = false; recordingStartedAt = Date.now();
    $('recordingTimer').textContent = '00:00'; $('recordingIndicator').closest('.voice-capture').classList.add('is-recording');
    mediaRecorder.addEventListener('dataavailable', (event) => { if (event.data && event.data.size) recordingChunks.push(event.data); });
    mediaRecorder.addEventListener('error', () => {
      clearInterval(recordingTimerId); recordingTimerId = null; releaseMediaStream();
      setVoiceStatus('The browser could not record audio. Try again or use Upload audio.', 'error');
      $('recordingIndicator').closest('.voice-capture').classList.remove('is-recording');
      mediaRecorder = null; captureLocked = false; syncControls();
    }, { once: true });
    mediaRecorder.addEventListener('stop', async () => {
      clearInterval(recordingTimerId); recordingTimerId = null; releaseMediaStream();
      $('recordingIndicator').closest('.voice-capture').classList.remove('is-recording');
      const rawBlob = new Blob(recordingChunks, { type: mediaRecorder?.mimeType || recordingChunks[0]?.type || 'application/octet-stream' });
      recordingChunks = []; mediaRecorder = null;
      if (!rawBlob.size) {
        setVoiceStatus('No audio was captured. Please try recording again.', 'error'); captureLocked = false; syncControls(); return;
      }
      if (rawBlob.size > MAX_AUDIO_BYTES) {
        setVoiceStatus('The recording is too large. Please make a shorter recording.', 'error'); captureLocked = false; syncControls(); return;
      }
      setVoiceStatus('Preparing your recording as WAV for Gnani STT…'); syncControls();
      try {
        const wavBlob = await recordingBlobToWav(rawBlob);
        if (wavBlob.size > MAX_AUDIO_BYTES) throw new Error('The converted WAV is over 10 MB. Please record a shorter clip.');
        recordedWavFile = new File([wavBlob], `voice_recording_${Date.now()}.wav`, { type: 'audio/wav', lastModified: Date.now() });
        if (recordingPreviewUrl) URL.revokeObjectURL(recordingPreviewUrl);
        recordingPreviewUrl = URL.createObjectURL(recordedWavFile);
        const preview = $('recordingPreview'); preview.src = recordingPreviewUrl; preview.hidden = false;
        setVoiceStatus(maxDurationReached ? 'Maximum recording time reached. Review the clip, then send it.' : 'Recording ready. Review your audio, then send it to the support agent.', 'success');
      } catch (error) {
        setVoiceStatus(error.message || 'Could not prepare the recording. Try again or use Upload audio.', 'error');
        toast('Could not prepare browser audio.'); captureLocked = false;
      }
      syncControls();
    }, { once: true });
    mediaRecorder.start(250);
    setVoiceStatus('Recording… Speak now. Stop when you have finished.');
    recordingTimerId = setInterval(() => {
      const elapsed = Date.now() - recordingStartedAt;
      $('recordingTimer').textContent = formatDuration(elapsed);
      if (elapsed >= MAX_RECORDING_MS && mediaRecorder?.state === 'recording') {
        maxDurationReached = true; setVoiceStatus('55-second limit reached. Finishing the recording…'); stopRecording();
      }
    }, 250);
    syncControls();
  } catch (error) {
    releaseMediaStream(); mediaRecorder = null; captureLocked = false; syncControls();
    let message = 'Microphone access failed. Allow microphone permission in your browser, or use Upload audio.';
    if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') message = 'Microphone permission was denied. Allow microphone access for this site, then try again.';
    else if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') message = 'No microphone was found. Connect a microphone or use Upload audio.';
    else if (error?.name === 'NotReadableError') message = 'The microphone is busy or unavailable. Close other apps using it and try again.';
    setVoiceStatus(message, 'error'); toast(message);
  }
}
function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    try { mediaRecorder.stop(); setVoiceStatus('Recording stopped. Preparing preview…'); }
    catch { releaseMediaStream(); mediaRecorder = null; captureLocked = false; syncControls(); setVoiceStatus('Could not stop the recording cleanly. Please try again.', 'error'); }
  }
}
$('chatForm').addEventListener('submit', async (event) => {
  event.preventDefault(); if (requestInProgress || captureLocked) return;
  const message = $('messageInput').value.trim(); if (!message) return;
  addMessage(message, 'user'); $('messageInput').value = ''; requestInProgress = true; syncControls();
  const loading = addMessage('Checking relevant documents and preparing a response…', 'assistant', 'Working'); loading.querySelector('.bubble').classList.add('loading');
  try {
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, session_id: sessionId }) });
    const d = await r.json(); loading.remove();
    if (!r.ok) { const detail = d.detail || {}; addMessage(detail.message || detail || 'The service is unavailable. Check configuration and try again.', 'assistant', 'Service unavailable'); showSources(detail.sources || []); toast('Request could not be completed.'); }
    else { addMessage(d.response, 'assistant', `Decision: ${d.decision || 'answer'}`); showSources(d.sources || []); if (d.tool_calls?.length) toast('Support workflow action recorded.'); }
  } catch { loading.remove(); addMessage('I could not reach the support service. Check that the backend is running, then retry.', 'assistant', 'Connection error'); toast('Unable to reach the backend.'); }
  finally { requestInProgress = false; syncControls(); $('messageInput').focus(); }
});
$('audioInput').addEventListener('change', async (event) => {
  const input = event.target; const file = input.files[0]; if (!file) return;
  try { await processVoiceFile(file, 'uploaded'); }
  finally { input.value = ''; }
});
$('recordButton').addEventListener('click', startRecording);
$('stopButton').addEventListener('click', stopRecording);
$('sendRecordingButton').addEventListener('click', () => { if (recordedWavFile) processVoiceFile(recordedWavFile, 'recorded'); });
$('discardRecordingButton').addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state === 'recording') stopRecording();
  releaseRecordingDraft(); setVoiceStatus('Recording discarded. Ready for a new recording.'); toast('Recording discarded.');
});
$('resetButton').addEventListener('click', async () => {
  if (requestInProgress || captureLocked) return;
  try { await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId }) }); } catch {}
  sessionId = crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
  $('messages').replaceChildren(); addMessage('New conversation started. I’m ZentroMart’s AI support assistant. What can I help you with?');
  showSources([]); toast('Conversation reset.');
});
window.addEventListener('beforeunload', () => { clearInterval(recordingTimerId); releaseMediaStream(); if (recordingPreviewUrl) URL.revokeObjectURL(recordingPreviewUrl); });

function enterSupport(mode = 'chat') {
  const landing = $('landingPage');
  const app = $('supportApp');
  if (landing) landing.hidden = true;
  if (app) app.hidden = false;
  try { history.replaceState(null, '', mode === 'voice' ? '#voice-support' : '#support'); } catch {}
  if (mode === 'voice') {
    $('voiceCaptureTitle')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => $('recordButton')?.focus({ preventScroll: true }), 250);
  } else {
    $('messageInput')?.focus({ preventScroll: true });
  }
}
$('startVoiceButton')?.addEventListener('click', () => enterSupport('voice'));
$('startChatButton')?.addEventListener('click', () => enterSupport('chat'));
$('landingChatLink')?.addEventListener('click', () => enterSupport('chat'));
$('footerStartButton')?.addEventListener('click', () => enterSupport('chat'));
if (window.location.hash === '#support' || window.location.hash === '#voice-support') {
  enterSupport(window.location.hash === '#voice-support' ? 'voice' : 'chat');
}

syncControls(); statusCheck();
