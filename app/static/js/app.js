/* Shared JavaScript utilities */

async function fetchJSON(url) {
  const resp = await fetch(url);
  return resp.json();
}

async function postJSON(url, data) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
