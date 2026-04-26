"use strict";

(function () {
  const appConfigEl = document.getElementById("app-config");
  const appConfig = appConfigEl ? JSON.parse(appConfigEl.textContent) : {};
  let uiMeta = {
    states: appConfig.states || [],
    relays: appConfig.relays || [],
    inputs: appConfig.inputs || [],
    cameras: appConfig.cameras || [],
    languages: appConfig.languages || {},
    text: appConfig.text || {}
  };
  let currentLanguage = "nl";

  const connDot = document.getElementById("connDot");
  connDot.classList.add("disconnected");
  const gameStateEl = document.getElementById("gameState");
  const soundReadyEl = document.getElementById("soundReady");
  const timerEl = document.getElementById("timer");
  timerEl.addEventListener("click", () => {
    toggleTimer();
  });
  const shutdownBtn = document.getElementById("shutdownBtn");
  const rebootBtn = document.getElementById("rebootBtn");
  const langNlBtn = document.getElementById("lang-nl");
  const langEnBtn = document.getElementById("lang-en");
  const stateButtonsEl = document.getElementById("stateButtons");
  const relayButtonsEl = document.getElementById("relayButtons");
  const cameraGridEl = document.getElementById("cameraGrid");

  let timer = { running: false, elapsed: 0 };
  let timerBaseAt = performance.now();
  let timerInterval = null;

  let lastHintsRenderKey = null;
  let lastRenderedTimerText = null;
  let lastRenderedTimerState = null;

  function orderedItems(items) {
    return (items || [])
      .filter(item => item && item.visible !== false)
      .slice()
      .sort((a, b) => Number(a.order || 0) - Number(b.order || 0));
  }

  function applyMetadata(data) {
    let changed = false;

    if (Array.isArray(data.states)) {
      uiMeta.states = data.states;
      changed = true;
    }
    if (Array.isArray(data.relays_meta)) {
      uiMeta.relays = data.relays_meta;
      changed = true;
    } else if (Array.isArray(data.relays)) {
      uiMeta.relays = data.relays;
      changed = true;
    }
    if (Array.isArray(data.cameras)) {
      uiMeta.cameras = data.cameras;
      changed = true;
    }
    if (Array.isArray(data.inputs_meta)) {
      uiMeta.inputs = data.inputs_meta;
      changed = true;
    }
    if (data.languages && typeof data.languages === "object") {
      uiMeta.languages = data.languages;
    }
    if (data.text && typeof data.text === "object") {
      uiMeta.text = data.text;
    }

    if (changed) {
      renderStaticControls();
    }
  }

  function renderStaticControls() {
    renderStateButtons();
    renderRelayButtons();
    renderCameras();
  }

  function renderStateButtons() {
    if (!stateButtonsEl) return;
    stateButtonsEl.innerHTML = "";

    orderedItems(uiMeta.states).forEach(state => {
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.type = "button";
      btn.dataset.state = state.id;
      btn.textContent = state.label || state.id;
      btn.disabled = state.enabled === false || state.selectable === false;
      btn.addEventListener("click", () => setState(state.id));
      stateButtonsEl.appendChild(btn);
    });
  }

  function renderRelayButtons() {
    if (!relayButtonsEl) return;
    relayButtonsEl.innerHTML = "";

    orderedItems(uiMeta.relays).forEach(relay => {
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.type = "button";
      btn.dataset.relay = relay.id;
      btn.id = `relay-btn-${relay.id}`;
      btn.textContent = relay.label || relay.id;
      btn.disabled = relay.enabled === false;
      btn.addEventListener("click", async () => {
        const name = btn.dataset.relay;
        const r = await fetch("/api/relay/toggle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name })
        });
        if (!r.ok) return;
        const data = await r.json();
        setRelayButton(data.name, data.on);
      });
      relayButtonsEl.appendChild(btn);
    });
  }

  function renderCameras() {
    if (!cameraGridEl) return;
    cameraGridEl.innerHTML = "";

    const cameras = orderedItems(uiMeta.cameras);
    cameraGridEl.style.setProperty("--camera-count", Math.max(cameras.length, 1));

    cameras.forEach(camera => {
      const key = camera.id;
      const url = String(camera.url || "").trim();

      const item = document.createElement("div");
      item.className = "cameraItem";
      item.id = `camera-card-${key}`;

      const wrap = document.createElement("div");
      wrap.className = "cameraFrameWrap";

      const frame = document.createElement("iframe");
      frame.className = "cameraFrame";
      frame.id = `camera-frame-${key}`;
      frame.title = camera.label || key;
      frame.loading = "lazy";
      frame.allowFullscreen = true;
      frame.referrerPolicy = "no-referrer";

      if (url) {
        frame.src = url;
      } else {
        frame.removeAttribute("src");
      }

      const openBtn = document.createElement("a");
      openBtn.className = "btn small cameraOpenBtn hidden";
      openBtn.id = `camera-open-${key}`;
      openBtn.target = "_blank";
      openBtn.rel = "noopener noreferrer";
      openBtn.textContent = "open";

      if (url) {
        openBtn.href = url;
        openBtn.classList.remove("hidden");
      } else {
        openBtn.removeAttribute("href");
        openBtn.classList.add("hidden");
      }

      wrap.appendChild(frame);
      wrap.appendChild(openBtn);
      item.appendChild(wrap);
      cameraGridEl.appendChild(item);
    });
  }

  function pad2(n) { return String(n).padStart(2, "0"); }

  function renderTimer() {
    const now = performance.now();
    let elapsed = timer.elapsed;

    if (timer.running) elapsed += (now - timerBaseAt) / 1000.0;
    elapsed = Math.max(0, elapsed);

    const total = Math.floor(elapsed);
    const mm = Math.floor(total / 60);
    const ss = total % 60;
    const timerText = `${pad2(mm)}:${pad2(ss)}`;

    if (timerText !== lastRenderedTimerText) {
      timerEl.textContent = timerText;
      lastRenderedTimerText = timerText;
    }

    const isOver15Min = elapsed >= 15 * 60;
    const isPaused = !timer.running && elapsed > 0;
    const timerState = isOver15Min ? "danger" : isPaused ? "paused" : "normal";

    if (timerState !== lastRenderedTimerState) {
      timerEl.classList.remove("paused", "danger");

      if (timerState === "danger") {
        timerEl.classList.add("danger");
      } else if (timerState === "paused") {
        timerEl.classList.add("paused");
      }

      lastRenderedTimerState = timerState;
    }
  }

  function applyTimer(newTimer) {
    timer = { running: !!newTimer.running, elapsed: Number(newTimer.elapsed || 0) };
    timerBaseAt = performance.now();

    if (!timerInterval) timerInterval = setInterval(renderTimer, 250);

    renderTimer();
  }

  function setInputDot(label, state) {
    const safe = String(label).replaceAll(" ", "_");
    const dot = document.getElementById(`dot-${safe}`);
    if (!dot) return;

    dot.classList.remove("active", "inactive", "unknown");
    dot.title = state;

    if (state === "ACTIVE") dot.classList.add("active");
    else if (state === "INACTIVE") dot.classList.add("inactive");
    else dot.classList.add("unknown");
  }

  function setRelayButton(name, on) {
    const btn = document.getElementById(`relay-btn-${name}`);
    if (!btn) return;
    btn.classList.toggle("active-state", !!on);
  }

  function setGameState(st) {
    gameStateEl.textContent = st;

    document.querySelectorAll("button[data-state]").forEach(btn => {
      btn.classList.toggle("active-state", btn.dataset.state === st);
    });

    if (st === "idle") {
      shutdownBtn.classList.remove("hidden");
      rebootBtn.classList.remove("hidden");
    } else {
      shutdownBtn.classList.add("hidden");
      rebootBtn.classList.add("hidden");
    }
  }

  function setSoundStatus(sound) {
    if (!soundReadyEl) return;

    const ready = !!(sound && sound.ready);
    soundReadyEl.textContent = ready ? "yes" : "no";
    soundReadyEl.classList.toggle("sound-ready", ready);
    soundReadyEl.classList.toggle("sound-not-ready", !ready);

    if (sound && sound.last_status_payload) {
      soundReadyEl.title = sound.last_status_payload;
    } else {
      soundReadyEl.title = "";
    }
  }

  function setLanguage(lang) {
    currentLanguage = lang || "nl";
    langNlBtn.classList.toggle("active-state", lang === "nl");
    langEnBtn.classList.toggle("active-state", lang === "en");
  }

  function uiText(key) {
    const langText = uiMeta.text[currentLanguage] || uiMeta.text.nl || {};
    return langText[key] || key;
  }

  async function loadInitial() {
    const r = await fetch("/api/state", { cache: "no-store" });
    const data = await r.json();
    applyMetadata(data);
    setGameState(data.game_state);
    setLanguage(data.language || "nl");

    renderHints(data.game_state, data.hints || {});
    for (const [label, state] of Object.entries(data.inputs || {})) {
      setInputDot(label, state);
    }
    for (const [name, on] of Object.entries(data.relays || {})) {
      setRelayButton(name, on);
    }
    setSoundStatus(data.sound || {});
    applyTimer(data.timer || { running: false, elapsed: 0 });
  }

  async function setState(st) {
    await fetch("/api/set_state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: st })
    });
  }

  async function toggleTimer() {
    const r = await fetch("/api/timer/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    if (!r.ok) return;

    const data = await r.json();
    if (data.timer) {
      applyTimer(data.timer);
    }
  }

  async function setUiLanguage(lang) {
    const r = await fetch("/api/language", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: lang })
    });
    if (!r.ok) return;
    const data = await r.json();
    setLanguage(data.language || lang);
  }

  langNlBtn.addEventListener("click", () => setUiLanguage("nl"));
  langEnBtn.addEventListener("click", () => setUiLanguage("en"));

  shutdownBtn.addEventListener("click", async () => {
    const ok = confirm("Weet je zeker dat je de Raspberry Pi wilt afsluiten?");
    if (!ok) return;

    const r = await fetch("/api/poweroff", { method: "POST" });
    if (r.ok) connDot.classList.add("disconnected");
  });

  rebootBtn.addEventListener("click", async () => {
    const ok = confirm("Weet je zeker dat je de Raspberry Pi wilt herstarten?");
    if (!ok) return;

    const r = await fetch("/api/reboot", { method: "POST" });
    if (r.ok) connDot.classList.add("disconnected");
  });

  function createHintItem(h) {
    const li = document.createElement("li");
    li.className = "row compactRow hintItem";
    li.title = h.id || "";

    const label = document.createElement("span");
    label.className = "label";
    label.textContent = h.label || h.id;

    const play = document.createElement("span");
    play.className = "hintPlay";
    play.textContent = "\u25b6";

    li.appendChild(label);
    li.appendChild(play);

    li.addEventListener("click", () => {
      fetch(`/sound/hint/${encodeURIComponent(h.id)}`);
    });

    return li;
  }

  function createPuzzleBlock(puzzle, startOpen = false) {
    return createCollapsibleHintBlock(
      puzzle.label || puzzle.id || "Puzzel",
      puzzle.hints || [],
      "hintPuzzleTitle",
      startOpen
    );
  }

  function createCollapsibleHintBlock(title, hints, titleClass, startOpen = false) {
    const fragment = document.createDocumentFragment();

    const header = document.createElement("li");
    header.className = `row compactRow ${titleClass} hintAccordionHeader`;

    const titleText = document.createElement("span");
    titleText.innerHTML = `<strong>${title}</strong>`;

    const toggleIcon = document.createElement("span");
    toggleIcon.className = "hintToggleIcon";

    header.appendChild(titleText);
    header.appendChild(toggleIcon);

    const wrapper = document.createElement("li");
    wrapper.className = "hintPuzzleHints hintAccordionBody";

    const innerList = document.createElement("ul");
    innerList.className = "list compact";

    for (const h of (hints || [])) {
      innerList.appendChild(createHintItem(h));
    }

    wrapper.appendChild(innerList);

    wrapper.classList.toggle("hidden", !startOpen);
    toggleIcon.textContent = startOpen ? "\u25bc" : "\u25b6";

    fragment.appendChild(header);
    fragment.appendChild(wrapper);

    fragment._accordion = {
      header,
      wrapper,
      toggleIcon,
      get isOpen() {
        return !wrapper.classList.contains("hidden");
      },
      open() {
        wrapper.classList.remove("hidden");
        toggleIcon.textContent = "\u25bc";
      },
      close() {
        wrapper.classList.add("hidden");
        toggleIcon.textContent = "\u25b6";
      }
    };

    return fragment;
  }

  function renderHints(gameState, hintsData) {
    const key = JSON.stringify({
      gameState,
      hintsData
    });

    if (key === lastHintsRenderKey) {
      return;
    }

    lastHintsRenderKey = key;
    const sceneEl = document.getElementById("hints-scene");
    const hintsEl = document.getElementById("hints");

    if (sceneEl) sceneEl.textContent = gameState || "";
    if (!hintsEl) return;

    hintsEl.innerHTML = "";

    const globalLabel = hintsData?.global?.label || uiText("global_hints_label");
    const globalHints = hintsData?.global?.hints || [];
    const puzzles = hintsData?.puzzles || [];

    if (globalHints.length === 0 && puzzles.length === 0) {
      const li = document.createElement("li");
      li.className = "row compactRow";
      li.innerHTML = `<span class="muted">${uiText("no_hints")}</span>`;
      hintsEl.appendChild(li);
      return;
    }

    const accordionBlocks = [];

    if (globalHints.length > 0) {
      const globalBlock = createCollapsibleHintBlock(
        globalLabel,
        globalHints,
        "hintSectionTitle",
        false
      );
      accordionBlocks.push(globalBlock);
      hintsEl.appendChild(globalBlock);
    }

    puzzles.forEach((puzzle, index) => {
      const block = createPuzzleBlock(puzzle, index === 0);
      accordionBlocks.push(block);
      hintsEl.appendChild(block);
    });

    function closeAllExcept(activeBlock) {
      accordionBlocks.forEach(block => {
        if (block !== activeBlock) {
          block._accordion.close();
        }
      });
    }

    accordionBlocks.forEach(block => {
      const acc = block._accordion;
      acc.header.addEventListener("click", () => {
        const willOpen = !acc.isOpen;

        closeAllExcept(block);

        if (willOpen) {
          acc.open();
        } else {
          acc.close();
        }
      });
    });
  }

  function connectSSE() {
    const es = new EventSource("/events");

    es.addEventListener("open", () => {
      connDot.classList.remove("disconnected");
      connDot.classList.add("connected");
    });

    es.addEventListener("error", () => {
      connDot.classList.remove("connected");
      connDot.classList.add("disconnected");
    });

    es.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data);

        if (evt.type === "input") {
          setInputDot(evt.label, evt.state);
        } else if (evt.type === "game_state") {
          setGameState(evt.game_state);
        } else if (evt.type === "timer") {
          applyTimer(evt.timer);
        } else if (evt.type === "full_state") {
          applyMetadata(evt);
          setGameState(evt.game_state);
          setLanguage(evt.language || "nl");
          for (const [label, state] of Object.entries(evt.inputs || {})) {
            setInputDot(label, state);
          }
          for (const [name, on] of Object.entries(evt.relays || {})) {
            setRelayButton(name, on);
          }
          renderHints(evt.game_state, evt.hints || {});
          applyTimer(evt.timer || { running: false, elapsed: 0 });
          setSoundStatus(evt.sound || {});
        } else if (evt.type === "language") {
          setLanguage(evt.language || "nl");
          renderHints(gameStateEl.textContent, evt.hints || {});
        } else if (evt.type === "sound_status") {
          setSoundStatus(evt.sound || {});
        } else if (evt.type === "relay") {
          setRelayButton(evt.name, evt.on);
        } else if (evt.type === "relays" && evt.pattern) {
          for (const [name, on] of Object.entries(evt.pattern)) {
            setRelayButton(name, on);
          }
        }
      } catch (e) {
        console.error("Failed to handle SSE message", e);
      }
    };
  }

  (async () => {
    try {
      renderStaticControls();
      await loadInitial();
      connectSSE();
    } catch (e) {
      console.error("Failed to initialize escape room UI", e);
    }
  })();
})();
