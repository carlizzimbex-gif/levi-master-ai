
const $ = (id) => document.getElementById(id);

const form = $("audioForm");
const modeButtons = document.querySelectorAll("[data-mode]");
const instrumentalInput = $("instrumental");
const vocalsInput = $("vocals");
const trackInput = $("track");

let currentMode = "master";
let currentResults = [];

function showError(message) {
  const error = $("error");
  if (error) {
    error.textContent = message;
    error.hidden = false;
  }
}

function clearError() {
  const error = $("error");
  if (error) {
    error.textContent = "";
    error.hidden = true;
  }
}

function setText(id, value) {
  const element = $(id);
  if (element) element.textContent = value;
}

function selectedRadio(name, fallback) {
  const selected = document.querySelector(`input[name="${name}"]:checked`);
  return selected ? selected.value : fallback;
}

function updateMode(mode) {
  currentMode = mode;

  modeButtons.forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  const mixFields = $("mixFields");
  const masterFields = $("masterFields");

  if (mixFields) mixFields.hidden = mode !== "mix";
  if (masterFields) masterFields.hidden = mode !== "master";

  const instrumentalRequired = mode === "mix";
  if (instrumentalInput) instrumentalInput.required = instrumentalRequired;
  if (vocalsInput) vocalsInput.required = instrumentalRequired;
  if (trackInput) trackInput.required = mode === "master";

  const submit = $("submit");
  if (submit) {
    submit.textContent =
      mode === "mix" ? "Misturar e masterizar" : "Masterizar áudio";
  }
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => updateMode(button.dataset.mode));
});

function connectRange(inputId, outputId, suffix = "") {
  const input = $(inputId);
  const output = $(outputId);
  if (!input || !output) return;

  const update = () => {
    output.textContent = `${input.value}${suffix}`;
  };

  input.addEventListener("input", update);
  update();
}

connectRange("vocalGain", "gainValue", " dB");
connectRange("lufs", "lufsValue", " LUFS");
connectRange("bass", "bassValue", " dB");
connectRange("treble", "trebleValue", " dB");
connectRange("presence", "presenceValue", " dB");
connectRange("compression", "compressionValue");

function showFileName(input, outputId) {
  const output = $(outputId);
  if (!input || !output) return;

  input.addEventListener("change", () => {
    output.textContent = input.files?.[0]?.name || "Nenhum ficheiro selecionado";
  });
}

showFileName(instrumentalInput, "instrumentalName");
showFileName(vocalsInput, "vocalsName");
showFileName(trackInput, "trackName");

function getAudioFile(mode) {
  if (mode === "mix") {
    if (!instrumentalInput?.files?.[0] || !vocalsInput?.files?.[0]) {
      throw new Error("Seleciona o instrumental e a voz antes de continuar.");
    }
  } else if (!trackInput?.files?.[0]) {
    throw new Error("Seleciona um ficheiro de áudio para masterizar.");
  }
}

function makeFormData(profile) {
  const data = new FormData();

  data.append("mode", currentMode);
  data.append("output_format", selectedRadio("format", "wav"));
  data.append("target_lufs", $("lufs")?.value || "-14");
  data.append("vocal_gain", $("vocalGain")?.value || "0");

  data.append("bass", $("bass")?.value || "0");
  data.append("treble", $("treble")?.value || "0");
  data.append("presence", $("presence")?.value || "0");
  data.append("compression", $("compression")?.value || "4");
  data.append("profile", profile);

  if (currentMode === "mix") {
    data.append("instrumental", instrumentalInput.files[0]);
    data.append("vocals", vocalsInput.files[0]);
  } else {
    data.append("track", trackInput.files[0]);
  }

  return data;
}

function createVersionCard(title, description, blob, filename) {
  const container = document.createElement("article");
  container.className = "version-card";

  const heading = document.createElement("h3");
  heading.textContent = title;

  const detail = document.createElement("p");
  detail.textContent = description;

  const audio = document.createElement("audio");
  audio.controls = true;
  audio.preload = "metadata";

  const url = URL.createObjectURL(blob);
  audio.src = url;

  const download = document.createElement("a");
  download.href = url;
  download.download = filename;
  download.className = "download-link";
  download.textContent = "Descarregar esta versão";

  container.append(heading, detail, audio, download);
  return container;
}

function showVersions(versions) {
  const result = $("result");
  if (!result) return;

  result.replaceChildren();

  const heading = document.createElement("h2");
  heading.textContent = "Ouve e escolhe a tua versão";

  const description = document.createElement("p");
  description.textContent =
    "Compara as duas masterizações e descarrega a tua favorita.";

  const cards = document.createElement("div");
  cards.className = "versions-grid";

  versions.forEach((version) => {
    cards.appendChild(
      createVersionCard(
        version.title,
        version.description,
        version.blob,
        version.filename
      )
    );
  });

  result.append(heading, description, cards);
  result.hidden = false;
}

async function processVersion(profile, index, total) {
  const progress = $("progress");
  const progressText = $("progressText");

  if (progress) {
    progress.hidden = false;
    progress.max = total;
    progress.value = index;
  }

  if (progressText) {
    progressText.textContent =
      `A processar versão ${index} de ${total}...`;
  }

  const response = await fetch("/api/process", {
    method: "POST",
    body: makeFormData(profile),
  });

  if (!response.ok) {
    let message = `Erro do servidor (${response.status}).`;

    try {
      const body = await response.json();
      if (body.detail) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch (_) {
      // Mantém a mensagem padrão.
    }

    throw new Error(message);
  }

  const blob = await response.blob();

  const extension = selectedRadio("format", "wav") === "mp3" ? "mp3" : "wav";

  return {
    title: profile === "natural" ? "Natural Pro" : "Perfect Modern",
    description:
      profile === "natural"
        ? "Processamento subtil para preservar o carácter original."
        : "Processamento mais presente e moderno, com maior controlo dinâmico.",
    blob,
    filename: `levi-master-${profile}.${extension}`,
  };
}

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    try {
      getAudioFile(currentMode);
    } catch (error) {
      showError(error.message);
      return;
    }

    const submit = $("submit");
    const progress = $("progress");
    const progressText = $("progressText");
    const result = $("result");

    currentResults = [];
    if (result) {
      result.replaceChildren();
      result.hidden = true;
    }

    if (submit) {
      submit.disabled = true;
      submit.textContent = "A processar...";
    }

    if (progress) {
      progress.hidden = false;
      progress.max = 2;
      progress.value = 0;
    }

    try {
      const natural = await processVersion("natural", 1, 2);
      currentResults.push(natural);

      const modern = await processVersion("modern", 2, 2);
      currentResults.push(modern);

      showVersions(currentResults);

      if (progressText) {
        progressText.textContent = "Concluído! Compara as duas versões.";
      }
      if (progress) progress.value = 2;
    } catch (error) {
      showError(
        error instanceof Error
          ? error.message
          : "Não foi possível processar o áudio."
      );
      if (progressText) progressText.textContent = "O processamento falhou.";
    } finally {
      if (submit) {
        submit.disabled = false;
        submit.textContent =
          currentMode === "mix" ? "Misturar e masterizar" : "Masterizar áudio";
      }
    }
  });
}

updateMode(currentMode);
