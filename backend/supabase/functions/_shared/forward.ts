// Internal jobs authenticate with a secret header, never a browser-visible key.
export async function forward(request: Request, path: string, sendBody = false) {
  if (request.method !== "POST") return new Response("Use POST", { status: 405 });
  const token = Deno.env.get("CLEARING_TOKEN");
  const backend = Deno.env.get("BACKEND_URL");
  if (!token || !backend) return new Response("Job configuration is missing", { status: 503 });
  if (request.headers.get("x-clearing-token") !== token) return new Response("Forbidden", { status: 403 });
  try {
    const response = await fetch(`${backend.replace(/\/$/, "")}/api/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-clearing-token": token },
      body: sendBody ? await request.text() : undefined,
      signal: AbortSignal.timeout(15000),
    });
    return new Response(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return new Response("GridLink backend is unavailable", { status: 502 });
  }
}
