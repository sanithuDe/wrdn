"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import {
    login,
    saveAuthSession,
} from "@/lib/authApi";

export default function LoginPage() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await login(
        username.trim(),
        password,
      );

      saveAuthSession(
        result.token,
        result.user,
      );

      router.push("/");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Login failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="wrdn-login-page">
      <form
        className="wrdn-login-card"
        onSubmit={handleSubmit}
      >
        <div className="wrdn-login-brand">
          <div className="app-brand-logo">W</div>
          <div>
            <h1>WRDN</h1>
            <p>Enterprise Prompt Shield</p>
          </div>
        </div>

        <h2>Sign in to dashboard</h2>
        <p className="wrdn-login-subtitle">
          Admin can upload policies. Employee can chat.
        </p>

        <label>Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="adminA"
          required
        />

        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          required
        />

        {error && (
          <p className="wrdn-login-error">{error}</p>
        )}

        <button type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Login"}
        </button>

        <p className="wrdn-login-hint">
          Try: adminA / admin123 or employeeA / employee123
        </p>
      </form>

      <style jsx>{`
        .wrdn-login-page {
          min-height: 100vh;
          display: grid;
          place-items: center;
          padding: 20px;
          color: #f5f7fb;
          background:
            radial-gradient(
              circle at top left,
              rgba(32, 228, 135, 0.08),
              transparent 34%
            ),
            #05070c;
        }

        .wrdn-login-card {
          width: 100%;
          max-width: 420px;
          padding: 28px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 18px;
          background: #080a0f;
          box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
        }

        .wrdn-login-brand {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 22px;
        }

        .wrdn-login-brand :global(.app-brand-logo) {
          width: 42px;
          height: 42px;
          display: grid;
          place-items: center;
          border-radius: 13px;
          color: #05070c;
          background: #20e487;
          font-weight: 900;
          box-shadow: 0 0 24px rgba(32, 228, 135, 0.22);
        }

        .wrdn-login-brand h1 {
          margin: 0;
          font-size: 22px;
          font-weight: 800;
          letter-spacing: -0.04em;
        }

        .wrdn-login-brand p {
          margin: 3px 0 0;
          color: #7d8590;
          font-size: 12px;
        }

        h2 {
          margin: 0 0 6px;
          font-size: 20px;
        }

        .wrdn-login-subtitle {
          margin: 0 0 18px;
          color: #7d8590;
          font-size: 13px;
        }

        label {
          display: block;
          margin-bottom: 6px;
          color: #c7ced8;
          font-size: 13px;
          font-weight: 700;
        }

        input {
          width: 100%;
          margin-bottom: 14px;
          padding: 11px 12px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 10px;
          outline: none;
          color: #f5f7fb;
          background: #05070c;
        }

        input:focus {
          border-color: #20e487;
          box-shadow: 0 0 0 3px rgba(32, 228, 135, 0.12);
        }

        button {
          width: 100%;
          margin-top: 4px;
          padding: 12px;
          border: 0;
          border-radius: 10px;
          color: #05070c;
          background: #20e487;
          font-weight: 800;
        }

        button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .wrdn-login-error {
          color: #fca5a5;
          font-size: 13px;
        }

        .wrdn-login-hint {
          margin: 14px 0 0;
          color: #7d8590;
          font-size: 12px;
        }
      `}</style>
    </main>
  );
}