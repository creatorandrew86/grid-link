export async function api(path, method = 'GET', body) {
  const token = localStorage.getItem('gridlink-token');
  const headers = {
    ...(body ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetch(`/api/${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
        ? detail.map((item) => item.msg).join(' ')
        : 'Could not reach GridLink. Check that the backend is running.'
    );
  }
  return data;
}

export const money = (value, digits = 3) =>
  new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value ?? 0);

export const amount = (value) => Number(value ?? 0).toLocaleString('en-IE', { maximumFractionDigits: 3 });

export const percent = (value) => `${Math.round((value ?? 0) * 100)}%`;

