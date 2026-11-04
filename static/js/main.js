
const state = {
    sessionId: 'sess_' + Math.random().toString(36).slice(2, 11),
    orderData: null,
    riskData: null,
    currentOrderId: null,
    grievance: null,
    awaitingEvidence: false,
    awaitingUnboxingVideo: false,
    reportUrl: null
};

const AI_MEDIA_THRESHOLD = 0.60;

const $ = id => document.getElementById(id);
const messages = $('messagesContainer');


/* =========================================================
   HELPERS
   ========================================================= */

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s ?? '';
    return d.innerHTML;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function markdown(s) {
    return esc(s)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function addMessage(text, sender = 'bot') {
    const wrapper = document.createElement('div');
    wrapper.className = `msg-wrapper ${sender}-msg`;

    if (sender === 'bot') {
        wrapper.innerHTML = `
            <div class="msg-avatar-sm">🤖</div>
            <div>
                <div class="msg-bubble bot-bubble">
                    <p>${markdown(text)}</p>
                </div>
                <div class="msg-time">
                    ${new Date().toLocaleTimeString('en-IN', {
                        hour: '2-digit',
                        minute: '2-digit'
                    })}
                </div>
            </div>
        `;
    } else {
        wrapper.innerHTML = `
            <div>
                <div class="msg-bubble user-bubble">${esc(text)}</div>
            </div>
            <div class="msg-avatar-sm">👤</div>
        `;
    }

    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
}


/* =========================================================
   EVIDENCE PREVIEW
   ========================================================= */

function addEvidencePreview(file) {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper user-msg';

    const url = URL.createObjectURL(file);

    let mediaHtml = '';

    if (file.type.startsWith('image/')) {
        mediaHtml = `
            <img
                src="${url}"
                alt="Captured evidence"
                style="
                    width:180px;
                    max-height:180px;
                    object-fit:cover;
                    border-radius:10px;
                    margin-top:8px;
                    display:block;
                "
            >
        `;
    } else if (file.type.startsWith('video/')) {
        mediaHtml = `
            <video
                src="${url}"
                controls
                style="
                    width:220px;
                    max-height:180px;
                    border-radius:10px;
                    margin-top:8px;
                    display:block;
                "
            ></video>
        `;
    }

    wrapper.innerHTML = `
        <div>
            <div class="image-preview-bubble" style="padding:8px">
                <div style="font-size:13px">
                    📎 <b>${esc(file.name || 'Captured evidence')}</b>
                </div>

                <div style="
                    font-size:11px;
                    color:var(--text-muted);
                    margin-top:4px
                ">
                    ${file.type.startsWith('video/')
                        ? 'Unboxing video'
                        : 'Product photo'}
                </div>

                ${mediaHtml}
            </div>
        </div>

        <div class="msg-avatar-sm">👤</div>
    `;

    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
}


/* =========================================================
   TYPING INDICATOR
   ========================================================= */

function typing(show) {
    const indicator = $('typingIndicator');

    if (!indicator) return;

    indicator.classList.toggle('visible', show);

    if (show) {
        messages.appendChild(indicator);
        messages.scrollTop = messages.scrollHeight;
    }
}


/* =========================================================
   UPLOAD VISIBILITY
   ========================================================= */

function showUploadControls() {
    state.awaitingEvidence = true;

    $('uploadZoneWrapper')?.classList.add('visible');
}

function hideUploadControls() {
    state.awaitingEvidence = false;

    $('uploadZoneWrapper')?.classList.remove('visible');
}


/* =========================================================
   CHAT
   ========================================================= */

async function chat(text) {
    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: text,
            session_id: state.sessionId
        })
    });

    return response.json();
}


