// Адрес сервера генерации квизов. Менять только здесь.
const BACKEND_URL = "http://localhost:8020";

const textInput = document.getElementById("text-input");
const numInput = document.getElementById("num-input");
const genBtn = document.getElementById("gen-btn");
const fileInput = document.getElementById("file-input");
const statusEl = document.getElementById("status");
const inputBlock = document.getElementById("input-block");
const quizBlock = document.getElementById("quiz-block");
const questionArea = document.getElementById("question-area");
const resultArea = document.getElementById("result-area");
const restartBtn = document.getElementById("restart-btn");

let quiz = [];
let current = 0;
let score = 0;

async function requestJSON(url, options) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try { detail = (await resp.json()).detail || detail; } catch (e) {}
        throw new Error(detail);
    }
    return resp.json();
}

async function generateFromText() {
    const text = textInput.value.trim();
    if (!text) { statusEl.textContent = "Вставьте текст или выберите файл."; return; }
    await runGeneration(() => requestJSON(`${BACKEND_URL}/quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, num_questions: Number(numInput.value) || 5 }),
    }));
}

async function generateFromFile(file) {
    const form = new FormData();
    form.append("file", file, file.name);
    await runGeneration(() => requestJSON(`${BACKEND_URL}/quiz_file`, { method: "POST", body: form }));
}

async function runGeneration(fetcher) {
    genBtn.disabled = true;
    statusEl.textContent = "⏳ Генерирую квиз через ИИ…";
    try {
        const data = await fetcher();
        quiz = data.quiz || [];
        if (!quiz.length) throw new Error("Пустой квиз");
        startQuiz();
    } catch (err) {
        statusEl.textContent = "Ошибка: " + err.message;
    } finally {
        genBtn.disabled = false;
    }
}

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
}

function answer(choice, card, q) {
    const buttons = card.querySelectorAll(".opt-btn");
    buttons.forEach((b, i) => {
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

genBtn.addEventListener("click", generateFromText);
fileInput.addEventListener("change", () => {
    if (fileInput.files.length) generateFromFile(fileInput.files[0]);
});
restartBtn.addEventListener("click", () => {
    quizBlock.hidden = true;
    inputBlock.hidden = false;
    fileInput.value = "";
});
