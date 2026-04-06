const BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// --- Publishers ---

export async function getPublishers() {
  return request(`${BASE_URL}/publishers`);
}

export async function createPublisher(data) {
  return request(`${BASE_URL}/publishers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

export async function updatePublisher(id, data) {
  return request(`${BASE_URL}/publishers/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

export async function deletePublisher(id) {
  return request(`${BASE_URL}/publishers/${id}`, { method: 'DELETE' });
}

// --- Run & Jobs ---

export async function runPublisher(id, dryRun = true) {
  return request(`${BASE_URL}/publishers/${id}/run?dry_run=${dryRun}`, { method: 'POST' });
}

export async function getJobStatus(jobId) {
  return request(`${BASE_URL}/jobs/${jobId}`);
}

export async function pollJob(jobId, onUpdate, intervalMs = 2000) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const job = await getJobStatus(jobId);
        if (onUpdate) onUpdate(job);
        if (job.status !== 'running') {
          clearInterval(timer);
          resolve(job);
        }
      } catch (err) {
        clearInterval(timer);
        reject(err);
      }
    }, intervalMs);
  });
}

// --- Approvals ---

export async function getApprovals() {
  return request(`${BASE_URL}/approvals`);
}

export async function getApprovalDetail(jobId) {
  return request(`${BASE_URL}/approvals/${jobId}`);
}

export async function confirmApproval(jobId) {
  return request(`${BASE_URL}/approvals/${jobId}/confirm`, { method: 'POST' });
}

// --- Logs ---

export async function getLogs() {
  return request(`${BASE_URL}/logs`);
}
