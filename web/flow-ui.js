const state = {
  queried: false,
  loading: false,
  mails: [],
  currentPage: 1,
  pageSize: 10,
  selectedMailIds: new Set(),
  focusedMailId: null,
  downloadedFiles: [],
  selectedFileIds: new Set(),
  analysis: null,
};

const queryForm = document.querySelector("#queryForm");
const queryButton = queryForm.querySelector("button[type='submit']");
const resetButton = document.querySelector("#resetButton");
const accountInput = document.querySelector("#accountInput");
const searchInput = document.querySelector("#searchInput");
const periodSelect = document.querySelector("#periodSelect");
const messageBar = document.querySelector("#messageBar");
const queryStatus = document.querySelector("#queryStatus");
const selectAllButton = document.querySelector("#selectAllButton");
const downloadButton = document.querySelector("#downloadButton");
const convertSelectedButton = document.querySelector("#convertSelectedButton");
const analyzeSelectedButton = document.querySelector("#analyzeSelectedButton");
const mailEmpty = document.querySelector("#mailEmpty");
const mailTableShell = document.querySelector("#mailTableShell");
const mailRows = document.querySelector("#mailRows");
const mailPagination = document.querySelector("#mailPagination");
const prevPageButton = document.querySelector("#prevPageButton");
const nextPageButton = document.querySelector("#nextPageButton");
const pageButtons = document.querySelector("#pageButtons");
const detailEmpty = document.querySelector("#detailEmpty");
const mailDetail = document.querySelector("#mailDetail");
const detailSubject = document.querySelector("#detailSubject");
const detailFrom = document.querySelector("#detailFrom");
const detailDate = document.querySelector("#detailDate");
const detailBody = document.querySelector("#detailBody");
const detailAttachments = document.querySelector("#detailAttachments");
const downloadEmpty = document.querySelector("#downloadEmpty");
const downloadList = document.querySelector("#downloadList");
const downloadStatus = document.querySelector("#downloadStatus");
const csvEmpty = document.querySelector("#csvEmpty");
const csvList = document.querySelector("#csvList");
const analysisEmpty = document.querySelector("#analysisEmpty");
const analysisContent = document.querySelector("#analysisContent");
const analysisSummary = document.querySelector("#analysisSummary");
const wordCloud = document.querySelector("#wordCloud");
const frequencyRows = document.querySelector("#frequencyRows");
const headerMeta = document.querySelector(".header-meta");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "요청 처리 중 오류가 발생했습니다.");
  }
  return data;
}

function showMessage(message, type = "info") {
  if (!message) {
    messageBar.className = "message-bar hidden";
    messageBar.textContent = "";
    return;
  }
  messageBar.className = `message-bar ${type}`;
  messageBar.textContent = message;
}

function fileId(file) {
  return file.id || file.relativePath || file.name;
}

function totalPages() {
  return Math.max(1, Math.ceil(state.mails.length / state.pageSize));
}

function visibleMails() {
  const start = (state.currentPage - 1) * state.pageSize;
  return state.mails.slice(start, start + state.pageSize);
}

function currentPageMailIds() {
  return visibleMails().map((mail) => mail.id);
}

function renderHeaderMeta() {
  const convertedCount = state.downloadedFiles.filter((file) => file.converted).length;
  const analysisCount = state.analysis?.totalWords || 0;
  headerMeta.innerHTML = `
    <span>조회 ${state.queried ? state.mails.length : 0}건</span>
    <span>다운로드 ${state.downloadedFiles.length}건</span>
    <span>CSV ${convertedCount}건</span>
    <span>분석 ${analysisCount}단어</span>
  `;
}

