const API_URL = (window.APP_CONFIG && window.APP_CONFIG.API_URL) || '';
const API = (path) => `${API_URL}${path}`;

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const dropZoneContent = document.getElementById('dropZoneContent');
const uploadProgress = document.getElementById('uploadProgress');
const resultsSection = document.getElementById('resultsSection');
const historyList = document.getElementById('historyList');
const historyEmpty = document.getElementById('historyEmpty');
const historyCount = document.getElementById('historyCount');
const exportBtn = document.getElementById('exportBtn');
const clearBtn = document.getElementById('clearBtn');

let currentScanUuid = null;

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const files = e.dataTransfer.files;
  if (files.length > 0) processFile(files[0]);
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) processFile(e.target.files[0]);
});

function processFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('Please select an image file', 'error');
    return;
  }

  dropZoneContent.style.display = 'none';
  uploadProgress.style.display = 'flex';

  const formData = new FormData();
  formData.append('image', file);

  fetch(API('/api/scan'), {
    method: 'POST',
    body: formData,
  })
    .then(r => r.json())
    .then(data => {
      uploadProgress.style.display = 'none';
      dropZoneContent.style.display = 'flex';

      if (data.error) {
        showToast(data.error, 'error');
        return;
      }

      displayResult(data);
      loadHistory();
      showToast('Card scanned successfully!', 'success');
    })
    .catch(err => {
      uploadProgress.style.display = 'none';
      dropZoneContent.style.display = 'flex';
      showToast('Failed to process image: ' + err.message, 'error');
    });
}

const FIELD_IDS = [
  'fieldIndustry', 'fieldSalesBranch', 'fieldRating',
  'fieldCity', 'fieldState', 'fieldGSTIN', 'fieldAssignedTo'
];

const FIELD_MAP = {
  fieldIndustry: 'industry',
  fieldSalesBranch: 'sales_branch',
  fieldRating: 'rating',
  fieldCity: 'city',
  fieldState: 'state',
  fieldGSTIN: 'gstin',
  fieldAssignedTo: 'assigned_to',
};

function displayResult(data) {
  const { scan, texts, vis_url } = data;
  currentScanUuid = scan.uuid;

  document.getElementById('resultImage').src = API(vis_url);
  document.getElementById('resultBadge').textContent = `${texts.length} texts`;

  const textList = document.getElementById('textList');
  textList.innerHTML = '';

  if (texts.length === 0) {
    textList.innerHTML = '<div class="text-item"><span class="content" style="color:var(--text-muted)">No text detected</span></div>';
  } else {
    texts.forEach((t, i) => {
      const div = document.createElement('div');
      div.className = 'text-item';
      if (t.confidence < 0.5) div.classList.add('confidence-very-low');
      else if (t.confidence < 0.8) div.classList.add('confidence-low');

      div.innerHTML = `
        <span class="index">#${i + 1}</span>
        <span class="content">${escapeHtml(t.text)}</span>
        <span class="confidence">${(t.confidence * 100).toFixed(1)}%</span>
      `;
      textList.appendChild(div);
    });
  }

  document.getElementById('fullTextArea').value = scan.full_text || '';
  resultsSection.style.display = 'block';

  populateFields(scan);
  document.getElementById('savedBadge').style.display = 'none';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function populateFields(scan) {
  for (const fieldId of FIELD_IDS) {
    const key = FIELD_MAP[fieldId];
    document.getElementById(fieldId).value = scan[key] || '';
  }
}

function saveCardDetails() {
  if (!currentScanUuid) return;

  const data = {};
  for (const fieldId of FIELD_IDS) {
    const key = FIELD_MAP[fieldId];
    data[key] = document.getElementById(fieldId).value;
  }

  fetch(API(`/api/scans/${currentScanUuid}`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
    .then(r => r.json())
    .then(resp => {
      if (resp.error) {
        showToast(resp.error, 'error');
        return;
      }
      document.getElementById('savedBadge').style.display = 'inline';
      showToast('Card details saved!', 'success');
      loadHistory();
    })
    .catch(err => showToast('Save failed: ' + err.message, 'error'));
}

function loadHistory() {
  fetch(API('/api/scans'))
    .then(r => r.json())
    .then(data => {
      const scans = data.scans;
      historyCount.textContent = `${scans.length} scan${scans.length !== 1 ? 's' : ''}`;
      exportBtn.disabled = scans.length === 0;
      clearBtn.disabled = scans.length === 0;

      if (scans.length === 0) {
        historyList.innerHTML = '';
        historyEmpty.style.display = 'flex';
        return;
      }

      historyEmpty.style.display = 'none';
      historyList.innerHTML = '';

      scans.forEach(s => {
        const fields = [];
        if (s.industry) fields.push(s.industry);
        if (s.city && s.state) fields.push(`${s.city}, ${s.state}`);
        else if (s.city) fields.push(s.city);
        else if (s.state) fields.push(s.state);
        if (s.assigned_to) fields.push(s.assigned_to);

        const metaText = fields.length > 0
          ? fields.join(' · ')
          : `${s.text_count} texts`;

        const item = document.createElement('div');
        item.className = 'history-item';
        item.innerHTML = `
          <img class="thumb" src="${API(s.image_url)}" alt="${escapeHtml(s.filename)}" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2248%22 height=%2248%22><rect fill=%22%23334155%22 width=%2248%22 height=%2248%22/><text x=%2224%22 y=%2230%22 text-anchor=%22middle%22 fill=%22%2394a3b8%22 font-size=%2220%22>?</text></svg>'">
          <div class="info">
            <div class="filename">${escapeHtml(s.filename)}</div>
            <div class="meta">${escapeHtml(metaText)}</div>
          </div>
          <div class="actions">
            <button class="btn-icon" onclick="viewScan('${s.uuid}')" title="View">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
            <button class="btn-icon danger" onclick="deleteScan('${s.uuid}')" title="Delete">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
              </svg>
            </button>
          </div>
        `;
        historyList.appendChild(item);
      });
    });
}

function viewScan(uuid) {
  fetch(API(`/api/scans/${uuid}`))
    .then(r => r.json())
    .then(data => {
      currentScanUuid = data.scan.uuid;
      displayResult(data);
    });
}

function deleteScan(uuid) {
  if (!confirm('Delete this scan?')) return;
  fetch(API(`/api/scans/${uuid}`), { method: 'DELETE' })
    .then(() => {
      if (currentScanUuid === uuid) {
        resultsSection.style.display = 'none';
        currentScanUuid = null;
      }
      loadHistory();
      showToast('Scan deleted', 'info');
    });
}

function exportCSV() {
  window.location.href = API('/api/export/csv');
  showToast('CSV file downloaded', 'success');
}

function clearAll() {
  if (!confirm('Delete ALL scans? This cannot be undone.')) return;
  fetch(API('/api/clear'), { method: 'DELETE' })
    .then(() => {
      resultsSection.style.display = 'none';
      currentScanUuid = null;
      loadHistory();
      showToast('All scans cleared', 'info');
    });
}

function copyFullText() {
  const ta = document.getElementById('fullTextArea');
  ta.select();
  navigator.clipboard.writeText(ta.value).then(() => {
    showToast('Text copied to clipboard', 'success');
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

loadHistory();
