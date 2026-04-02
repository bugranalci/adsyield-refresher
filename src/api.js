const BASE_URL = 'http://127.0.0.1:8000';

export async function getPublishers() {
  const res = await fetch(`${BASE_URL}/publishers`);
  return res.json();
}

export async function createPublisher(data) {
  const res = await fetch(`${BASE_URL}/publishers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

export async function runPublisher(id, dryRun = true) {
  const res = await fetch(`${BASE_URL}/publishers/${id}/run?dry_run=${dryRun}`, {
    method: 'POST'
  });
  return res.json();
}

export async function getLogs() {
  const res = await fetch(`${BASE_URL}/logs`);
  return res.json();
}
export async function updatePublisher(id, data) {
  const res = await fetch(`${BASE_URL}/publishers/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}
export async function deletePublisher(id) {
  const res = await fetch(`${BASE_URL}/publishers/${id}`, {
    method: 'DELETE'
  });
  return res.json();
}