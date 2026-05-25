// Адрес сервера генерации квизов. Менять только здесь.
const BACKEND_URL = "/api/quiz";

const modeTextBtn = document.getElementById("mode-text");
const modeDocBtn = document.getElementById("mode-doc");
const paneText = document.getElementById("pane-text");
const paneDoc = document.getElementById("pane-doc");
const textInput = document.getElementById("text-input");
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
const exportFormat = document.getElementById("export-format");
const exportBtn = document.getElementById("export-btn");
const exportAnswers = document.getElementById("export-answers");
const questionArea = document.getElementById("question-area");
const resultArea = document.getElementById("result-area");
const restartBtn = document.getElementById("restart-btn");

let mode = "text"; // "text" | "document"
let quiz = [];
let lastMeta = {};
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

// --- Переключатель режима ---
function setMode(next) {
    mode = next;
    const isText = next === "text";
    modeTextBtn.classList.toggle("active", isText);
    modeDocBtn.classList.toggle("active", !isText);
    paneText.hidden = !isText;
    paneDoc.hidden = isText;
}
modeTextBtn.addEventListener("click", () => setMode("text"));
modeDocBtn.addEventListener("click", () => setMode("document"));

fileInput.addEventListener("change", () => {
    fileNameEl.textContent = fileInput.files.length
        ? fileInput.files[0].name
        : "Выбрать документ (.pdf / .docx / .txt)";
});

// --- Генерация: единый FormData на POST /quiz ---
genBtn.addEventListener("click", generate);

