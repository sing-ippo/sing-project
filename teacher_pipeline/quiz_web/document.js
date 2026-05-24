// Сервер генерации квизов (quiz_server). Менять только здесь.
const BACKEND_URL = "http://localhost:8020";

const fileInput = document.getElementById("file-input");
const fileNameEl = document.getElementById("file-name");
const pagesInput = document.getElementById("pages-input");
const topicInput = document.getElementById("topic-input");
const numInput = document.getElementById("num-input");
const genBtn = document.getElementById("gen-btn");
const progressEl = document.getElementById("progress");
const statusEl = document.getElementById("status");
const debugLog = document.getElementById("debug-log");
const inputBlock = document.getElementById("input-block");
const quizBlock = document.getElementById("quiz-block");
const questionArea = document.getElementById("question-area");
const resultArea = document.getElementById("result-area");
const restartBtn = document.getElementById("restart-btn");

let quiz = [];
let current = 0;
let score = 0;

function dbg(msg, cls) {
    const now = new Date();
    const ts = now.toLocaleTimeString("ru-RU", { hour12: false }) +
        "." + String(now.getMilliseconds()).padStart(3, "0");
    const line = document.createElement("div");
    if (cls) line.className = cls;
    line.textContent = `[${ts}] ${msg}`;
    debugLog.appendChild(line);
    debugLog.scrollTop = debugLog.scrollHeight;
}

function renderMath(el) {
    if (!window.renderMathInElement) return;
    try {
        renderMathInElement(el, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "$", right: "$", display: false },
            ],
            throwOnError: false,
        });
    } catch (e) { console.error("KaTeX:", e); }
}

fileInput.addEventListener("change", () => {
    fileNameEl.textContent = fileInput.files.length ? fileInput.files[0].name : "";
});

genBtn.addEventListener("click", generate);

async function generate() {
    if (!fileInput.files.length) { dbg("Выберите документ.", "dbg-err"); return; }
    const file = fileInput.files[0];
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("pages", pagesInput.value.trim());
    form.append("topic", topicInput.value.trim());
    form.append("num_questions", String(Number(numInput.value) || 5));

    genBtn.disabled = true;
    progressEl.hidden = false;
    dbg(`→ POST ${BACKEND_URL}/quiz_doc | "${file.name}" | страницы: ${pagesInput.value || "авто"} | тема: ${topicInput.value || "—"}`);
    const t0 = performance.now();
    let ticks = 0;
    statusEl.textContent = "Читаю документ и генерирую квиз… 0.0с";
    const timer = setInterval(() => {
        ticks += 0.1;
        statusEl.textContent = `Читаю документ и генерирую квиз… ${ticks.toFixed(1)}с`;
    }, 100);

    try {
        const resp = await fetch(`${BACKEND_URL}/quiz_doc`, { method: "POST", body: form });
        if (!resp.ok) {
            let detail = `HTTP ${resp.status}`;
            try { detail = (await resp.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
        }
        const data = await resp.json();
        const ms = Math.round(performance.now() - t0);
        const m = data.meta || {};
        dbg(`← 200 OK за ${ms} мс`, "dbg-ok");
        const conn = m.connectivity ? (m.connectivity.ok ? "✓ все вопросы привязаны к чанкам" : `✗ битых ссылок: ${m.connectivity.bad.length}`) : "—";
        dbg(`meta: страниц=${m.pages}, слов=${m.words ?? "?"}, тема=${m.topic}, вопросов=${m.generated}, связность=${conn}, время сервера=${m.elapsed_ms} мс`);
        quiz = data.quiz || [];
        if (!quiz.length) throw new Error("Пустой квиз");
        startQuiz();
    } catch (err) {
        const ms = Math.round(performance.now() - t0);
        dbg(`← ОШИБКА за ${ms} мс: ${err.message}`, "dbg-err");
        statusEl.textContent = "Ошибка: " + err.message;
    } finally {
        clearInterval(timer);
        genBtn.disabled = false;
        progressEl.hidden = true;
    }
}

function startQuiz() {
    current = 0; score = 0;
    inputBlock.hidden = true;
    quizBlock.hidden = false;
    resultArea.hidden = true;
    restartBtn.hidden = true;
    renderQuestion();
}

function renderQuestion() {
    const q = quiz[current];
    const letters = ["A", "B", "C", "D"];
    const card = document.createElement("div");
    card.className = "q-card";
    card.innerHTML = `<div class="q-progress">Вопрос ${current + 1} из ${quiz.length}</div>
        <div class="q-text">${escapeHtml(q.question)}</div>`;
    (q.options || []).forEach((opt, i) => {
        const btn = document.createElement("button");
        btn.className = "opt-btn";
        btn.textContent = `${letters[i] || ""}) ${opt}`;
        btn.onclick = () => answer(i, card, q);
        card.appendChild(btn);
    });
    questionArea.innerHTML = "";
    questionArea.appendChild(card);
    renderMath(card);
}

function answer(choice, card, q) {
    card.querySelectorAll(".opt-btn").forEach((b, i) => {
        b.disabled = true;
        if (i === q.correct) b.classList.add("correct");
        else if (i === choice) b.classList.add("wrong");
    });
    if (choice === q.correct) score++;
    if (q.explanation) {
        const exp = document.createElement("div");
        exp.className = "explanation";
        exp.textContent = "💡 " + q.explanation;
        card.appendChild(exp);
        renderMath(exp);
    }
    const next = document.createElement("button");
    next.className = "next-btn";
    next.textContent = current + 1 < quiz.length ? "Следующий вопрос →" : "Показать результат";
    next.onclick = () => {
        current++;
        if (current < quiz.length) renderQuestion();
        else showResult();
    };
    card.appendChild(next);
}

function showResult() {
    questionArea.innerHTML = "";
    resultArea.hidden = false;
    resultArea.textContent = `🏁 Результат: ${score} из ${quiz.length}`;
    restartBtn.hidden = false;
}

function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : s;
    return d.innerHTML;
}

restartBtn.addEventListener("click", () => {
    quizBlock.hidden = true;
    inputBlock.hidden = false;
});
