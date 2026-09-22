import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8600";

const client = axios.create({ baseURL: BASE_URL });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("session_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A stored token can go stale (backend restarted mid-session, or the JWT simply expired) -
// when that happens the API returns 401 (bad/expired token) or 404 (token still valid but
// the in-memory session is gone). Either way the right move is to drop back to the login
// screen instead of leaving the user stuck on silent/confusing errors.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const isLoginRequest = error?.config?.url?.includes("/api/auth/login");
    if ((status === 401 || status === 404) && !isLoginRequest) {
      localStorage.removeItem("session_token");
      localStorage.removeItem("session_id");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.reload();
      }
    }
    return Promise.reject(error);
  }
);

export async function login(username, password) {
  const { data } = await client.post("/api/auth/login", { username, password });
  return data;
}

export async function uploadFiles(files) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const { data } = await client.post("/api/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function sendChatMessage(message) {
  const { data } = await client.post("/api/chat", { message });
  return data;
}

export async function updateConfig(config) {
  const { data } = await client.patch("/api/config", config);
  return data;
}

export async function fetchSessionInfo() {
  const { data } = await client.get("/api/session/me");
  return data;
}

export async function fetchTurnEval(turnId) {
  const { data } = await client.get(`/api/chat/${turnId}/eval`);
  return data;
}

export async function endSession() {
  const { data } = await client.delete("/api/session/me");
  return data;
}

export default client;
