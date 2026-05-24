// Адрес голосового сервера (voice_server). Менять только здесь.
const BACKEND_URL = "http://localhost:8010";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");

// Память диалога: прошлые ходы [{role, content}] — отправляем для разрешения «про него» и т.п.
const history = [];

// Стадии «как в мессенджере» — крутятся по таймеру, пока ждём ответ.
const STAGES = [
    "Отправляю запрос…",
    "Ищу в базе знаний и на mirea.ru…",
    "Передаю модели…",
    "Модель формулирует ответ…",
];

function scrollDown() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : s;
    return d.innerHTML;
}

// Линкуем ПОСЛЕ экранирования: сначала полные URL, затем «голые» домены
// (priem.mirea.ru). Без lookbehind (старый Safari ломается) — email вроде
// pk@mirea.ru бережём проверкой символа перед совпадением в колбэке.
const LINK_RE = /(https?:\/\/[^\s<]+)|((?:[a-zA-Z0-9-]+\.)+(?:ru|рф|com|org|edu)(?:\/[^\s<]*)?)/g;

function linkify(text) {
    return escapeHtml(text).replace(LINK_RE, (m, full, bare, offset, str) => {
        if (full) return `<a href="${full}" target="_blank" rel="noopener">${full}</a>`;
        // голый домен: пропускаем, если это часть email/уже-домена (перед ним @ . или буква/цифра)
        const prev = offset > 0 ? str[offset - 1] : "";
        if (/[@\w.]/.test(prev)) return m;
        return `<a href="https://${bare}" target="_blank" rel="noopener">${bare}</a>`;
    });
}

function addMessage(text, cls, asHtml) {
    const el = document.createElement("div");
    el.className = "msg " + cls;
    if (asHtml) el.innerHTML = text;
    else el.textContent = text;
    messagesEl.appendChild(el);
    scrollDown();
    return el;
}

// Анимированный статус-пузырь: печатающие точки + сменяемый текст стадии.
function createStatusBubble() {
    const el = document.createElement("div");
    el.className = "msg bot status";
    el.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
    const label = document.createElement("span");
    label.className = "status-text";
    label.textContent = STAGES[0];
    el.appendChild(label);
    messagesEl.appendChild(el);
    scrollDown();

    let i = 0;
    const timer = setInterval(() => {
        if (i < STAGES.length - 1) {
            i += 1;
            label.textContent = STAGES[i];
        }
    }, 1100);

    return { stop: () => { clearInterval(timer); el.remove(); } };
}

function hostOf(url) {
    try {
        return new URL(url).host.replace(/^www\./, "");
    } catch (e) {
        return "";
    }
}

function addSources(list) {
    if (!list || !list.length) return;
    const wrap = document.createElement("div");
    wrap.className = "sources";

    const title = document.createElement("div");
    title.className = "sources-title";
    title.textContent = "Полезные ссылки по теме";
    wrap.appendChild(title);

    list.forEach((s) => {
        const card = document.createElement("a");
        card.className = "source-card";
        card.href = s.url || "#";
        card.target = "_blank";
        card.rel = "noopener";

        let snippet = (s.snippet || "").slice(0, 140);
        if ((s.snippet || "").length > 140) snippet += "…";

        card.innerHTML =
            `<span class="source-host">${escapeHtml(hostOf(s.url))}</span>` +
            `<span class="source-name">${escapeHtml(s.title || s.url || "")}</span>` +
            (snippet ? `<span class="source-snippet">${escapeHtml(snippet)}</span>` : "");
        wrap.appendChild(card);
    });

    messagesEl.appendChild(wrap);
    scrollDown();
}

function addFeedback(requestId) {
    const wrap = document.createElement("div");
    wrap.className = "fb";
    wrap.innerHTML = "<span>Помогло?</span>";
    const yes = document.createElement("button");
    yes.textContent = "👍 Да";
    const no = document.createElement("button");
    no.textContent = "👎 Нет";
    wrap.appendChild(yes);
    wrap.appendChild(no);

    const send = async (helpful) => {
        wrap.innerHTML = helpful ? "<span>Спасибо за отзыв! 🙂</span>" : "<span>Спасибо, учтём!</span>";
        try {
            await fetch(`${BACKEND_URL}/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ request_id: requestId, helpful }),
            });
        } catch (err) {
            console.error("Не удалось отправить отзыв:", err);
        }
    };
    yes.onclick = () => send(true);
    no.onclick = () => send(false);

    messagesEl.appendChild(wrap);
    scrollDown();
}

formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = inputEl.value.trim();
    if (!question) return;

    addMessage(question, "user");
    inputEl.value = "";
    inputEl.disabled = true;
    sendBtn.disabled = true;

    const status = createStatusBubble();

    try {
        const resp = await fetch(`${BACKEND_URL}/ask_text`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, history: history.slice(-6) }),
        });
        if (!resp.ok) throw new Error(`Сервер вернул ${resp.status}`);
        const data = await resp.json();

        status.stop();
        const answer = data.answer || "";
        addMessage(linkify(answer), "bot", true);
        addSources(data.sources);
        if (data.request_id) addFeedback(data.request_id);

        history.push({ role: "user", content: question }, { role: "assistant", content: answer });
    } catch (err) {
        status.stop();
        addMessage("Сервис временно недоступен. Попробуйте ещё раз.", "bot");
        console.error(err);
    } finally {
        inputEl.disabled = false;
        sendBtn.disabled = false;
        inputEl.focus();
    }
});
