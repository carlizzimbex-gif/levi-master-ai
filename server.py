
const $ = (id) => document.getElementById(id);

const form = $("form");
const modeButtons = document.querySelectorAll("[data-mode]");

const instrumentalInput = $("instrumental");
const vocalsInput = $("vocals");
const trackInput = $("track");

let currentMode = "mix";
let activeUrls = [];

function showError(message) {
  const error = $("error");
  if (!error) return;
  error.textContent = message;
  error.classList.remove("hidden");
  error.hidden = false;
}

function clearError() {
  const error = $("error");
  if (!error) return;
  error.textContent = "";
  error.classList.add("hidden");
  error.hidden = true;
}

function updateMode(mode) {
  currentMode = mode;

  modeButtons.forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  $("mixFields").classList.toggle("hidden", mode !== "mix");
  $("masterFields").classList.toggle("hidden", mode !== "master");

  instrumentalInput.required = mode === "mix";
  vocalsInput.required = mode === "mix";
  trackInput.required = mode === "master";

  $("submit").innerHTML = mode === "mix"
    ? "<span>✦</span> MISTURAR E MASTERIZAR <b>→</b>"
    : "<span>✦</span> MASTERIZAR ÁUDIO <b>→</b>";
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => updateMode(button.dataset.mode));
});

function connectRange(inputId, outputId, suffix = " dB") {
  const input = $(inputId);
  const output = $(outputId);
  if (!input || !output) return;

  const update = () => {
    output.textContent = inputId === "compression"
      ? (Number(input.value) <= 3 ? "Leve" :
         Number(input.value) <= 6 ? "Média" : "Forte")
      : `${input.value}${suffix}`;
  };

  input.addEventListener("input", update);
  update();
}

connectRange("vocalGain", "gainValue");
connectRange("lufs", "lufsValue", " LUFS");
connectRange("bass", "bassValue");
connectRange("treble", "trebleValue");
connectRange("presence", "presenceValue");
connectRange("compression", "compressionValue", "");

function showFileName(input, outputId) {
  const output = $(outputId);
  if (!input || !output) return;

  input.addEventListener("change", () => {
    output.textContent = input.files?.[0]?.name || "Escolher ficheiro";
  });
}

showFileName(instrumentalInput, "instName");
showFileName(vocalsInput, "voxName");
showFileName(trackInput, "trackName");

function validateFiles() {
  if (currentMode === "mix") {
    if (!instrumentalInput.files.length || !vocalsInput.files.length) {
      throw new Error("Seleciona o instrumental e a voz antes de continuar.");
    }

    if (
      instrumentalInput.files[0].size === 0 ||
      vocalsInput.files[0].size === 0
    ) {
      throw new Error("Um dos ficheiros selecionados está vazio.");
    }
  } else {
    if (!trackInput.files.length) {
      throw new Error("Seleciona uma música para masterizar.");
    }

    if (trackInput.files[0].size === 0) {
      throw new Error("O ficheiro selecionado está vazio.");
    }
  }

  const files = currentMode === "mix"
    ? [instrumentalInput.files[0], vocalsInput.files[0]]
    : [trackInput.files[0]];

  const maxBytes = 200 * 1024 * 1024;
  const allowed = /\.(wav|mp3|m4a|aac|flac|ogg|aiff|aif)$/i;

  for (const file of files) {
    if (!allowed.test(file.name)) {
      throw new Error(`Formato não suportado: ${file.name}`);
    }

    if (file.size > maxBytes) {
      throw new Error("Cada ficheiro deve ter no máximo 200 MB.");
    }
  }
}

function makeFormData(profile) {
  const data = new FormData();

  data.append("mode", currentMode);
  data.append(
    "output_format",
    document.querySelector('input[name="format"]:checked')?.value || "wav"
  );
  data.append("target_lufs", $("lufs").value);
  data.append("vocal_gain", $("vocalGain").value);
  data.append("bass", $("bass").value);
  data.append("treble", $("treble").value);
  data.append("presence", $("presence").value);
  data.append("compression", $("compression").value);
  data.append("profile", profile);

  if (currentMode === "mix") {
    data.append("instrumental", instrumentalInput.files[0]);
    data.append("vocals", vocalsInput.files[0]);
  } else {
    data.append("track", trackInput.files[0]);
  }

  return data;
}

function setProgress(percent, message) {
  const wrap = $("progressWrap");
  wrap.classList.remove("hidden");
  wrap.hidden = false;

  $("progressText").textContent = message;
  $("progressPct").textContent = `${percent}%`;

  const bar = wrap.querySelector(".progress span");
  if (bar) bar.style.width = `${percent}%`;
}

function clearResults() {
  activeUrls.forEach((url) => URL.revokeObjectURL(url));
  activeUrls = [];

  const result = $("result");
  result.replaceChildren();
  result.classList.add("hidden");
  result.hidden = true;
}

async function processVersion(profile, index) {
  const label = profile === "natural" ? "Natural Pro" : "Perfect Modern";

  setProgress(
    index === 1 ? 10 : 55,
    `A processar versão ${index} de 2: ${label}…`
  );

  const response = await fetch("/api/process", {
    method: "POST",
    body: makeFormData(profile)
  });

  if (!response.ok) {
    let message = `O servidor devolveu o erro ${response.status}.`;

    try {
      const body = await response.json();
      if (body.detail) {
        message = typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
      }
    } catch (_) {
      // Mantém a mensagem de erro original.
    }

    throw new Error(message);
  }

  const blob = await response.blob();

  if (!blob.size) {
    throw new Error(`O servidor devolveu um ficheiro vazio para ${label}.`);
  }

  const url = URL.createObjectURL(blob);
  activeUrls.push(url);

  return { label, url, blob };
}

function showVersions(versions) {
  const result = $("result");
  result.replaceChildren();

  const heading = document.createElement("h2");
  heading.textContent = "A tua música está pronta!";
  result.appendChild(heading);

  const description = document.createElement("p");
  description.textContent =
    "Escuta as duas versões e descarrega a que preferires.";
  result.appendChild(description);

  versions.forEach((version) => {
    const card = document.createElement("article");
    card.className = "version-card";

    const title = document.createElement("h3");
    title.textContent = version.label;

    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "metadata";
    audio.src = version.url;
    audio.style.width = "100%";

    const download = document.createElement("a");
    download.href = version.url;
    download.download =
      `levi-master-${version.label.toLowerCase().replace(/\s+/g, "-")}.` +
      (document.querySelector('input[name="format"]:checked')?.value || "wav");
    download.textContent = "Descarregar versão";
    download.className = "download-button";

    card.append(title, audio, download);
    result.appendChild(card);
  });

  result.classList.remove("hidden");
  result.hidden = false;
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  clearResults();

  const submit = $("submit");
  submit.disabled = true;

  try {
    validateFiles();

    submit.textContent = "A processar…";
    setProgress(5, "A preparar os ficheiros de áudio…");

    const versions = [];

    versions.push(await processVersion("natural", 1));
    setProgress(55, "Primeira versão concluída. A preparar a segunda…");

    versions.push(await processVersion("modern", 2));

    setProgress(100, "Processamento concluído!");
    showVersions(versions);
  } catch (error) {
    showError(error.message || "Ocorreu um erro ao processar o áudio.");
  } finally {
    submit.disabled = false;
    updateMode(currentMode);
  }
});

updateMode("mix");