async function send(text) {
    if (!text.trim()) return;

    addMessage(text, 'user');

    $('messageInput').value = '';
    $('messageInput').disabled = true;
    $('btnSend').disabled = true;

    typing(true);

    await sleep(450);

    let data;

    try {
        data = await chat(text);
    } catch (error) {
        data = {
            reply:
                'I could not connect to the verification service. Please try again.'
        };
    }

    typing(false);

    addMessage(
        data.reply || 'How can I help you?',
        'bot'
    );

    if (data.order_data) {
        state.orderData = data.order_data;
        state.riskData = data.order_data.risk;
        state.currentOrderId = data.order_data.order_id;
        state.grievance = data.grievance;

        renderOrder(
            data.order_data,
            data.order_data.risk
        );
    }

    if (data.grievance) {
        state.grievance = data.grievance;
    }

    if (
        data.show_upload ||
        data.action === 'request_evidence'
    ) {
        state.awaitingUnboxingVideo = false;
        showUploadControls();
    }

    $('messageInput').disabled = false;
    $('btnSend').disabled = false;
    $('messageInput').focus();
}


/* =========================================================
   ORDER CARD
   ========================================================= */

function renderOrder(order, risk) {
    $('orderCard').classList.add('visible');

    $('orderCardBody').innerHTML = `
        <div class="order-product-name">
            ${esc(order.product)}
        </div>

        <div class="order-meta-row">
            <span class="order-meta-label">Order ID</span>
            <span class="order-meta-value">
                ${esc(order.order_id)}
            </span>
        </div>

        <div class="order-meta-row">
            <span class="order-meta-label">Model</span>
            <span class="order-meta-value">
                ${esc(order.model || 'N/A')}
            </span>
        </div>

        <div class="order-meta-row">
            <span class="order-meta-label">Colour</span>
            <span class="order-meta-value">
                ${esc(order.color || 'N/A')}
            </span>
        </div>

        <div class="order-meta-row">
            <span class="order-meta-label">Size</span>
            <span class="order-meta-value">
                ${esc(order.size || 'N/A')}
            </span>
        </div>

        <div class="order-meta-row">
            <span class="order-meta-label">Amount</span>
            <span class="order-meta-value price">
                ₹${Number(order.price).toLocaleString('en-IN')}
            </span>
        </div>

        <div class="order-meta-row">
            <span class="order-meta-label">Status</span>
            <span class="order-meta-value">
                ${esc(order.status)}
            </span>
        </div>
    `;

    $('riskCard').classList.add('visible');

    $('riskCardBody').innerHTML = `
        <div class="risk-score-display">
            <div class="risk-gauge medium">
                ${Number(risk?.score ?? 0).toFixed(1)}
            </div>

            <div class="risk-info">
                <div class="risk-level medium">
                    ${esc(risk?.level || 'Normal')} context
                </div>

                <div class="risk-label">
                    Returns: ${risk?.past_returns || 0}
                    · Flags: ${risk?.fraud_flags || 0}
                </div>
            </div>
        </div>
    `;
}


/* =========================================================
   VERIFICATION PIPELINE
   ========================================================= */

function resetPipeline() {
    ['Cnn', 'Ae', 'Fuzzy'].forEach(step => {
        const element = $(`step${step}`);
        const status = $(`step${step}Status`);

        if (element) {
            element.classList.remove('active', 'done');
        }

        if (status) {
            status.textContent = 'Waiting…';
        }
    });

    ['connector1', 'connector2'].forEach(id => {
        $(id)?.classList.remove('active');
    });
}


async function pipeline(file) {
    $('analysisOverlay').classList.add('active');

    resetPipeline();

    $('stepCnn').classList.add('active');
    $('stepCnnStatus').textContent = 'Checking quality…';

    const verificationPromise = verify(file);

    await sleep(650);

    $('stepCnn').classList.replace('active', 'done');
    $('stepCnnStatus').textContent = '✓ Checked';

    $('connector1').classList.add('active');

    $('stepAe').classList.add('active');
    $('stepAeStatus').textContent = 'Matching evidence…';

    await sleep(700);

    $('stepAe').classList.replace('active', 'done');
    $('stepAeStatus').textContent = '✓ Compared';

    $('connector2').classList.add('active');

    $('stepFuzzy').classList.add('active');
    $('stepFuzzyStatus').textContent = 'Making safe decision…';

    let result;

    try {
        result = await verificationPromise;
    } catch (error) {
        result = {
            success: false,
            error: 'Evidence could not be analyzed.'
        };
    }

    await sleep(500);

    $('stepFuzzy').classList.replace('active', 'done');
    $('stepFuzzyStatus').textContent = '✓ Complete';

    await sleep(350);

    $('analysisOverlay').classList.remove('active');

    if (result.success) {
        showResult(result);
    } else {
        addMessage(
            '⚠️ ' + (result.error || 'Evidence could not be analyzed.'),
            'bot'
        );

        toast(
            result.error || 'Analysis failed',
            'error'
        );

        // Allow another upload if verification failed.
        showUploadControls();
    }
}


