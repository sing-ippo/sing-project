// Адрес голосового сервера (voice_server). Менять только здесь.
const BACKEND_URL = "/api/voice";

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

// Рендер ответа бота как Markdown (жирный/списки/ссылки) + санитизация (XSS-safe).
// Формулы LaTeX защищаем от markdown плейсхолдерами; голые домены → кликабельные ссылки.
function renderMarkdown(text) {
    let src = String(text == null ? "" : text);

    // 1) Защитить математику ($$…$$, $…$, \[…\], \(…\)) — иначе markdown ломает _ и * в LaTeX.
    const math = [];
    src = src.replace(/\$\$[\s\S]+?\$\$|\$[^\n$]+?\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)/g, (m) => {
        math.push(m);
        return `@@MATH${math.length - 1}@@`;
    });

    // 2) Голые домены → полные URL (marked сделает кликабельными).
    src = src.replace(LINK_RE, (m, full, bare, offset, str) => {
        if (full) return full;
        const prev = offset > 0 ? str[offset - 1] : "";
        if (/[@\w./]/.test(prev)) return m; // часть email/пути — не трогаем
        return "https://" + bare;
    });

    let html = window.marked ? window.marked.parse(src, { breaks: true, gfm: true }) : escapeHtml(src);
    if (window.DOMPurify) html = window.DOMPurify.sanitize(html);

    // 3) Вернуть LaTeX (экранируя HTML-символы) — KaTeX отрендерит его позже из текстовых узлов.
    html = html.replace(/@@MATH(\d+)@@/g, (m, i) => escapeHtml(math[Number(i)]));
    return html;
}

// Рендер формул KaTeX в элементе (как на странице извлечения формул). Битый LaTeX не валит страницу.
function renderMath(el) {
    if (!window.renderMathInElement) return;
    try {
        window.renderMathInElement(el, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "\\[", right: "\\]", display: true },
                { left: "$", right: "$", display: false },
                { left: "\\(", right: "\\)", display: false },
            ],
            throwOnError: false,
        });
    } catch (e) {
        console.error("KaTeX:", e);
    }
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

// Видео-плеер RuTube — только для доверённого домена (iframe строим сами, не через markdown).
function addVideo(video) {
    if (!video || !video.embed_url || !video.embed_url.startsWith("https://rutube.ru/")) return;
    const wrap = document.createElement("div");
    wrap.className = "video-card";
    const title = document.createElement("div");
    title.className = "video-title";
    title.textContent = "🎬 " + (video.title || "Видео РТУ МИРЭА");
    const frame = document.createElement("iframe");
    frame.src = video.embed_url;
    frame.loading = "lazy";
    frame.allow = "clipboard-write; autoplay; fullscreen";
    frame.allowFullscreen = true;
    wrap.appendChild(title);
    wrap.appendChild(frame);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
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

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 90000);
    try {
        const resp = await fetch(`${BACKEND_URL}/ask_text`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, history: history.slice(-6) }),
            signal: ctrl.signal,
        });
        if (!resp.ok) throw new Error(`Сервер вернул ${resp.status}`);
        const data = await resp.json();

        status.stop();
        const answer = data.answer || "";
        const botEl = addMessage(renderMarkdown(answer), "bot", true);
        botEl.querySelectorAll("a").forEach((a) => { a.target = "_blank"; a.rel = "noopener"; });
        renderMath(botEl);
        addVideo(data.video);
        addSources(data.sources);
        if (data.request_id) addFeedback(data.request_id);

        history.push({ role: "user", content: question }, { role: "assistant", content: answer });
    } catch (err) {
        status.stop();
        const msg = err.name === "AbortError"
            ? "Ответ занял слишком долго. Попробуйте ещё раз."
            : "Сервис временно недоступен. Попробуйте ещё раз.";
        addMessage(msg, "bot");
        console.error(err);
    } finally {
        clearTimeout(timer);
        inputEl.disabled = false;
        sendBtn.disabled = false;
        inputEl.focus();
    }
});
