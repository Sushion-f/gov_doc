const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

/** 默认 JSON 请求超时（毫秒） */
export const DEFAULT_REQUEST_TIMEOUT_MS = 15000;
/** 长耗时接口（如会话 run、大事件流） */
export const LONG_REQUEST_TIMEOUT_MS = 120000;
/** 事件流文本拉取（bootstrap 选中会话时） */
export const EVENT_STREAM_TIMEOUT_MS = 60000;

function buildUrl(path) {
  return `${API_BASE_URL}${path}`;
}

/**
 * 合并超时 signal 与用户传入的 signal（任一方 abort 即中止）。
 */
function resolveSignal(timeoutMs, userSignal) {
  if (typeof AbortSignal === "undefined") {
    return undefined;
  }
  const timed =
    typeof AbortSignal.timeout === "function"
      ? AbortSignal.timeout(timeoutMs)
      : (() => {
          const controller = new AbortController();
          const id = window.setTimeout(() => controller.abort(), timeoutMs);
          controller.signal.addEventListener("abort", () => window.clearTimeout(id), { once: true });
          return controller.signal;
        })();
  if (!userSignal) {
    return timed;
  }
  if (typeof AbortSignal.any === "function") {
    return AbortSignal.any([timed, userSignal]);
  }
  const merged = new AbortController();
  const abortMerged = () => merged.abort();
  timed.addEventListener("abort", abortMerged);
  userSignal.addEventListener("abort", abortMerged);
  return merged.signal;
}

export async function requestJson(path, options = {}) {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, ...rest } = options;
  const signal = resolveSignal(timeoutMs, rest.signal);
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(rest.headers || {}),
    },
    ...rest,
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

export async function requestText(path, options = {}) {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, ...rest } = options;
  const signal = resolveSignal(timeoutMs, rest.signal);
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    ...rest,
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.text();
}

export async function uploadFile(path, file, options = {}) {
  const { timeoutMs = 60000, ...rest } = options;
  const signal = resolveSignal(timeoutMs, rest.signal);
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(buildUrl(path), {
    method: "POST",
    credentials: "include",
    body: formData,
    ...rest,
    signal,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function postForm(path, formData, options = {}) {
  const { timeoutMs = 60000, ...rest } = options;
  const signal = resolveSignal(timeoutMs, rest.signal);
  const response = await fetch(buildUrl(path), {
    method: "POST",
    credentials: "include",
    body: formData,
    ...rest,
    signal,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function readEventStream(path, options = {}) {
  const events = [];
  await streamEventStream(path, {
    ...options,
    onEvent(event) {
      events.push(event);
    },
  });
  return events;
}

export async function streamEventStream(path, options = {}) {
  const { timeoutMs = LONG_REQUEST_TIMEOUT_MS, onEvent = () => {}, signal: userSignal } = options;
  const signal = resolveSignal(timeoutMs, userSignal);
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Event stream unavailable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const chunk of parts) {
      const dataLines = chunk
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6));

      for (const line of dataLines) {
        if (!line || line === "[DONE]") {
          if (line === "[DONE]") {
            return;
          }
          continue;
        }
        onEvent(JSON.parse(line));
      }
    }

    if (done) {
      return;
    }
  }
}