/* =========================================================
   SEND IMAGE / VIDEO TO BACKEND
   ========================================================= */

async function verify(file) {
    const formData = new FormData();

    formData.append('evidence', file);
    formData.append('session_id', state.sessionId);
    formData.append(
        'order_id',
        state.currentOrderId || ''
    );
    formData.append(
        'grievance',
        state.grievance || 'damage'
    );

    try {
        const response = await fetch('/api/verify', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            return {
                success: false,
                error: result.error || 'Verification request failed.'
            };
        }

        // Preserve the report URL for the result card.
        if (result.report_url) {
            state.reportUrl = result.report_url;
        }

        return result;

    } catch (error) {
        console.error('Verification error:', error);

        return {
            success: false,
            error: 'The verification service is unavailable.'
        };
    }
}


/* =========================================================
   SCORE BAR
   ========================================================= */

function score(id, value, pct) {
    const valueElement = $(`${id}Val`);
    const barElement = $(`${id}Bar`);

    if (!valueElement || !barElement) return;

    valueElement.textContent = value;

    barElement.style.width =
        Math.max(0, Math.min(100, pct)) + '%';
}


/* =========================================================
   AI MEDIA RESULT
   ========================================================= */

function getAiMediaData(analysis) {
    return analysis?.ai_media || {};
}


function getAiProbability(aiMedia) {
    let probability = Number(aiMedia?.ai_probability);

    if (!Number.isFinite(probability)) {
        probability = 0;
    }

    // Support detector results represented as percentages.
    if (probability > 1) {
        probability = probability / 100;
    }

    return Math.max(0, Math.min(1, probability));
}


function renderAiMedia(aiMedia) {
    if (!aiMedia || typeof aiMedia !== 'object' ||
        Object.keys(aiMedia).length === 0) {

        return `
            <div style="
                margin-top:10px;
                padding:10px;
                border-radius:10px;
                background:rgba(255,255,255,0.04);
            ">
                <b>🤖 AI-generated media check:</b>
                Not available
            </div>
        `;
    }

    const aiProbability = getAiProbability(aiMedia);

    let realProbability = Number(aiMedia.real_probability);

    if (!Number.isFinite(realProbability)) {
        realProbability = 1 - aiProbability;
    }

    if (realProbability > 1) {
        realProbability = realProbability / 100;
    }

    const confidence = Number(aiMedia.confidence || 0);

    let icon = '🟢';
    let text = 'Likely Real';

    if (
        aiMedia.status === 'suspicious' ||
        aiProbability >= AI_MEDIA_THRESHOLD
    ) {
        icon = '🔴';
        text = 'AI-generated media suspected';
    } else if (aiMedia.status === 'uncertain') {
        icon = '🟡';
        text = 'Uncertain';
    }

    return `
        <div style="
            margin-top:12px;
            padding:12px;
            border-radius:12px;
            background:rgba(255,255,255,0.04);
            border:1px solid rgba(255,255,255,0.08);
        ">

            <div style="
                font-size:13px;
                font-weight:700;
                margin-bottom:8px;
            ">
                🤖 AI-Generated Media Detection
            </div>

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                margin-bottom:6px;
            ">
                <span>${icon} ${text}</span>
                <b>${(confidence * 100).toFixed(1)}% confidence</b>
            </div>

            <div style="
                font-size:11px;
                color:var(--text-muted);
                line-height:1.8;
            ">
                AI probability:
                ${(aiProbability * 100).toFixed(2)}%

                <br>

                Real probability:
                ${(realProbability * 100).toFixed(2)}%

                <br>

                AI detection threshold:
                60%
            </div>

            <div style="
                height:7px;
                background:rgba(255,255,255,.10);
                border-radius:10px;
                overflow:hidden;
                margin-top:9px;
            ">
                <div style="
                    height:100%;
                    width:${aiProbability * 100}%;
                    background:${aiProbability >= AI_MEDIA_THRESHOLD
                        ? '#ef4444'
                        : '#22c55e'};
                    border-radius:10px;
                "></div>
            </div>

            ${
                aiMedia.model
                    ? `
                        <div style="
                            margin-top:7px;
                            font-size:10px;
                            color:var(--text-muted);
                        ">
                            Model: ${esc(aiMedia.model)}
                        </div>
                    `
                    : ''
            }

        </div>
    `;
}


