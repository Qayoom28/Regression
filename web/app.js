async function api(path, method = 'GET', body) {
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function formDataToJson(form) {
  const data = new FormData(form);
  return Object.fromEntries(data.entries());
}

async function refresh() {
  const [summary, leads] = await Promise.all([
    api('/api/summary'),
    api('/api/leads'),
  ]);

  document.getElementById('summary').innerHTML = [
    ['Leads', summary.leads],
    ['Customers', summary.customers],
    ['Open Tasks', summary.open_tasks],
    ['Pipeline Value', `₹${Number(summary.pipeline_value || 0).toLocaleString()}`],
  ].map(([label, value]) => `<div class="card"><h3>${label}</h3><p>${value}</p></div>`).join('');

  document.getElementById('leads-table').innerHTML = leads.slice(0, 10).map(
    lead => `<tr><td>${lead.id}</td><td>${lead.name}</td><td>${lead.email}</td><td>${lead.status}</td></tr>`
  ).join('');
}

for (const [id, path] of [
  ['lead-form', '/api/leads'],
  ['customer-form', '/api/customers'],
  ['opp-form', '/api/opportunities'],
  ['task-form', '/api/tasks'],
]) {
  document.getElementById(id).addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    try {
      await api(path, 'POST', formDataToJson(form));
      form.reset();
      await refresh();
    } catch (err) {
      alert(`Request failed: ${err.message}`);
    }
  });
}

refresh();
