const fileInput = document.querySelector("#fileInput");
const pickButton = document.querySelector("#pickButton");
const parseButton = document.querySelector("#parseButton");
const downloadButton = document.querySelector("#downloadButton");
const dropZone = document.querySelector("#dropZone");
const fileName = document.querySelector("#fileName");
const errorBox = document.querySelector("#error");
const result = document.querySelector("#result");
const projectName = document.querySelector("#projectName");
const gearRows = document.querySelector("#gearRows");
const ampRows = document.querySelector("#ampRows");
const gearCount = document.querySelector("#gearCount");
const ampCount = document.querySelector("#ampCount");

let selectedFile = null;

pickButton.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => selectFile(fileInput.files.item(0)));
parseButton.addEventListener("click", parseSelectedFile);
downloadButton.addEventListener("click", downloadTextFile);

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
  selectFile(event.dataTransfer.files.item(0));
});

function selectFile(file) {
  selectedFile = file;
  hideError();
  result.hidden = true;
  fileName.textContent = file ? file.name : "Brak pliku";
  parseButton.disabled = !file;
}

async function parseSelectedFile() {
  if (!selectedFile) return;

  parseButton.disabled = true;
  parseButton.textContent = "Parsowanie...";
  hideError();

  try {
    const response = await fetch("/api/parse", {
      method: "POST",
      body: formDataWithFile(),
    });

    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }

    renderResult(await response.json());
  } catch (error) {
    showError(error.message);
  } finally {
    parseButton.disabled = !selectedFile;
    parseButton.textContent = "Parsuj";
  }
}

async function downloadTextFile() {
  if (!selectedFile) return;

  try {
    const response = await fetch("/api/equipment.txt", {
      method: "POST",
      body: formDataWithFile(),
    });

    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${baseName(selectedFile.name)}-lista-sprzetu.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    showError(error.message);
  }
}

function renderResult(data) {
  projectName.textContent = data.project_name;
  renderTable(gearRows, data.gear, ["model", "quantity"]);
  renderTable(ampRows, data.amps, ["model", "quantity", "ids"]);

  const totalGear = data.gear.reduce((sum, row) => sum + row.quantity, 0);
  const totalAmps = data.amps.reduce((sum, row) => sum + row.quantity, 0);
  gearCount.textContent = `${totalGear} szt.`;
  ampCount.textContent = `${totalAmps} szt.`;
  result.hidden = false;
}

function renderTable(tbody, rows, columns) {
  tbody.replaceChildren();

  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const column of columns) {
      const td = document.createElement("td");
      if (column === "model") td.className = "model";
      if (column === "quantity") td.className = "qty";
      td.textContent = Array.isArray(row[column]) ? row[column].join(", ") : row[column];
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

function formDataWithFile() {
  const body = new FormData();
  body.append("file", selectedFile);
  return body;
}

async function errorMessage(response) {
  const body = await response.json().catch(() => null);
  return body?.detail || `Błąd HTTP ${response.status}`;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.textContent = "";
  errorBox.hidden = true;
}

function baseName(name) {
  return name.replace(/\.[^.]+$/, "") || "dbpr";
}