/* =========================================================
   REPORT DOWNLOAD
   ========================================================= */

function renderReportLink(reportUrl) {
    if (!reportUrl) return '';

    return `
        <div style="
            margin-top:15px;
            text-align:center;
        ">
            <a
                class="btn-primary"
                href="${esc(reportUrl)}"
                target="_blank"
                rel="noopener"
                style="
                    display:inline-flex;
                    align-items:center;
                    justify-content:center;
                    text-decoration:none;
                "
            >
                📄 Download Verification Report
            </a>
        </div>
    `;
}


/* =========================================================
   RESULT CARD
   ========================================================= */

function showResult(data) {
    const analysis = data.analysis || {};
    const aiMedia = getAiMediaData(analysis);

    const aiProbability = getAiProbability(aiMedia);

    const needsUnboxingVideo =
        data.final_decision === 'additional_evidence_required' ||
        data.requires_unboxing_video === true ||
        data.additional_evidence_required === true;

    const map = {
        approved: [
            '✅',
            'Return Verified',
            'verified'
        ],

        human_review: [
            '🟡',
            'Human Verification Required',
            'review'
        ],

        reupload_required: [
            '📸',
            'Clearer Evidence Required',
            'reupload'
        ],

        not_verified: [
            '❌',
            'No Sufficient Issue Identified',
            'notverified'
        ],

        additional_evidence_required: [
            '🎥',
            'Unboxing Video Required',
            'review'
        ]
    };

    const [
        icon,
        title,
        cssClass
    ] = map[data.final_decision] || map.human_review;


    /* ---------------------------------------------------------
       UPDATE SCORES
       --------------------------------------------------------- */

    score(
        'scoreCnn',
        ((analysis.product_confidence || 0) * 100).toFixed(1) + '%',
        (analysis.product_confidence || 0) * 100
    );

    score(
        'scoreAe',
        ((analysis.damage_confidence || 0) * 100).toFixed(1) + '%',
        (analysis.damage_confidence || 0) * 100
    );

    score(
        'scoreRisk',
        (data.risk?.score ?? 0).toFixed(1) + '/10',
        (data.risk?.score ?? 0) * 10
    );

    const fuzzyScore =
        data.final_decision === 'approved'
            ? 2
            : data.final_decision === 'human_review'
                ? 5
                : data.final_decision === 'reupload_required'
                    ? 4
                    : data.final_decision === 'additional_evidence_required'
                        ? 5
                        : 8;

    score(
        'scoreFuzzy',
        fuzzyScore.toFixed(1) + '/10',
        fuzzyScore * 10
    );


    /* ---------------------------------------------------------
       EVIDENCE FLAGS
       --------------------------------------------------------- */

    $('flagsBody').innerHTML = `
        <div style="
            display:flex;
            flex-direction:column;
            gap:8px;
            font-size:12px;
        ">

            <div>
                <b>Evidence quality:</b>
                ${
                    analysis.quality?.is_blurry
                        ? '⚠️ Too blurry'
                        : '✅ Usable'
                }
            </div>

            <div>
                <b>Expected:</b>
                ${esc(analysis.expected_product || 'Unknown')}
            </div>

            <div>
                <b>Detected:</b>
                ${esc(analysis.detected_product || 'Unknown')}
                (
                    ${Math.round(
                        (analysis.product_confidence || 0) * 100
                    )}%
                )
            </div>

            <div>
                <b>Detected colour:</b>
                ${esc(analysis.detected_color || 'Unknown')}
            </div>

            <div>
                <b>Damage evidence:</b>
                ${
                    analysis.damage_detected
                        ? '⚠️ Detected'
                        : 'Not confirmed'
                }
                (
                    ${Math.round(
                        (analysis.damage_confidence || 0) * 100
                    )}%
                )
            </div>

            <div>
                <b>Package Order ID:</b>
                ${
                    analysis.package_order_match
                        ? '✅ Matched'
                        : 'Not verified / not readable'
                }
            </div>

            ${renderAiMedia(aiMedia)}

        </div>
    `;


    /* ---------------------------------------------------------
       MANAGEMENT CASE
       --------------------------------------------------------- */

    const caseLine = data.case
        ? `
            <div class="result-note">
                Case
                <b>${esc(data.case.case_id)}</b>
                was sent to the management queue.
            </div>
        `
        : '';


    /* ---------------------------------------------------------
       ADDITIONAL VIDEO REQUEST
       --------------------------------------------------------- */

    if (needsUnboxingVideo) {
        state.awaitingUnboxingVideo = true;

        addMessage(
            `⚠️ The submitted product photo has an AI probability of ${(aiProbability * 100).toFixed(1)}%, which meets the 60% threshold.

This does NOT mean your return is rejected.

Please submit an **unboxing video** so that the evidence can be checked further.`,
            'bot'
        );

        showUploadControls();

    } else {
        state.awaitingUnboxingVideo = false;
        hideUploadControls();
    }


    /* ---------------------------------------------------------
       RESULT CARD
       --------------------------------------------------------- */

    const explanation = needsUnboxingVideo
        ? 'Additional evidence is required. Your return has not been rejected.'
        : (analysis.reason || '');

    $('resultCard').innerHTML = `
        <div class="result-icon ${cssClass}">
            ${icon}
        </div>

        <div class="result-title">
            ${title}
        </div>

        <div class="result-subtitle">
            ${esc(explanation)}
        </div>

        <div class="result-tags">
            <span class="result-tag">
                ${esc(data.grievance || 'return')}
            </span>

            <span class="result-tag">
                ${esc(analysis.media_type || 'image')}
            </span>
        </div>

        <div class="result-metrics">
            <div>
                <span>Product match</span>
                <b>
                    ${Math.round(
                        (analysis.product_confidence || 0) * 100
                    )}%
                </b>
            </div>

            <div>
                <span>Damage confidence</span>
                <b>
                    ${Math.round(
                        (analysis.damage_confidence || 0) * 100
                    )}%
                </b>
            </div>

            <div>
                <span>Frames analyzed</span>
                <b>${analysis.frames_analyzed || 1}</b>
            </div>
        </div>

        ${renderAiMedia(aiMedia)}

        ${
            needsUnboxingVideo
                ? `
                    <div class="result-note" style="margin-top:12px">
                        🎥 Please upload or record an unboxing video
                        to continue verification.
                        <br>
                        <b>This is an additional evidence request, not a rejection.</b>
                    </div>
                `
                : ''
        }

        ${caseLine}

        ${renderReportLink(data.report_url || state.reportUrl)}

        <div class="result-actions">

            <button
                class="btn-primary"
                id="resultClose"
            >
                Close
            </button>

            <a
                class="btn-icon-secondary"
                href="/management"
                style="
                    text-decoration:none;
                    display:flex;
                    align-items:center;
                "
            >
                Management Queue
            </a>

        </div>
    `;

    $('resultCardWrapper').classList.add('active');


    /* ---------------------------------------------------------
       CHAT RESULT
       --------------------------------------------------------- */

    if (!needsUnboxingVideo) {
        let aiMessage = '';

        if (aiMedia && aiMedia.ai_probability !== undefined) {
            aiMessage =
                `\n🤖 AI-media probability: ${(aiProbability * 100).toFixed(1)}%.`;
        }

        if (data.final_decision === 'human_review') {
            addMessage(
                `🟡 **Human Verification Required**

${analysis.reason || 'The submitted evidence requires manual verification.'}

${data.case
                    ? 'A case has been sent to the management queue.'
                    : ''}${aiMessage}`,
                'bot'
            );
        } else {
            addMessage(
                `${icon} **${title}**

${analysis.reason || ''}${aiMessage}`,
                'bot'
            );
        }
    }
}