function renderMailRows() {
  mailRows.innerHTML = visibleMails()
    .map((mail) => {
      const checked = state.selectedMailIds.has(mail.id) ? "checked" : "";
      const active = state.focusedMailId === mail.id ? " active" : "";
      const pdfCount = mail.attachments.filter((attachment) => attachment.isPdf).length;
      return `
        <tr class="mail-row${active}" data-mail-id="${escapeHtml(mail.id)}">
          <td>
            <input type="checkbox" aria-label="${escapeHtml(mail.subject)} 선택" ${checked} />
          </td>
          <td>${escapeHtml(mail.receivedAt)}</td>
          <td>${escapeHtml(mail.from)}</td>
          <td class="subject-cell">${escapeHtml(mail.subject)}</td>
          <td><span class="attachment-chip">${pdfCount} PDF</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderPagination() {
  const hasRows = state.queried && state.mails.length > 0;
  const pageCount = totalPages();
  mailPagination.classList.toggle("hidden", !hasRows);
  prevPageButton.disabled = state.currentPage <= 1 || state.loading;
  nextPageButton.disabled = state.currentPage >= pageCount || state.loading;

  pageButtons.innerHTML = Array.from({ length: pageCount }, (_, index) => {
    const page = index + 1;
    const active = page === state.currentPage ? " active" : "";
    return `<button class="page-button${active}" type="button" data-page="${page}" aria-label="${page}페이지">${page}</button>`;
  }).join("");
}

function renderMailArea() {
  const hasRows = state.queried && state.mails.length > 0;
  const pageIds = currentPageMailIds();
  const isCurrentPageSelected = pageIds.length > 0 && pageIds.every((id) => state.selectedMailIds.has(id));
  mailEmpty.classList.toggle("hidden", hasRows);
  mailTableShell.classList.toggle("hidden", !hasRows);
  selectAllButton.disabled = !hasRows || state.loading;
  downloadButton.disabled = state.selectedMailIds.size === 0 || state.loading;
  queryButton.disabled = state.loading;
  selectAllButton.textContent = isCurrentPageSelected ? "현재 페이지 전체 해제" : "현재 페이지 전체 선택";
  queryStatus.textContent = state.loading ? "처리 중..." : state.queried ? `${state.mails.length}건 조회됨 · ${state.currentPage}/${totalPages()}페이지` : "대기";

  if (hasRows) {
    renderMailRows();
  }
  renderPagination();
}

function renderDetail() {
  const mail = state.mails.find((item) => item.id === state.focusedMailId);
  detailEmpty.classList.toggle("hidden", Boolean(mail));
  mailDetail.classList.toggle("hidden", !mail);

  if (!mail) {
    return;
  }

  detailSubject.textContent = mail.subject;
  detailFrom.textContent = mail.from;
  detailDate.textContent = mail.receivedAt;
  detailBody.textContent = mail.body || "본문 미리보기가 없습니다.";
  detailAttachments.innerHTML = mail.attachments.length
    ? mail.attachments
        .map(
          (attachment) => `
            <li>
              <span>${escapeHtml(attachment.name)}</span>
              <small>${escapeHtml(attachment.sizeLabel)}</small>
            </li>
          `,
        )
        .join("")
    : "<li><span>첨부파일 없음</span><small>-</small></li>";
}

function renderDownloadList() {
  const hasFiles = state.downloadedFiles.length > 0;
  downloadEmpty.classList.toggle("hidden", hasFiles);
  downloadList.classList.toggle("hidden", !hasFiles);
  downloadStatus.textContent = `${state.downloadedFiles.length}건`;

  downloadList.innerHTML = state.downloadedFiles
    .map((file) => {
      const id = fileId(file);
      return `
        <article class="file-card">
          <input type="checkbox" data-file-id="${escapeHtml(id)}" ${state.selectedFileIds.has(id) ? "checked" : ""} aria-label="${escapeHtml(file.name)} CSV 변환 선택" />
          <div>
            <h3>${escapeHtml(file.name)}</h3>
            <p>${escapeHtml(file.sourceSubject || file.relativePath)}</p>
          </div>
          <span class="file-badge done">다운로드 완료</span>
        </article>
      `;
    })
    .join("");
}

function renderCsvList() {
  const hasFiles = state.downloadedFiles.length > 0;
  csvEmpty.classList.toggle("hidden", hasFiles);
  csvList.classList.toggle("hidden", !hasFiles);
  convertSelectedButton.disabled = state.selectedFileIds.size === 0 || state.loading;
  analyzeSelectedButton.disabled = state.selectedFileIds.size === 0 || state.loading;

  csvList.innerHTML = state.downloadedFiles
    .map((file) => {
      const id = fileId(file);
      const buttonText = file.converted ? "다시 변환" : "CSV 변환";
      const badgeClass = file.converted ? "done" : "pending";
      const badgeText = file.converted ? "CSV 생성 완료" : "변환 대기";
      const csvPath = file.converted ? `<p>${escapeHtml(file.reportPath || "result.csv")}에 반영됨</p>` : "<p>선택 후 변환할 수 있습니다.</p>";
      return `
        <article class="file-card ${file.converted ? "converted" : ""}">
          <input type="checkbox" data-file-id="${escapeHtml(id)}" ${state.selectedFileIds.has(id) ? "checked" : ""} aria-label="${escapeHtml(file.name)} CSV 변환 선택" />
          <div>
            <h3>${escapeHtml(file.name)}</h3>
            ${csvPath}
          </div>
          <button class="secondary-button" type="button" data-convert-file="${escapeHtml(id)}" ${state.loading ? "disabled" : ""}>${buttonText}</button>
          <span class="file-badge ${badgeClass}">${badgeText}</span>
        </article>
      `;
    })
    .join("");
}

function renderResults() {
  renderDownloadList();
  renderCsvList();
}

function renderAnalysis() {
  const hasAnalysis = Boolean(state.analysis);
  analysisEmpty.classList.toggle("hidden", hasAnalysis);
  analysisContent.classList.toggle("hidden", !hasAnalysis);

  if (!state.analysis) {
    return;
  }

  const topWords = state.analysis.topWords || [];
  const cloudWords = state.analysis.wordCloud || topWords;
  const cloudImage = state.analysis.wordCloudImage || "";
  analysisSummary.innerHTML = `
    <span>분석 파일 ${state.analysis.fileCount}개</span>
    <span>총 단어 ${state.analysis.totalWords}개</span>
    <span>고유 단어 ${state.analysis.uniqueWords}개</span>
  `;

  wordCloud.classList.toggle("image-mode", Boolean(cloudImage));
  wordCloud.innerHTML = cloudImage
    ? `<img class="cloud-image" src="${escapeHtml(cloudImage)}" alt="워드클라우드 이미지" />`
    : cloudWords.slice(0, 35).map((item) => {
        const size = Number(item.sizeRem || 1);
        const color = item.color || "#2563a8";
        return `<span class="cloud-word" style="--cloud-size: ${size.toFixed(2)}rem; --cloud-color: ${escapeHtml(color)};" title="${escapeHtml(item.word)} ${item.count}회">${escapeHtml(item.word)}</span>`;
      }).join("");

  frequencyRows.innerHTML = topWords.slice(0, 50).map((item, index) => `
    <tr>
      <td>${index + 1}</td>
      <td>${escapeHtml(item.word)}</td>
      <td>${item.count}</td>
    </tr>
  `).join("");
}

function render() {
  renderHeaderMeta();
  renderMailArea();
  renderDetail();
  renderResults();
  renderAnalysis();
}

function resetState({ keepConfig = true } = {}) {
  state.queried = false;
  state.loading = false;
  state.mails = [];
  state.currentPage = 1;
  state.selectedMailIds.clear();
  state.focusedMailId = null;
  state.downloadedFiles = [];
  state.selectedFileIds.clear();
  state.analysis = null;
  if (!keepConfig) {
    accountInput.value = "";
  }
  showMessage("");
  render();
}

function focusMail(mailId) {
  state.focusedMailId = mailId;
  render();
}

function toggleMailSelection(mailId, selected) {
  if (selected) {
    state.selectedMailIds.add(mailId);
    state.focusedMailId = mailId;
  } else {
    state.selectedMailIds.delete(mailId);
  }
  render();
}

function mergeDownloadedFiles(files) {
  files.forEach((file) => {
    const nextFile = {
      ...file,
      id: file.id || file.relativePath || file.name,
      converted: false,
    };
    const existingIndex = state.downloadedFiles.findIndex((item) => fileId(item) === fileId(nextFile));
    if (existingIndex === -1) {
      state.downloadedFiles.push(nextFile);
    } else {
      state.downloadedFiles[existingIndex] = {
        ...state.downloadedFiles[existingIndex],
        ...nextFile,
        converted: state.downloadedFiles[existingIndex].converted,
      };
    }
    state.selectedFileIds.add(fileId(nextFile));
  });
  state.analysis = null;
}

async function loadConfig() {
  try {
    const config = await apiRequest("/api/config");
    accountInput.value = config.emailAddress || "";
  } catch (error) {
    if (window.location.protocol === "file:") {
      accountInput.value = "서버 접속 필요";
      showMessage("HTML 파일을 직접 열면 실제 메일 API를 사용할 수 없습니다. http://127.0.0.1:8000 주소로 접속하세요.", "error");
      return;
    }

    accountInput.value = "메일 설정 필요";
    showMessage(`메일 설정 또는 서버 상태를 확인하세요. ${error.message}`, "error");
  }
}

async function queryMails() {
  state.loading = true;
  state.queried = true;
  state.mails = [];
  state.currentPage = 1;
  state.selectedMailIds.clear();
  state.focusedMailId = null;
  state.downloadedFiles = [];
  state.selectedFileIds.clear();
  state.analysis = null;
  showMessage("메일함을 조회하는 중입니다.");
  render();

  const params = new URLSearchParams({
    query: searchInput.value.trim(),
    period: periodSelect.value,
  });

  try {
    const data = await apiRequest(`/api/mail?${params.toString()}`);
    state.mails = data.mails || [];
    state.focusedMailId = state.mails[0]?.id || null;
    state.currentPage = 1;
    showMessage(`${state.mails.length}건의 메일을 조회했습니다.`, state.mails.length ? "success" : "info");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function downloadSelectedMails() {
  state.loading = true;
  showMessage("선택한 메일의 PDF 첨부파일을 다운로드하는 중입니다.");
  render();

  try {
    const data = await apiRequest("/api/download", {
      method: "POST",
      body: JSON.stringify({
        mailIds: Array.from(state.selectedMailIds),
      }),
    });
    mergeDownloadedFiles(data.files || []);
    showMessage(`${data.files?.length || 0}개의 PDF를 다운로드했습니다.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function convertFiles(fileIds) {
  state.loading = true;
  showMessage("선택한 PDF를 CSV로 변환하는 중입니다.");
  render();

  try {
    const data = await apiRequest("/api/convert", {
      method: "POST",
      body: JSON.stringify({
        files: Array.from(fileIds),
      }),
    });
    const convertedIds = new Set(data.convertedFiles || []);
    state.downloadedFiles = state.downloadedFiles.map((file) => {
      const id = fileId(file);
      if (convertedIds.has(id)) {
        return {
          ...file,
          converted: true,
          reportPath: data.reportPath || "result.csv",
        };
      }
      return file;
    });
    showMessage(`${convertedIds.size}개의 PDF를 CSV 리포트로 변환했습니다.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function analyzeFiles(fileIds) {
  state.loading = true;
  showMessage("선택한 PDF의 단어를 분석하는 중입니다.");
  render();

  try {
    const data = await apiRequest("/api/analyze", {
      method: "POST",
      body: JSON.stringify({
        files: Array.from(fileIds),
      }),
    });
    state.analysis = data.analysis;
    showMessage(`${data.analysis.fileCount}개 PDF의 단어 분석을 완료했습니다.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

queryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  queryMails();
});

resetButton.addEventListener("click", () => {
  resetState();
});

selectAllButton.addEventListener("click", () => {
  const pageIds = currentPageMailIds();
  const shouldSelectAll = pageIds.some((id) => !state.selectedMailIds.has(id));
  if (shouldSelectAll) {
    pageIds.forEach((id) => state.selectedMailIds.add(id));
    state.focusedMailId = pageIds[0] || null;
  } else {
    pageIds.forEach((id) => state.selectedMailIds.delete(id));
  }
  render();
});

downloadButton.addEventListener("click", downloadSelectedMails);

convertSelectedButton.addEventListener("click", () => {
  convertFiles(new Set(state.selectedFileIds));
});

analyzeSelectedButton.addEventListener("click", () => {
  analyzeFiles(new Set(state.selectedFileIds));
});

prevPageButton.addEventListener("click", () => {
  state.currentPage = Math.max(1, state.currentPage - 1);
  render();
});

nextPageButton.addEventListener("click", () => {
  state.currentPage = Math.min(totalPages(), state.currentPage + 1);
  render();
});

pageButtons.addEventListener("click", (event) => {
  const button = event.target.closest("[data-page]");
  if (!button) {
    return;
  }
  state.currentPage = Number(button.dataset.page);
  render();
});

mailRows.addEventListener("click", (event) => {
  const row = event.target.closest(".mail-row");
  if (!row) {
    return;
  }

  const mailId = row.dataset.mailId;
  const checkbox = row.querySelector("input[type='checkbox']");
  if (event.target === checkbox) {
    toggleMailSelection(mailId, checkbox.checked);
    return;
  }

  focusMail(mailId);
});

downloadList.addEventListener("change", (event) => {
  const checkbox = event.target.closest("input[type='checkbox']");
  if (!checkbox) {
    return;
  }

  if (checkbox.checked) {
    state.selectedFileIds.add(checkbox.dataset.fileId);
  } else {
    state.selectedFileIds.delete(checkbox.dataset.fileId);
  }
  state.analysis = null;
  render();
});

csvList.addEventListener("change", (event) => {
  const checkbox = event.target.closest("input[type='checkbox']");
  if (!checkbox) {
    return;
  }

  if (checkbox.checked) {
    state.selectedFileIds.add(checkbox.dataset.fileId);
  } else {
    state.selectedFileIds.delete(checkbox.dataset.fileId);
  }
  state.analysis = null;
  render();
});

csvList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-convert-file]");
  if (!button) {
    return;
  }
  convertFiles(new Set([button.dataset.convertFile]));
});

render();
loadConfig();
