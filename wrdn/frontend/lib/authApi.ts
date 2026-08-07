const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:18000"
).replace(/\/+$/, "");

export type AuthUser = {
  user_id: number;
  username: string;
  role: "ADMIN" | "EMPLOYEE" | string;
  client_id: string;
};

export type LoginResponse = {
  status: string;
  token: string;
  user: AuthUser;
};

const TOKEN_KEY = "wrdn_auth_token";
const USER_KEY = "wrdn_auth_user";

export function saveAuthSession(
  token: string,
  user: AuthUser,
) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(
    USER_KEY,
    JSON.stringify(user),
  );
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getAuthUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
      }),
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail || "Login failed.",
    );
  }

  return data as LoginResponse;
}