/* =========================================================
   CAMERA
   ========================================================= */

let cameraStream = null;
let cameraMode = null;


function stopCamera() {
    if (cameraStream) {
        cameraStream
            .getTracks()
            .forEach(track => track.stop());

        cameraStream = null;
    }

    cameraMode = null;
}


async function openCamera(mode) {
    if (!navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia) {

        toast(
            'Camera access is not supported by this browser.',
            'error'
        );

        return;
    }

    try {
        cameraMode = mode;

        cameraStream =
            await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: {
                        ideal: 'environment'
                    }
                },
                audio: mode === 'video'
            });

        showCameraModal(mode);

    } catch (error) {
        console.error('Camera error:', error);

        toast(
            'Camera permission was denied or the camera is unavailable.',
            'error'
        );

        stopCamera();
    }
}


/* =========================================================
   CAMERA MODAL
   ========================================================= */

function showCameraModal(mode) {
    const existing = document.getElementById('cameraModal');

    if (existing) {
        existing.remove();
    }

    const modal = document.createElement('div');
    modal.id = 'cameraModal';

    modal.style.cssText = `
        position:fixed;
        inset:0;
        z-index:99999;
        background:rgba(0,0,0,.88);
        display:flex;
        align-items:center;
        justify-content:center;
        padding:20px;
    `;

    const box = document.createElement('div');

    box.style.cssText = `
        width:min(700px,95vw);
        max-height:95vh;
        background:#111;
        border-radius:20px;
        padding:16px;
        box-sizing:border-box;
        box-shadow:0 20px 70px rgba(0,0,0,.5);
        display:flex;
        flex-direction:column;
        gap:12px;
    `;

    const title =
        mode === 'photo'
            ? '📷 Take Product Photo'
            : '🎥 Record Unboxing Video';

    box.innerHTML = `
        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            color:white;
            font-size:16px;
            font-weight:700;
        ">
            <span>${title}</span>

            <button
                id="cameraClose"
                type="button"
                style="
                    border:0;
                    background:rgba(255,255,255,.1);
                    color:white;
                    border-radius:10px;
                    padding:8px 12px;
                    cursor:pointer;
                    font-size:18px;
                "
            >
                ✕
            </button>
        </div>

        <video
            id="cameraPreview"
            autoplay
            playsinline
            muted
            style="
                width:100%;
                max-height:65vh;
                object-fit:contain;
                background:#000;
                border-radius:14px;
            "
        ></video>

        <canvas
            id="cameraCanvas"
            style="display:none"
        ></canvas>

        <div style="
            display:flex;
            justify-content:center;
            gap:10px;
            flex-wrap:wrap;
        ">
            ${
                mode === 'photo'
                    ? `
                        <button
                            id="cameraCapture"
                            type="button"
                            class="btn-primary"
                            style="padding:12px 22px;cursor:pointer"
                        >
                            📸 Capture Photo
                        </button>
                    `
                    : `
                        <button
                            id="cameraRecord"
                            type="button"
                            class="btn-primary"
                            style="padding:12px 22px;cursor:pointer"
                        >
                            🔴 Start Recording
                        </button>
                    `
            }
        </div>
    `;

    modal.appendChild(box);
    document.body.appendChild(modal);

    const video = document.getElementById('cameraPreview');
    video.srcObject = cameraStream;

    document.getElementById('cameraClose').onclick = () => {
        stopCamera();
        modal.remove();
    };

    if (mode === 'photo') {
        document.getElementById('cameraCapture').onclick =
            capturePhoto;
    } else {
        setupVideoRecording();
    }
}