async function generate() {
    const num = Number(numInput.value) || 5;
    const form = new FormData();
    form.append("num_questions", String(num));

    if (mode === "text") {
        const text = textInput.value.trim();
        if (!text) { dbg("Пустой ввод — вставьте текст.", "dbg-err"); return; }
        form.append("text", text);
        dbg(`→ POST /quiz | текст ${text.length} симв | вопросов ${num}`);
    } else {
        if (!fileInput.files.length) { dbg("Выберите документ.", "dbg-err"); return; }
        const file = fileInput.files[0];
        form.append("file", file, file.name);
        form.append("pages", pagesInput.value.trim());
        form.append("topic", topicInput.value.trim());
        dbg(`→ POST /quiz | файл "${file.name}" | страницы: ${pagesInput.value || "авто"} | тема: ${topicInput.value || "—"} | вопросов ${num}`);
    }

    genBtn.disabled = true;
    progressEl.hidden = false;
    const t0 = performance.now();
    let ticks = 0;
    statusEl.textContent = "Генерирую квиз… 0.0с";
    const timer = setInterval(() => {
        ticks += 0.1;
        statusEl.textContent = `Генерирую квиз… ${ticks.toFixed(1)}с`;
    }, 100);

    try {
        const resp = await fetch(`${BACKEND_URL}/quiz`, { method: "POST", body: form });
        if (!resp.ok) {
            let detail = `HTTP ${resp.status}`;
            try { detail = (await resp.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
        }
        const data = await resp.json();
        const ms = Math.round(performance.now() - t0);
        const m = data.meta || {};
        dbg(`← 200 OK за ${ms} мс`, "dbg-ok");
        const conn = m.connectivity
            ? (m.connectivity.ok ? "✓ все вопросы привязаны к чанкам" : `✗ битых ссылок: ${m.connectivity.bad.length}`)
            : "—";
        dbg(`meta: модель=${m.model}, источник=${m.source}, вопросов=${m.generated}` +
            (m.words != null ? `, слов=${m.words}` : "") +
            (m.input_chars != null ? `, символов=${m.input_chars}` : "") +
            (m.connectivity ? `, связность=${conn}` : "") +
            `, время сервера=${m.elapsed_ms} мс`);
        quiz = data.quiz || [];
        lastMeta = m;
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

// --- Прохождение квиза ---
function startQuiz() {
    current = 0;
    score = 0;
    statusEl.textContent = "";
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

// Рендер LaTeX-формул ($...$) через KaTeX. Битый LaTeX не валит страницу.
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
    } catch (e) {
        console.error("KaTeX:", e);
    }
}

restartBtn.addEventListener("click", () => {
    quizBlock.hidden = true;
    inputBlock.hidden = false;
});

// --- Экспорт в форматы Moodle ---
function cdata(s) {
    // Безопасный CDATA: разбиваем редкую последовательность ]]>
    return "<![CDATA[" + String(s == null ? "" : s).split("]]>").join("]]]]><![CDATA[>") + "]]>";
}

function toMoodleXML(items) {
    const parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"];
    items.forEach((q, idx) => {
        parts.push('  <question type="multichoice">');
        parts.push(`    <name><text>Вопрос ${idx + 1}</text></name>`);
        parts.push(`    <questiontext format="html"><text>${cdata(q.question)}</text></questiontext>`);
        parts.push("    <single>true</single>");
        parts.push("    <shuffleanswers>true</shuffleanswers>");
        parts.push("    <answernumbering>abc</answernumbering>");
        (q.options || []).forEach((opt, i) => {
            const fraction = i === q.correct ? "100" : "0";
            parts.push(`    <answer fraction="${fraction}" format="html"><text>${cdata(opt)}</text></answer>`);
        });
        if (q.explanation) {
            parts.push(`    <generalfeedback format="html"><text>${cdata(q.explanation)}</text></generalfeedback>`);
        }
        parts.push("  </question>");
    });
    parts.push("</quiz>");
    return parts.join("\n");
}

function giftEscape(s) {
    return String(s == null ? "" : s).replace(/([~=#{}:\\])/g, "\\$1");
}

function toGIFT(items) {
    return items.map((q, idx) => {
        const lines = [`::Вопрос ${idx + 1}:: ${giftEscape(q.question)} {`];
        (q.options || []).forEach((opt, i) => {
            lines.push(`${i === q.correct ? "=" : "~"}${giftEscape(opt)}`);
        });
        if (q.explanation) lines.push(`#### ${giftEscape(q.explanation)}`);
        lines.push("}");
        return lines.join("\n");
    }).join("\n\n") + "\n";
}

function download(filename, text, mime) {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

function quizTitle() {
    const t = lastMeta.topic;
    return t && t !== "—" ? "Тест: " + t : "Тест";
}

// Печатные форматы (pdf/docx) — собирает сервер; качаем blob.
async function exportPrintable(fmt) {
    const form = new FormData();
    form.append("quiz", JSON.stringify(quiz));
    form.append("format", fmt);
    form.append("title", quizTitle());
    form.append("with_answers", exportAnswers && exportAnswers.checked ? "true" : "false");
    dbg(`→ POST /export | формат ${fmt} | ключ: ${exportAnswers && exportAnswers.checked}`);
    exportBtn.disabled = true;
    try {
        const resp = await fetch(`${BACKEND_URL}/export`, { method: "POST", body: form });
        if (!resp.ok) {
            let detail = `HTTP ${resp.status}`;
            try { detail = (await resp.json()).detail || detail; } catch (e) {}
            throw new Error(detail);
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = fmt === "pdf" ? "quiz.pdf" : "quiz.docx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        dbg(`← файл ${a.download} скачан`, "dbg-ok");
    } catch (err) {
        dbg(`← ОШИБКА экспорта: ${err.message}`, "dbg-err");
    } finally {
        exportBtn.disabled = false;
    }
}

exportBtn.addEventListener("click", () => {
    if (!quiz.length) return;
    const fmt = exportFormat.value;
    if (fmt === "gift") {
        download("quiz.gift.txt", toGIFT(quiz), "text/plain;charset=utf-8");
    } else if (fmt === "xml") {
        download("quiz_moodle.xml", toMoodleXML(quiz), "application/xml;charset=utf-8");
    } else {
        exportPrintable(fmt); // pdf | docx
    }
});
