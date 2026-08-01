/* Shared helpers used across dashboard.html and explore.html */

function requireAuth() {
  if (!localStorage.getItem('lb_user')) {
    window.location.href = '/';
  } else {
    var el = document.getElementById('navUserName');
    if (el) el.textContent = localStorage.getItem('lb_user');
  }
}

function logout() {
  localStorage.removeItem('lb_user');
  window.location.href = '/';
}

function getRepo() {
  return localStorage.getItem('lb_repo') || '';
}

function setRepo(path) {
  localStorage.setItem('lb_repo', path);
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return res.json();
}

function nowStamp() {
  const d = new Date();
  return d.toISOString().slice(0, 16).replace('T', ' ');
}