/* =========================================================
   CAPTURE PHOTO
   ========================================================= */

function capturePhoto() {
    const video = document.getElementById('cameraPreview');
    const canvas = document.getElementById('cameraCanvas');

    if (!video.videoWidth) {
        toast('Camera is not ready yet.', 'warning');
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext('2d');

    context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );

    canvas.toBlob(
        blob => {
            if (!blob) {
                toast('Could not capture the photo.', 'error');
                return;
            }

            const file = new File(
                [blob],
                `vericart-camera-${Date.now()}.jpg`,
                { type: 'image/jpeg' }
            );

            const modal = document.getElementById('cameraModal');

            stopCamera();

            if (modal) {
                modal.remove();
            }

            handleFile(file);
        },
        'image/jpeg',
        0.92
    );
}


/* =========================================================
   RECORD VIDEO
   ========================================================= */

function setupVideoRecording() {
    const recordButton = document.getElementById('cameraRecord');

    if (!recordButton) return;

    let recorder = null;
    let chunks = [];
    let recording = false;

    recordButton.onclick = () => {
        if (!recording) {
            chunks = [];

            const mimeTypes = [
                'video/webm;codecs=vp9',
                'video/webm;codecs=vp8',
                'video/webm'
            ];

            const supportedType = mimeTypes.find(
                type => MediaRecorder.isTypeSupported(type)
            );

            try {
                recorder = new MediaRecorder(
                    cameraStream,
                    supportedType
                        ? { mimeType: supportedType }
                        : undefined
                );
            } catch (error) {
                console.error(error);

                toast(
                    'Video recording is not supported by this browser.',
                    'error'
                );

                return;
            }

            recorder.ondataavailable = event => {
                if (event.data && event.data.size > 0) {
                    chunks.push(event.data);
                }
            };

            recorder.onstop = () => {
                const mimeType = recorder.mimeType || 'video/webm';

                const blob = new Blob(
                    chunks,
                    { type: mimeType }
                );

                const extension =
                    mimeType.includes('mp4') ? 'mp4' : 'webm';

                const file = new File(
                    [blob],
                    `vericart-camera-${Date.now()}.${extension}`,
                    { type: mimeType }
                );

                const modal = document.getElementById('cameraModal');

                stopCamera();

                if (modal) {
                    modal.remove();
                }

                handleFile(file);
            };

            recorder.start();

            recording = true;

            recordButton.textContent = '⏹ Stop Recording';
            recordButton.style.background = '#dc2626';

        } else {
            recorder.stop();
            recording = false;
        }
    };
}


