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

export type ManagedUser = {
  user_id: number;
  username: string;
  role: string;
  client_id: string;
  created_at: string;
};

export type LoginResponse = {
  status: string;
  token: string;
  user: AuthUser;
};

const TOKEN_KEY = "wrdn_auth_token";
const USER_KEY = "wrdn_auth_user";

function authHeaders(): HeadersInit {
  const token = getAuthToken();
  return {
    "Content-Type": "application/json",
    ...(token
      ? { Authorization: `Bearer ${token}` }
      : {}),
  };
}

function errorMessage(
  data: { detail?: unknown } | null,
  fallback: string,
): string {
  const detail = data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string }) => item?.msg)
      .filter(Boolean)
      .join(" ");
  }
  return fallback;
}

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
      errorMessage(data, "Login failed."),
    );
  }

  return data as LoginResponse;
}

export async function signup(input: {
  username: string;
  password: string;
  organisation: string;
  full_name: string;
  email: string;
  role: "ADMIN" | "EMPLOYEE";
}): Promise<{
  status: string;
  message: string;
  user: AuthUser;
}> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/signup`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      errorMessage(data, "Signup failed."),
    );
  }

  return data;
}

export async function listUsers(): Promise<
  ManagedUser[]
> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/users`,
    {
      method: "GET",
      headers: authHeaders(),
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      errorMessage(data, "Could not load users."),
    );
  }

  return (data?.users || []) as ManagedUser[];
}

export async function createUser(input: {
  username: string;
  password: string;
  role: "ADMIN" | "EMPLOYEE";
}): Promise<AuthUser> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/users`,
    {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(input),
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      errorMessage(data, "Could not create user."),
    );
  }

  return data.user as AuthUser;
}

export async function deleteUser(
  username: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/users/${encodeURIComponent(username)}`,
    {
      method: "DELETE",
      headers: authHeaders(),
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      errorMessage(data, "Could not delete user."),
    );
  }
}
