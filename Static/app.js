
"use strict";

const $ = (id) => document.getElementById(id);

const form = $("form");
const submitButton = $("submit");
const modeButtons = document.querySelectorAll("[data-mode]");

const instrumentalInput = $("instrumental");
const vocalsInput = $("vocals");
const trackInput = $("track");

let currentMode = "mix";
let isProcessing = false;

function setVisible(element, visible) {
  if (!element) return;

  element.classList.toggle("hidden", !visible);
  element.hidden = !visible;
}

function showError(message) {
  const error = $("error");
  if (!error) return;

  error.textContent = message;
  setVisible(error, true);
}

function clearError() {
  const error = $("error");
  if (!error) return;

  error.textContent = "";
  setVisible(error, false);
}

function selectedRadio(name, fallback) {
  const selected = document.querySelector(
    `input[name="${name}"]:checked`
  );

  return selected ? selected.value : fallback;
}

function updateMode(mode) {
  currentMode = mode === "master" ? "master" : "mix";

  modeButtons.forEach((button) => {
    const active = button.dataset.mode === currentMode;

    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  setVisible($("mixFields"), currentMode === "mix");
  setVisible($("masterFields"), currentMode === "master");

  if (instrumentalInput) {
    instrumentalInput.required = currentMode === "mix";
  }

  if (vocalsInput) {
    vocalsInput.required = currentMode === "mix";
  }

  if (trackInput) {
    trackInput.required = currentMode === "master";
  }

  if (submitButton && !isProcessing) {
    submitButton.innerHTML =
      currentMode === "mix"
        ? "<span>✦</span> MISTURAR E MASTERIZAR <b>→</b>"
        : "<span>✦</span> MASTERIZAR A MINHA MÚSICA <b>→</b>";
  }
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (!isProcessing) {
      updateMode(button.dataset.mode);
    }
  });
});

function connectRange(inputId, outputId, suffix = "") {
  const input = $(inputId);
  const output = $(outputId);

  if (!input || !output) return;

  const update = () => {
    let value = input.value;

    if (inputId === "lufs" && Number(value) < 0) {
      value = "−" + Math.abs(Number(value));
    }

    output.textContent = `${value}${suffix}`;
  };

  input.addEventListener("input", update);
  update();
}

connectRange("vocalGain", "gainValue", " dB");
connectRange("lufs", "lufsValue", " LUFS");
connectRange("bass", "bassValue", " dB");
connectRange("treble", "trebleValue", " dB");
connectRange("presence", "presenceValue", " dB");

const compressionInput = $("compression");
const compressionOutput = $("compressionValue");

if (compressionInput && compressionOutput) {
  const updateCompression = () => {
    const value = Number(compressionInput.value);

    const label =
      value <= 2 ? "Leve" :
      value <= 5 ? "Média" :
      value <= 8 ? "Forte" : "Muito forte";

    compressionOutput.textContent = `${label} (${value}/10)`;
  };

  compressionInput.addEventListener("input", updateCompression);
  updateCompression();
}

function showFileName(input, outputId) {
  const output = $(outputId);
  if (!input || !output) return;

  input.addEventListener("change", () => {
    output.textContent =
      input.files?.[0]?.name || "Escolher ficheiro";
  });
}

showFileName(instrumentalInput, "instName");
showFileName(vocalsInput, "voxName");
showFileName(trackInput, "trackName");

function validateFiles() {
  if (currentMode === "mix") {
    if (!instrumentalInput?.files?.[0]) {
      throw new Error("Seleciona o ficheiro instrumental.");
    }

    if (!vocalsInput?.files?.[0]) {
      throw new Error("Seleciona o ficheiro dos vocais.");
    }
  } else if (!trackInput?.files?.[0]) {
    throw new Error("Seleciona a música que pretendes masterizar.");
  }
}

function makeFormData(profile) {
  const data = new FormData();

  const style = selectedRadio("style", "natural");
  const allowedStyles = [
    "natural",
    "trap",
    "rap",
    "drill",
    "rnb",
    "afrobeat",
    "pop"
  ];

  if (!allowedStyles.includes(style)) {
    throw new Error("Seleciona um estilo musical válido.");
  }

  data.append("mode", currentMode);
  data.append("output_format", selectedRadio("format", "wav"));
  data.append("target_lufs", $("lufs").value);
  data.append("vocal_gain", $("vocalGain").value);
  data.append("bass", $("bass").value);
  data.append("treble", $("treble").value);
  data.append("presence", $("presence").value);
  data.append("compression", $("compression").value);
  data.append("profile", profile);

  // Envia o estilo musical selecionado ao backend.
  data.append("style", style);

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
  const text = $("progressText");
  const pct = $("progressPct");
  const bar = document.querySelector(".progress span");

  setVisible(wrap, true);

  if (text) {
    text.textContent = message;
  }

  if (pct) {
    pct.textContent = `${Math.round(percent)}%`;
  }

  if (bar) {
    bar.style.width =
      `${Math.max(0, Math.min(100, percent))}%`;
  }
}