/* =========================================================
   HANDLE UPLOADED / CAPTURED FILE
   ========================================================= */

async function handleFile(file) {
    if (!state.currentOrderId) {
        toast('Please provide an Order ID first.', 'warning');
        return;
    }

    if (!state.awaitingEvidence) {
        toast(
            'Start a return request before uploading evidence.',
            'warning'
        );
        return;
    }

    if (file.size > 50 * 1024 * 1024) {
        toast('Please keep evidence under 50 MB.', 'warning');
        return;
    }

    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');

    if (!isImage && !isVideo) {
        toast('Please select an image or video.', 'warning');
        return;
    }

    // When an unboxing video has been requested,
    // do not accept another image.
    if (state.awaitingUnboxingVideo && !isVideo) {
        toast(
            'An unboxing video is required. Please upload or record a video.',
            'warning'
        );
        return;
    }

    // Initial evidence should be a product photo or video.
    state.awaitingEvidence = false;

    hideUploadControls();

    addEvidencePreview(file);

    typing(true);

    await sleep(350);

    typing(false);

    addMessage(
        state.awaitingUnboxingVideo
            ? 'Unboxing video received. I will analyze the video evidence before deciding the next step.'
            : 'Evidence received. I will check its quality, product match, grievance details, and whether the media appears AI-generated.',
        'bot'
    );

    await pipeline(file);
}


/* =========================================================
   TOAST
   ========================================================= */

function toast(msg, type = 'info') {
    const toastElement = document.createElement('div');
    toastElement.className = 'toast';

    const icon =
        type === 'error'
            ? '❌'
            : type === 'success'
                ? '✅'
                : type === 'warning'
                    ? '⚠️'
                    : '💡';

    toastElement.innerHTML = `
        <span>${icon}</span>
        <span>${esc(msg)}</span>
    `;

    $('toastContainer').appendChild(toastElement);

    setTimeout(
        () => toastElement.remove(),
        3500
    );
}


/* =========================================================
   SETUP
   ========================================================= */

