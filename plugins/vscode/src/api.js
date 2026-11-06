// ReCode API client. Plain Node (global fetch, Node 18+); no VS Code imports so it can be tested on its own.

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 = network problem, 401 = bad token, 429 = slow down, ...
  }
}

class ReCodeClient {
  constructor({ baseUrl, token, fetchImpl = globalThis.fetch, timeoutMs = 30000 }) {
    this.baseUrl = String(baseUrl || "").trim().replace(/\/+$/, "");
    this.token = token;
    this.fetch = fetchImpl;
    this.timeoutMs = timeoutMs;
  }

  async request(method, path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let response;
    try {
      response = await this.fetch(this.baseUrl + path, {
        method,
        headers: {
          Authorization: `Token ${this.token}`,
          Accept: "application/json",
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (err) {
      const message = err && err.name === "AbortError"
        ? `ReCode didn't answer within ${Math.round(this.timeoutMs / 1000)}s.`
        : `Can't reach ${this.baseUrl}. Is the ReCode server running?`;
      throw new ApiError(message, 0);
    } finally {
      clearTimeout(timer);
    }
    let data = null;
    try { data = await response.json(); } catch (_) { /* not JSON */ }
    if (!response.ok || !data || data.ok === false) {
      const fallback = response.status === 404 ? `Not found: ${path}` : `ReCode answered with an error (${response.status}).`;
      throw new ApiError((data && data.error) || fallback, response.status);
    }
    return data;
  }

  me() { return this.request("GET", "/api/v1/me/"); }
  async today() { return (await this.request("GET", "/api/v1/today/")).challenge; }
  async challenge(slug) { return (await this.request("GET", `/api/v1/challenges/${encodeURIComponent(slug)}/`)).challenge; }
  async challenges() { return (await this.request("GET", "/api/v1/challenges/")).challenges; }
  run({ code, language, challenge }) { return this.request("POST", "/api/v1/run/", { code, language, challenge }); }
  submit({ code, language, challenge, mode }) { return this.request("POST", "/api/v1/submit/", { code, language, challenge, mode }); }

  /** Today's live leaderboard (public endpoint). */
  async leaderboard(limit = 5) {
    const data = await this.request("GET", "/leaderboard/data/?period=daily&scope=all");
    return (data.rows || []).slice(0, limit);
  }

  webUrl(path = "/") { return this.baseUrl + path; }
}

module.exports = { ApiError, ReCodeClient };
