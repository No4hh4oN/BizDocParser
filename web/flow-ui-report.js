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
  analysisFileId: null,
  expandedStaffEvalFileId: null,
  convertingFileIds: new Set(),
  analyzingFileIds: new Set(),
  evaluatingFileIds: new Set(),
  staffModelByFile: {},
  staffModelOptions: [],
};

const STAFF_MODEL_OPTIONS = ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o1", "o3", "o4-mini"];

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
const analysisActionEmpty = document.querySelector("#analysisActionEmpty");
const analysisList = document.querySelector("#analysisList");
const analysisModal = document.querySelector("#analysisModal");
const analysisModalTitle = document.querySelector("#analysisModalTitle");
const analysisModalClose = document.querySelector("#analysisModalClose");
const downloadCloudImage = document.querySelector("#downloadCloudImage");
const downloadFrequencyCsv = document.querySelector("#downloadFrequencyCsv");
const analysisSummary = document.querySelector("#analysisSummary");
const wordCloud = document.querySelector("#wordCloud");
const frequencyRows = document.querySelector("#frequencyRows");
const headerMeta = document.querySelector(".header-meta");
const staffEvalActionEmpty = document.querySelector("#staffEvalActionEmpty");
const staffEvalList = document.querySelector("#staffEvalList");

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
  if (!message || type !== "error") {
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

function findDownloadedFileById(id) {
  return state.downloadedFiles.find((file) => fileId(file) === id) || null;
}

function pickConvertibleFileIds(fileIds) {
  return Array.from(fileIds).filter((id) => {
    const file = findDownloadedFileById(id);
    return Boolean(file) && !file.converted && !state.convertingFileIds.has(id);
  });
}

function ensureStaffModel(fileIdValue) {
  const options = state.staffModelOptions.length ? state.staffModelOptions : STAFF_MODEL_OPTIONS;
  if (!state.staffModelByFile[fileIdValue]) {
    state.staffModelByFile[fileIdValue] = options[0];
  } else if (!options.includes(state.staffModelByFile[fileIdValue])) {
    state.staffModelByFile[fileIdValue] = options[0];
  }
  return state.staffModelByFile[fileIdValue];
}

function renderStaffModelOptions(selectedModel) {
  const options = state.staffModelOptions.length ? state.staffModelOptions : STAFF_MODEL_OPTIONS;
  return options.map((model) => {
    const selected = model === selectedModel ? "selected" : "";
    return `<option value="${escapeHtml(model)}" ${selected}>${escapeHtml(model)}</option>`;
  }).join("");
}

function triggerTextDownload(fileName, content, contentType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
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
  const analysisCount = state.downloadedFiles.filter((file) => Boolean(file.analysisData)).length;
  headerMeta.innerHTML = `
    <span>조회 ${state.queried ? state.mails.length : 0}건</span>
    <span>다운로드 ${state.downloadedFiles.length}건</span>
    <span>보고서 ${convertedCount}건</span>
    <span>분석 ${analysisCount}건</span>
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
          <input type="checkbox" data-file-id="${escapeHtml(id)}" ${state.selectedFileIds.has(id) ? "checked" : ""} aria-label="${escapeHtml(file.name)} 보고서 생성 선택" />
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
  const selectedConvertibleCount = pickConvertibleFileIds(state.selectedFileIds).length;
  convertSelectedButton.disabled = selectedConvertibleCount === 0 || state.loading || state.convertingFileIds.size > 0;

  csvList.innerHTML = state.downloadedFiles
    .map((file) => {
      const id = fileId(file);
      const isConverting = state.convertingFileIds.has(id);
      const badgeClass = file.converted ? "done" : isConverting ? "pending" : "pending";
      const badgeText = file.converted ? "보고서 생성 완료" : isConverting ? "생성 중" : "생성 대기";
      const csvPath = file.converted
        ? `<p class="path-text">${escapeHtml(file.reportPath || "")}</p>`
        : "<p>선택 후 임원 보고서를 생성할 수 있습니다.</p>";
      const convertButton = file.converted
        ? ""
        : `<button class="secondary-button" type="button" data-convert-file="${escapeHtml(id)}" ${isConverting ? "disabled" : ""}>${isConverting ? "보고서 생성 중..." : "보고서 생성"}</button>`;
      const reportDownloadButton = file.reportPath
        ? `<button class="secondary-button" type="button" data-download-report="${escapeHtml(file.reportPath)}">보고서 다운로드</button>`
        : "";
      return `
        <article class="file-card ${file.converted ? "converted" : ""}">
          <input type="checkbox" data-file-id="${escapeHtml(id)}" ${state.selectedFileIds.has(id) ? "checked" : ""} aria-label="${escapeHtml(file.name)} 보고서 생성 선택" />
          <div>
            <h3>${escapeHtml(file.name)}</h3>
            ${csvPath}
          </div>
          ${convertButton}
          ${reportDownloadButton}
          <span class="file-badge ${badgeClass}">${badgeText}</span>
        </article>
      `;
    })
    .join("");
}

function renderStaffEvaluationList() {
  const hasFiles = state.downloadedFiles.length > 0;
  staffEvalActionEmpty.classList.toggle("hidden", hasFiles);
  staffEvalList.classList.toggle("hidden", !hasFiles);

  if (!hasFiles) {
    return;
  }

  staffEvalList.innerHTML = state.downloadedFiles
    .map((file) => {
      const id = fileId(file);
      const canEvaluate = file.converted;
      const isEvaluating = state.evaluatingFileIds.has(id);
      const selectedModel = ensureStaffModel(id);
      const modelSelect = `<select id="staffModel_${escapeHtml(id)}" class="model-select" data-staff-model-file="${escapeHtml(id)}" ${canEvaluate ? "" : "disabled"}>
        ${renderStaffModelOptions(selectedModel)}
      </select>`;
      const evalButton = canEvaluate
        ? `<button class="secondary-button" type="button" data-evaluate-file="${escapeHtml(id)}" ${isEvaluating ? "disabled" : ""}>${isEvaluating ? "작업 가능 인원 분석 중..." : "작업 가능 인원 분석"}</button>`
        : `<button class="secondary-button" type="button" disabled>보고서 생성 후 분석 가능</button>`;
      const viewButton = file.staffResultPath
        ? `<button class="secondary-button" type="button" data-view-staff="${escapeHtml(id)}">${state.expandedStaffEvalFileId === id ? "결과 접기" : "결과 보기"}</button>`
        : "";
      const downloadButton = file.staffResultPath
        ? `<button class="secondary-button" type="button" data-download-staff="${escapeHtml(file.staffResultPath)}">결과 다운로드</button>`
        : "";
      const pathText = file.staffResultPath
        ? `<p class="path-text">${escapeHtml(file.staffResultPath)}</p>`
        : "<p>문서별 참여판단을 실행하세요.</p>";
      const secondaryActions = viewButton || downloadButton
        ? `<div class="staff-eval-secondary">${viewButton}${downloadButton}</div>`
        : "";
      const resultPanel =
        file.staffResultData && state.expandedStaffEvalFileId === id
          ? renderInlineStaffEvaluationResult(file.staffResultData)
          : "";
      return `
        <article class="file-card staff-eval-card ${file.staffResultPath ? "converted" : ""}">
          <div class="file-main">
            <h3>${escapeHtml(file.name)}</h3>
            ${pathText}
          </div>
          <div class="staff-eval-controls">
            ${modelSelect}
            ${evalButton}
          </div>
          ${secondaryActions}
          ${resultPanel}
        </article>
      `;
    })
    .join("");
}

function renderResults() {
  renderDownloadList();
  renderCsvList();
  renderStaffEvaluationList();
}

function renderAnalysisList() {
  const hasFiles = state.downloadedFiles.length > 0;
  analysisActionEmpty.classList.toggle("hidden", hasFiles);
  analysisList.classList.toggle("hidden", !hasFiles);

  if (!hasFiles) {
    return;
  }

  analysisList.innerHTML = state.downloadedFiles
    .map((file) => {
      const id = fileId(file);
      const isAnalyzing = state.analyzingFileIds.has(id);
      const analyzeButton = file.analysisData
        ? ""
        : `<button class="secondary-button" type="button" data-analyze-file="${escapeHtml(id)}" ${isAnalyzing ? "disabled" : ""}>${isAnalyzing ? "단어 분석 중..." : "단어 분석"}</button>`;
      const viewButton = file.analysisData
        ? `<button class="secondary-button" type="button" data-view-analysis="${escapeHtml(id)}">워드클라우드 결과 보기</button>`
        : "";
      const badgeClass = file.analysisData ? "done" : "pending";
      const badgeText = file.analysisData ? "분석 완료" : isAnalyzing ? "분석 중" : "분석 대기";
      return `
        <article class="file-card ${file.analysisData ? "converted" : ""}">
          <div class="file-main">
            <h3>${escapeHtml(file.name)}</h3>
            <p>${escapeHtml(file.analysisData ? "문서별 단어 분석 결과가 준비되었습니다." : "문서별 단어 분석을 실행하세요.")}</p>
          </div>
          ${analyzeButton}
          ${viewButton}
          <span class="file-badge ${badgeClass}">${badgeText}</span>
        </article>
      `;
    })
    .join("");
}

function renderAnalysis() {
  if (!analysisModal) {
    return;
  }
  const activeFile = findDownloadedFileById(state.analysisFileId || "");
  const active = activeFile?.analysisData || null;
  analysisModal.classList.toggle("hidden", !active);
  if (!active) {
    return;
  }

  const topWords = active.topWords || [];
  const cloudWords = active.wordCloud || topWords;
  const cloudImage = active.wordCloudImage || "";
  analysisModalTitle.textContent = `${activeFile?.name || "선택 문서"} 워드클라우드 결과`;
  analysisSummary.innerHTML = `
    <span>대상 파일 ${escapeHtml(activeFile?.name || "-")}</span>
    <span>전체 단어 ${active.totalWords || 0}개</span>
    <span>고유 단어 ${active.uniqueWords || 0}개</span>
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

function renderInlineStaffEvaluationResult(resultData) {
  const summary = resultData.evaluation_summary || {};
  const evaluations = resultData.employee_evaluations || [];
  const rows = evaluations
    .map((item) => {
      const roles = (item.suitable_roles || []).join(", ");
      return `
        <tr>
          <td>${escapeHtml(item.employee_id || "")}</td>
          <td>${escapeHtml(item.name || "")}</td>
          <td>${escapeHtml(item.label || "")}</td>
          <td>${escapeHtml(roles)}</td>
          <td>${escapeHtml(item.caution || "")}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="staff-eval-result-panel">
      <div class="analysis-summary">
        <span>전체 직원 ${summary.total_employees || 0}명</span>
        <span>핵심 가능 ${summary.core_role_possible_count || 0}명</span>
        <span>일부 가능 ${summary.partial_possible_count || 0}명</span>
        <span>불가 ${summary.not_available_count || 0}명</span>
      </div>
      <div class="frequency-table-wrap">
        <table class="frequency-table">
          <thead>
            <tr>
              <th scope="col">직원ID</th>
              <th scope="col">이름</th>
              <th scope="col">라벨</th>
              <th scope="col">적합 역할</th>
              <th scope="col">주의사항</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function render() {
  renderHeaderMeta();
  renderMailArea();
  renderDetail();
  renderResults();
  renderAnalysisList();
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
  state.analysisFileId = null;
  state.expandedStaffEvalFileId = null;
  state.convertingFileIds.clear();
  state.analyzingFileIds.clear();
  state.evaluatingFileIds.clear();
  state.staffModelByFile = {};
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
      reportPath: "",
      staffResultPath: "",
      staffResultData: null,
      analysisData: null,
    };
    const existingIndex = state.downloadedFiles.findIndex((item) => fileId(item) === fileId(nextFile));
    if (existingIndex === -1) {
      state.downloadedFiles.push(nextFile);
    } else {
      state.downloadedFiles[existingIndex] = {
        ...state.downloadedFiles[existingIndex],
        ...nextFile,
        converted: state.downloadedFiles[existingIndex].converted,
        reportPath: state.downloadedFiles[existingIndex].reportPath || "",
        staffResultPath: state.downloadedFiles[existingIndex].staffResultPath || "",
        staffResultData: state.downloadedFiles[existingIndex].staffResultData || null,
        analysisData: state.downloadedFiles[existingIndex].analysisData || null,
      };
    }
    state.selectedFileIds.add(fileId(nextFile));
    ensureStaffModel(fileId(nextFile));
  });
  state.analysis = null;
  state.analysisFileId = null;
  state.expandedStaffEvalFileId = null;
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
  state.analysisFileId = null;
  state.expandedStaffEvalFileId = null;
  state.convertingFileIds.clear();
  state.analyzingFileIds.clear();
  state.evaluatingFileIds.clear();
  state.staffModelByFile = {};
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
  showMessage("");
  render();

  try {
    const data = await apiRequest("/api/download", {
      method: "POST",
      body: JSON.stringify({
        mailIds: Array.from(state.selectedMailIds),
      }),
    });
    mergeDownloadedFiles(data.files || []);
    showMessage("");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function convertFiles(fileIds) {
  const targetIds = pickConvertibleFileIds(fileIds);
  if (!targetIds.length) {
    showMessage("선택한 파일은 모두 보고서 생성이 완료되었거나 생성 중입니다.", "info");
    render();
    return;
  }

  targetIds.forEach((id) => state.convertingFileIds.add(id));
  showMessage(`${targetIds.length}개의 PDF로 임원 보고서를 생성하는 중입니다.`);
  render();

  try {
    const data = await apiRequest("/api/convert", {
      method: "POST",
      body: JSON.stringify({
        files: targetIds,
      }),
    });
    const convertedIds = new Set(data.convertedFiles || []);
    const reportPathsByFile = data.reportPathsByFile || {};
    state.downloadedFiles = state.downloadedFiles.map((file) => {
      const id = fileId(file);
      if (convertedIds.has(id)) {
        return {
          ...file,
          converted: true,
          reportPath: reportPathsByFile[id] || data.reportPath || "",
          staffResultPath: "",
          staffResultData: null,
          analysisData: null,
        };
      }
      return file;
    });
    state.analysis = null;
    if (state.analysisFileId && convertedIds.has(state.analysisFileId)) {
      state.analysisFileId = null;
    }
    state.expandedStaffEvalFileId = null;
    showMessage(`${convertedIds.size}개의 PDF에 대해 임원 보고서를 생성했습니다.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    targetIds.forEach((id) => state.convertingFileIds.delete(id));
    render();
  }
}

async function loadOpenAIModels() {
  try {
    const data = await apiRequest("/api/openai-models");
    const models = Array.isArray(data.models) ? data.models.filter((item) => typeof item === "string" && item.trim()) : [];
    if (!models.length) {
      return;
    }
    state.staffModelOptions = models;
    Object.keys(state.staffModelByFile).forEach((fileKey) => {
      if (!state.staffModelOptions.includes(state.staffModelByFile[fileKey])) {
        state.staffModelByFile[fileKey] = state.staffModelOptions[0];
      }
    });
    render();
  } catch (error) {
    // 모델 목록 조회 실패 시 기본 목록 사용
  }
}

async function evaluateStaff(fileIds, modelOverride = null) {
  const targetId = Array.from(fileIds)[0];
  const file = findDownloadedFileById(targetId || "");
  if (!file) {
    showMessage("참여판단할 파일을 찾을 수 없습니다.", "error");
    return;
  }
  if (!file.converted) {
    showMessage("임원 보고서 생성 후 참여판단이 가능합니다.", "info");
    return;
  }
  if (file.staffResultPath || file.staffResultData) {
    const shouldReanalyze = window.confirm(
      "기존 참여판단 결과가 있습니다.\n먼저 기존 결과물을 다운로드 받으셨나요?\n새로 분석을 원하면 Yes, 분석을 취소하려면 No를 선택하세요.",
    );
    if (!shouldReanalyze) {
      return;
    }
  }

  const defaultModel = (state.staffModelOptions.length ? state.staffModelOptions[0] : STAFF_MODEL_OPTIONS[0]) || "gpt-5-mini";
  const selectedModel = (modelOverride || state.staffModelByFile[targetId] || defaultModel).trim();
  state.evaluatingFileIds.add(targetId);
  showMessage("");
  render();

  try {
    const payload = { files: [targetId], model: selectedModel };

    const data = await apiRequest("/api/staff-evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const evaluatedIds = new Set(data.evaluatedFiles || []);
    const resultPathsByFile = data.resultPathsByFile || {};
    const resultByFile = data.resultByFile || {};
    state.downloadedFiles = state.downloadedFiles.map((file) => {
      const id = fileId(file);
      if (!evaluatedIds.has(id)) {
        return file;
      }
      return {
        ...file,
        staffResultPath: resultPathsByFile[id] || data.resultPath || "",
        staffResultData: resultByFile[id] || null,
      };
    });
    state.expandedStaffEvalFileId = targetId;
    showMessage("");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.evaluatingFileIds.delete(targetId);
    render();
  }
}

function downloadGeneratedFile(relativePath) {
  if (!relativePath) {
    return;
  }
  window.open(`/api/download-file?path=${encodeURIComponent(relativePath)}`, "_blank");
}

function viewStaffEvaluationForFile(fileKey) {
  const file = state.downloadedFiles.find((item) => fileId(item) === fileKey);
  if (!file || !file.staffResultData) {
    showMessage("표시할 참여판단 결과가 없습니다. 먼저 분석을 실행하세요.", "info");
    return;
  }
  state.expandedStaffEvalFileId = state.expandedStaffEvalFileId === fileKey ? null : fileKey;
  render();
}

function viewAnalysisForFile(fileKey) {
  const file = findDownloadedFileById(fileKey);
  if (!file || !file.analysisData) {
    showMessage("표시할 워드클라우드 결과가 없습니다. 먼저 단어 분석을 실행하세요.", "info");
    return;
  }

  state.analysis = file.analysisData;
  state.analysisFileId = fileKey;
  render();
}

function closeAnalysisModal() {
  state.analysis = null;
  state.analysisFileId = null;
  render();
}

function downloadCurrentWordCloudImage() {
  const file = findDownloadedFileById(state.analysisFileId || "");
  const cloudImage = file?.analysisData?.wordCloudImage || "";
  if (!cloudImage) {
    showMessage("다운로드할 워드클라우드 이미지가 없습니다.", "info");
    return;
  }

  const anchor = document.createElement("a");
  anchor.href = cloudImage;
  anchor.download = `${(file?.name || "wordcloud").replace(/\.pdf$/i, "")}_wordcloud.png`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function downloadCurrentFrequencyCsv() {
  const file = findDownloadedFileById(state.analysisFileId || "");
  const topWords = file?.analysisData?.topWords || [];
  if (!topWords.length) {
    showMessage("다운로드할 단어 빈도 결과가 없습니다.", "info");
    return;
  }

  const lines = ["rank,word,count"];
  topWords.forEach((item, index) => {
    const word = String(item.word || "").replaceAll('"', '""');
    lines.push(`${index + 1},"${word}",${Number(item.count || 0)}`);
  });
  const fileName = `${(file?.name || "frequency").replace(/\.pdf$/i, "")}_word_frequency.csv`;
  triggerTextDownload(fileName, `${lines.join("\n")}\n`, "text/csv;charset=utf-8");
}

async function analyzeFiles(fileIds) {
  const targetId = Array.from(fileIds)[0];
  const file = findDownloadedFileById(targetId || "");
  if (!file) {
    showMessage("분석할 파일을 찾을 수 없습니다.", "error");
    return;
  }

  state.analyzingFileIds.add(targetId);
  showMessage(`${file.name} 단어를 분석하는 중입니다.`);
  render();

  try {
    const data = await apiRequest("/api/analyze", {
      method: "POST",
      body: JSON.stringify({
        files: [targetId],
      }),
    });
    const perFile = data.analysis?.perFile || [];
    const resolved = perFile[0] || data.analysis || null;
    if (!resolved) {
      throw new Error("분석 결과를 받지 못했습니다.");
    }

    state.downloadedFiles = state.downloadedFiles.map((item) => {
      const id = fileId(item);
      if (id !== targetId) {
        return item;
      }
      return {
        ...item,
        analysisData: {
          totalWords: resolved.totalWords || 0,
          uniqueWords: resolved.uniqueWords || 0,
          topWords: resolved.topWords || [],
          wordCloud: resolved.wordCloud || [],
          wordCloudImage: resolved.wordCloudImage || "",
        },
      };
    });
    showMessage(`${file.name} 단어 분석을 완료했습니다. 결과 보기 버튼으로 확인하세요.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    state.analyzingFileIds.delete(targetId);
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
  state.analysisFileId = null;
  state.expandedStaffEvalFileId = null;
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
  state.analysisFileId = null;
  state.expandedStaffEvalFileId = null;
  render();
});

csvList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-convert-file]");
  if (button) {
    convertFiles(new Set([button.dataset.convertFile]));
    return;
  }

  const reportButton = event.target.closest("[data-download-report]");
  if (reportButton) {
    downloadGeneratedFile(reportButton.dataset.downloadReport);
  }
});

analysisList.addEventListener("click", (event) => {
  const analyzeButton = event.target.closest("[data-analyze-file]");
  if (analyzeButton) {
    analyzeFiles(new Set([analyzeButton.dataset.analyzeFile]));
    return;
  }

  const viewButton = event.target.closest("[data-view-analysis]");
  if (viewButton) {
    viewAnalysisForFile(viewButton.dataset.viewAnalysis);
  }
});

staffEvalList.addEventListener("change", (event) => {
  const modelSelect = event.target.closest("[data-staff-model-file]");
  if (!modelSelect) {
    return;
  }
  const fileKey = modelSelect.dataset.staffModelFile;
  const model = modelSelect.value;
  if (!fileKey) {
    return;
  }
  const defaultModel = (state.staffModelOptions.length ? state.staffModelOptions[0] : STAFF_MODEL_OPTIONS[0]) || "gpt-5-mini";
  state.staffModelByFile[fileKey] = model || defaultModel;
});

staffEvalList.addEventListener("click", (event) => {
  const evalButton = event.target.closest("[data-evaluate-file]");
  if (evalButton) {
    const fileKey = evalButton.dataset.evaluateFile;
    const defaultModel = (state.staffModelOptions.length ? state.staffModelOptions[0] : STAFF_MODEL_OPTIONS[0]) || "gpt-5-mini";
    const model = state.staffModelByFile[fileKey] || defaultModel;
    evaluateStaff(new Set([fileKey]), model);
    return;
  }

  const viewButton = event.target.closest("[data-view-staff]");
  if (viewButton) {
    viewStaffEvaluationForFile(viewButton.dataset.viewStaff);
    return;
  }

  const staffButton = event.target.closest("[data-download-staff]");
  if (staffButton) {
    downloadGeneratedFile(staffButton.dataset.downloadStaff);
  }
});

analysisModalClose.addEventListener("click", closeAnalysisModal);

analysisModal.addEventListener("click", (event) => {
  if (event.target === analysisModal) {
    closeAnalysisModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !analysisModal.classList.contains("hidden")) {
    closeAnalysisModal();
  }
});

downloadCloudImage.addEventListener("click", downloadCurrentWordCloudImage);
downloadFrequencyCsv.addEventListener("click", downloadCurrentFrequencyCsv);

render();
loadConfig();
loadOpenAIModels();