function setup() {
    $('sessionIdDisplay').textContent =
        '#' + state.sessionId;

    // Upload controls start hidden.
    hideUploadControls();

    addMessage(
        '👋 Welcome to **VeriCart**. I’ll first ask what went wrong, then your Order ID, and only then request photo/video evidence.'
    );

    /* ---------------------------------------------------------
       CHAT
       --------------------------------------------------------- */

    $('btnSend').onclick = () => send(
        $('messageInput').value
    );

    $('messageInput').onkeydown = event => {
        if (event.key === 'Enter') {
            send($('messageInput').value);
        }
    };


    /* ---------------------------------------------------------
       NEW CHAT
       --------------------------------------------------------- */

    $('btnNewChat').onclick = async () => {
        await fetch('/api/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: state.sessionId
            })
        });

        location.reload();
    };


    /* ---------------------------------------------------------
       FILE UPLOAD
       --------------------------------------------------------- */

    const fileInput = $('evidenceFileInput');

    $('btnBrowse').onclick = event => {
        event.stopPropagation();
        fileInput.click();
    };

    $('uploadZone').onclick = event => {
        if (
            event.target.closest('#btnBrowse') ||
            event.target.closest('#btnTakePhoto') ||
            event.target.closest('#btnTakeVideo')
        ) {
            return;
        }

        fileInput.click();
    };

    fileInput.onchange = event => {
        const file = event.target.files?.[0];

        if (file) {
            handleFile(file);
        }

        fileInput.value = '';
    };


    /* ---------------------------------------------------------
       TAKE PHOTO
       --------------------------------------------------------- */

    $('btnTakePhoto').onclick = async event => {
        event.preventDefault();
        event.stopPropagation();

        if (!state.currentOrderId) {
            toast('Please provide an Order ID first.', 'warning');
            return;
        }

        if (!state.awaitingEvidence) {
            toast(
                'Start a return request before capturing evidence.',
                'warning'
            );
            return;
        }

        if (state.awaitingUnboxingVideo) {
            toast(
                'An unboxing video is required, not another photo.',
                'warning'
            );
            return;
        }

        await openCamera('photo');
    };


    /* ---------------------------------------------------------
       TAKE VIDEO
       --------------------------------------------------------- */

    $('btnTakeVideo').onclick = async event => {
        event.preventDefault();
        event.stopPropagation();

        if (!state.currentOrderId) {
            toast('Please provide an Order ID first.', 'warning');
            return;
        }

        if (!state.awaitingEvidence) {
            toast(
                'Start a return request before capturing evidence.',
                'warning'
            );
            return;
        }

        await openCamera('video');
    };


    /* ---------------------------------------------------------
       DRAG & DROP
       --------------------------------------------------------- */

    ['dragover', 'dragenter'].forEach(eventName => {
        $('uploadZone').addEventListener(eventName, event => {
            event.preventDefault();

            $('uploadZone').classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        $('uploadZone').addEventListener(eventName, event => {
            event.preventDefault();

            $('uploadZone').classList.remove('drag-over');
        });
    });

    $('uploadZone').addEventListener('drop', event => {
        if (
            event.dataTransfer &&
            event.dataTransfer.files[0]
        ) {
            handleFile(event.dataTransfer.files[0]);
        }
    });


    /* ---------------------------------------------------------
       ATTACH BUTTON
       --------------------------------------------------------- */

    $('btnAttach').onclick = () => {
        if (state.awaitingEvidence) {
            fileInput.click();
        } else {
            toast(
                'Tell Vera your grievance and provide the Order ID first.',
                'info'
            );
        }
    };


    /* ---------------------------------------------------------
       DEMO ORDERS
       --------------------------------------------------------- */

    document.querySelectorAll('.demo').forEach(button => {
        button.onclick = () => {
            send('I want to return because the product is damaged');

            setTimeout(() => {
                send(
                    'My Order ID is ' + button.dataset.order
                );
            }, 700);
        };
    });


    /* ---------------------------------------------------------
       RESULT CLOSE
       --------------------------------------------------------- */

    $('resultCardWrapper').onclick = event => {
        if (
            event.target.id === 'resultCardWrapper' ||
            event.target.id === 'resultClose'
        ) {
            $('resultCardWrapper').classList.remove('active');
        }
    };
}


document.addEventListener('DOMContentLoaded', setup);