function getStyleName(style) {
  const names = {
    natural: "Natural",
    trap: "Trap",
    rap: "Rap / Hip-Hop",
    drill: "Drill",
    rnb: "R&B",
    afrobeat: "Afrobeat",
    pop: "Pop"
  };

  return names[style] || "Natural";
}

function createVersionCard(version) {
  const card = document.createElement("article");
  card.className = "version-card";

  const heading = document.createElement("h3");
  heading.textContent = version.title;

  const description = document.createElement("p");
  description.textContent = version.description;

  const audio = document.createElement("audio");
  audio.controls = true;
  audio.preload = "metadata";
  audio.src = version.url;
  audio.style.width = "100%";

  const download = document.createElement("a");
  download.href = version.url;
  download.download = version.filename;
  download.className = "download-link";
  download.textContent = "Descarregar esta versão";

  card.append(heading, description, audio, download);

  return card;
}

function showVersions(versions) {
  const result = $("result");
  if (!result) return;

  result.replaceChildren();

  const heading = document.createElement("h2");
  heading.textContent = "Ouve e escolhe a tua versão";

  const description = document.createElement("p");
  description.textContent =
    "Compara as duas masterizações antes de descarregar.";

  const grid = document.createElement("div");
  grid.className = "versions-grid";

  versions.forEach((version) => {
    grid.appendChild(createVersionCard(version));
  });

  result.append(heading, description, grid);
  setVisible(result, true);
}

async function processVersion(profile, index) {
  const profileNames = {
    natural: "Natural Pro",
    modern: "Perfect Modern"
  };

  const style = selectedRadio("style", "natural");
  const styleName = getStyleName(style);

  setProgress(
    index === 1 ? 10 : 55,
    `A processar ${profileNames[profile]} · ${styleName}...`
  );

  const response = await fetch("/api/process", {
    method: "POST",
    body: makeFormData(profile)
  });

  if (!response.ok) {
    let message =
      `O servidor respondeu com o erro ${response.status}.`;

    try {
      const body = await response.json();

      if (body.detail) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch (_) {
      // Mantém a mensagem de erro padrão.
    }

    throw new Error(message);
  }

  const contentType =
    response.headers.get("content-type") || "";

  if (
    contentType.includes("application/json") ||
    contentType.includes("text/html")
  ) {
    throw new Error(
      "O servidor não devolveu um ficheiro de áudio válido."
    );
  }

  const blob = await response.blob();

  if (!blob.size) {
    throw new Error("O servidor devolveu um áudio vazio.");
  }

  const extension = selectedRadio("format", "wav");
  const url = URL.createObjectURL(blob);

  return {
    title: `${profileNames[profile]} · ${styleName}`,
    description:
      profile === "natural"
        ? `Perfil natural com ajustes para ${styleName}.`
        : `Perfil moderno com ajustes para ${styleName}.`,
    blob,
    url,
    filename: `levi-master-${style}-${profile}.${extension}`
  };
}

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (isProcessing) return;

    clearError();

    const result = $("result");

    if (result) {
      result.replaceChildren();
      setVisible(result, false);
    }

    try {
      validateFiles();
    } catch (error) {
      showError(error.message);
      return;
    }

    isProcessing = true;

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "A preparar áudio...";
    }

    const versions = [];

    try {
      setProgress(5, "A enviar os ficheiros para o servidor...");

      versions.push(await processVersion("natural", 1));

      setProgress(
        55,
        "Primeira versão concluída. A preparar a segunda..."
      );

      versions.push(await processVersion("modern", 2));

      showVersions(versions);

      setProgress(
        100,
        "Concluído! Os teus áudios estão prontos."
      );
    } catch (error) {
      versions.forEach((version) => {
        URL.revokeObjectURL(version.url);
      });

      showError(
        error instanceof Error
          ? error.message
          : "Não foi possível processar o áudio."
      );

      const progressText = $("progressText");

      if (progressText) {
        progressText.textContent = "O processamento falhou.";
      }
    } finally {
      isProcessing = false;

      if (submitButton) {
        submitButton.disabled = false;
      }

      updateMode(currentMode);
    }
  });
} else {
  console.error(
    "Levi Master AI: formulário #form não encontrado no index.html."
  );
}

updateMode(currentMode);
