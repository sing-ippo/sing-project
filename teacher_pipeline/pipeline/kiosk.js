// Адрес голосового сервера (voice_server). Менять только здесь.
const BACKEND_URL = "http://localhost:8010";

const recordBtn = document.getElementById("record-btn");
const questionEl = document.getElementById("question");
const answerEl = document.getElementById("answer");

let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isBusy = false;

// Микрофон запрашиваем один раз и переиспользуем поток.
async function ensureStream() {
    if (mediaStream) return mediaStream;
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return mediaStream;
}

async function startRecording() {
    if (isRecording || isBusy) return;

    try {
        const stream = await ensureStream();
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) audioChunks.push(event.data);
        };
        mediaRecorder.onstop = sendAudio;
        mediaRecorder.start();

        isRecording = true;
        recordBtn.classList.add("recording");
        answerEl.textContent = "";
        questionEl.textContent = "Слушаю…";
    } catch (err) {
        answerEl.textContent = "Нет доступа к микрофону. Разрешите доступ и попробуйте снова.";
        console.error(err);
    }
}

function stopRecording() {
    if (!isRecording) return;
    isRecording = false;
    recordBtn.classList.remove("recording");
    recordBtn.classList.add("loading");
    questionEl.textContent = "Обрабатываю…";

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
}

async function sendAudio() {
    isBusy = true;
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("file", blob, "question.webm");

    try {
        const response = await fetch(`${BACKEND_URL}/ask`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Сервер вернул ${response.status}`);
        }

        const data = await response.json();
        showResult(data);
    } catch (err) {
        questionEl.textContent = "";
        answerEl.textContent = "Сервис временно недоступен. Попробуйте ещё раз.";
        console.error(err);
    } finally {
        isBusy = false;
        recordBtn.classList.remove("loading");
    }
}

function showResult(data) {
    questionEl.textContent = data.question || "";
    answerEl.textContent = data.answer || "";

    if (data.audio_base64) {
        try {
            const audioBlob = base64ToBlob(data.audio_base64, "audio/wav");
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.onended = () => URL.revokeObjectURL(audioUrl);
            audio.play().catch((err) => console.error("Не удалось проиграть аудио:", err));
        } catch (err) {
            console.error("Ошибка декодирования аудио:", err);
        }
    }
}

function base64ToBlob(base64, mimeType) {
    const byteChars = atob(base64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
}

// Удержание кнопки = запись. Мышь и тач.
recordBtn.addEventListener("mousedown", startRecording);
recordBtn.addEventListener("mouseup", stopRecording);
recordBtn.addEventListener("mouseleave", stopRecording);
recordBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    startRecording();
});
recordBtn.addEventListener("touchend", (e) => {
    e.preventDefault();
    stopRecording();
});
