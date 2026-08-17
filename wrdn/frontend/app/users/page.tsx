"use client";

import { useRouter } from "next/navigation";
import {
  FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";

import AppSidebar from "@/components/AppSidebar";
import {
  clearAuthSession,
  createUser,
  deleteUser,
  getAuthUser,
  listUsers,
  type AuthUser,
  type ManagedUser,
} from "@/lib/authApi";

export default function UsersPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(
    null,
  );
  const [checkingAuth, setCheckingAuth] =
    useState(true);
  const [users, setUsers] = useState<ManagedUser[]>(
    [],
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] =
    useState(false);
  const [newRole, setNewRole] = useState<
    "ADMIN" | "EMPLOYEE"
  >("EMPLOYEE");

  const loadUsers = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const rows = await listUsers();
      setUsers(rows);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not load users.",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    const authUser = getAuthUser();
    if (!authUser) {
      router.replace("/signin");
      return;
    }
    if (authUser.role !== "ADMIN") {
      router.replace("/");
      return;
    }
    setUser(authUser);
    setCheckingAuth(false);
    void loadUsers();
  }, [router, loadUsers]);

  function handleLogout() {
    clearAuthSession();
    router.push("/signin");
  }

  async function handleCreate(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError("");
    setMessage("");
    setBusy(true);

    try {
      await createUser({
        username: newUsername.trim(),
        password: newPassword,
        role: newRole,
      });
      setNewUsername("");
      setNewPassword("");
      setNewRole("EMPLOYEE");
      setMessage("User created.");
      await loadUsers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not create user.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(username: string) {
    if (
      !window.confirm(
        `Delete user "${username}"? This cannot be undone.`,
      )
    ) {
      return;
    }

    setError("");
    setMessage("");
    setBusy(true);

    try {
      await deleteUser(username);
      setMessage(`Deleted "${username}".`);
      await loadUsers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not delete user.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (checkingAuth || !user) {
    return (
      <main className="users-shell">
        <p className="users-loading">Loading users…</p>
      </main>
    );
  }

  return (
    <div className="wrdn-application">
      <AppSidebar
        activeSection="settings"
        onSectionChange={() => undefined}
        onNewChat={() => router.push("/")}
        isAdmin
        username={user.username}
        onLogout={handleLogout}
      />

      <main className="users-main">
        <header className="users-header">
          <div>
            <p className="users-kicker">Organisation</p>
            <h1>Users</h1>
            <p>
              Create and delete accounts for{" "}
              <strong>{user.client_id}</strong>.
            </p>
          </div>
          <button
            type="button"
            className="users-refresh"
            onClick={() => void loadUsers()}
            disabled={busy}
          >
            Refresh
          </button>
        </header>

        <section className="users-card">
          <h2>Create user</h2>
          <form
            className="users-form"
            onSubmit={handleCreate}
          >
            <label>
              Username
              <input
                value={newUsername}
                onChange={(e) =>
                  setNewUsername(e.target.value)
                }
                placeholder="new.user"
                required
              />
            </label>
            <label>
              Password
              <span className="users-password-wrap">
                <input
                  type={
                    showNewPassword ? "text" : "password"
                  }
                  value={newPassword}
                  onChange={(e) =>
                    setNewPassword(e.target.value)
                  }
                  placeholder="Min 8 chars + complexity"
                  required
                />
                <button
                  type="button"
                  className="users-eye"
                  aria-label={
                    showNewPassword
                      ? "Hide password"
                      : "Show password"
                  }
                  onClick={() =>
                    setShowNewPassword((open) => !open)
                  }
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden
                  >
                    {showNewPassword ? (
                      <>
                        <path d="M3 3l18 18" />
                        <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                        <path d="M9.9 5.1A10.9 10.9 0 0 1 12 5c7 0 11 7 11 7a18.5 18.5 0 0 1-4.2 5.1" />
                        <path d="M6.6 6.6C4.1 8.4 2.5 11 2.5 12S5 17 12 17c1.1 0 2.1-.1 3.1-.4" />
                      </>
                    ) : (
                      <>
                        <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" />
                        <circle cx="12" cy="12" r="3" />
                      </>
                    )}
                  </svg>
                </button>
              </span>
            </label>
            <label>
              Role
              <select
                value={newRole}
                onChange={(e) =>
                  setNewRole(
                    e.target.value as
                      | "ADMIN"
                      | "EMPLOYEE",
                  )
                }
              >
                <option value="EMPLOYEE">Employee</option>
                <option value="ADMIN">Admin</option>
              </select>
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Working…" : "Create user"}
            </button>
          </form>
        </section>

        <section className="users-card">
          <h2>Current users ({users.length})</h2>
          {error ? (
            <p className="users-error">{error}</p>
          ) : null}
          {message ? (
            <p className="users-ok">{message}</p>
          ) : null}

          <div className="users-table-wrap">
            <table className="users-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Client</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((row) => {
                  const isSelf =
                    row.username === user.username;
                  return (
                    <tr key={row.user_id}>
                      <td>{row.username}</td>
                      <td>{row.role}</td>
                      <td>{row.client_id}</td>
                      <td>
                        {row.created_at
                          ? new Date(
                              row.created_at,
                            ).toLocaleString()
                          : "—"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="users-delete"
                          disabled={busy || isSelf}
                          title={
                            isSelf
                              ? "You cannot delete your own account"
                              : `Delete ${row.username}`
                          }
                          onClick={() =>
                            void handleDelete(
                              row.username,
                            )
                          }
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={5}>No users found.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <style>{`
        .users-shell,
        .users-loading {
          min-height: 100vh;
          display: grid;
          place-items: center;
          color: #c7ced8;
          background: #05070c;
        }

        .users-main {
          min-height: 100vh;
          overflow: auto;
          padding: 28px 32px 48px;
          background: #05070c;
          color: #f3f6fb;
        }

        .users-header {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          align-items: flex-start;
          margin-bottom: 24px;
        }

        .users-kicker {
          margin: 0 0 6px;
          color: #20e487;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        .users-header h1 {
          margin: 0 0 8px;
          font-size: 32px;
          letter-spacing: -0.03em;
        }

        .users-header p {
          margin: 0;
          color: #8b93a0;
        }

        .users-header strong {
          color: #d7dde7;
        }

        .users-refresh,
        .users-form button,
        .users-delete {
          border: 0;
          border-radius: 10px;
          font: inherit;
          font-weight: 700;
          cursor: pointer;
        }

        .users-refresh {
          padding: 10px 14px;
          color: #05070c;
          background: #20e487;
        }

        .users-card {
          margin-bottom: 20px;
          padding: 22px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          background: #0a0d14;
        }

        .users-card h2 {
          margin: 0 0 16px;
          font-size: 18px;
        }

        .users-form {
          display: grid;
          grid-template-columns: 1.2fr 1.4fr 0.8fr auto;
          gap: 12px;
          align-items: end;
        }

        .users-form label {
          display: grid;
          gap: 6px;
          color: #c7ced8;
          font-size: 12px;
          font-weight: 700;
        }

        .users-form input,
        .users-form select {
          width: 100%;
          padding: 11px 12px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 10px;
          color: #f5f7fb;
          background: #05070c;
          font: inherit;
        }

        .users-password-wrap {
          position: relative;
          display: block;
        }

        .users-password-wrap input {
          padding-right: 40px;
        }

        .users-eye {
          position: absolute;
          right: 6px;
          top: 50%;
          transform: translateY(-50%);
          width: 28px;
          height: 28px;
          display: grid;
          place-items: center;
          padding: 0;
          border: 0;
          border-radius: 8px;
          color: #9fe9c4;
          background: transparent;
          cursor: pointer;
        }

        .users-form button {
          padding: 12px 16px;
          color: #05070c;
          background: linear-gradient(
            135deg,
            #34f09a,
            #20e487 55%,
            #12c973
          );
        }

        .users-form button:disabled,
        .users-refresh:disabled,
        .users-delete:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }

        .users-error {
          color: #fca5a5;
        }

        .users-ok {
          color: #7dffb2;
        }

        .users-table-wrap {
          overflow-x: auto;
        }

        .users-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 14px;
        }

        .users-table th,
        .users-table td {
          padding: 12px 10px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          text-align: left;
        }

        .users-table th {
          color: #8b93a0;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .users-delete {
          padding: 8px 12px;
          color: #fecaca;
          background: rgba(248, 113, 113, 0.12);
          border: 1px solid rgba(248, 113, 113, 0.28);
        }

        @media (max-width: 980px) {
          .users-form {
            grid-template-columns: 1fr;
          }

          .users-main {
            padding: 20px 16px 40px;
          }
        }
      `}</style>
    </div>
  );
}
