"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import {
  login,
  saveAuthSession,
} from "@/lib/authApi";

export default function SignInPage() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      saveAuthSession(result.token, result.user);
      router.push("/");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Sign in failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-stage" aria-label="WRDN sign in">
        <aside className="auth-hero">
          <div className="auth-hero-glow" aria-hidden />
          <div className="auth-hero-grid" aria-hidden />

          <div className="auth-hero-brand">
            <span className="auth-mark">W</span>
            <div>
              <p className="auth-name">WRDN</p>
              <p className="auth-kicker">My Protection</p>
            </div>
          </div>

          <h1 className="auth-hero-title">
            Welcome back
            <span>to the shield room.</span>
          </h1>
          <p className="auth-hero-copy">
            Sign in with the username and password you
            created. Admin and Employee each use their own
            account.
          </p>
        </aside>

        <section className="auth-panel">
          <header className="auth-panel-head">
            <p className="auth-step">Secure entry</p>
            <h2>Sign in</h2>
            <p>
              Enter your username and password again —
              separately for Admin or Employee accounts.
            </p>
          </header>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-field">
              <label htmlFor="signin-username">Username</label>
              <input
                id="signin-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Your username"
                autoComplete="username"
                required
              />
            </div>

            <div className="auth-field">
              <label htmlFor="signin-password">Password</label>
              <div className="auth-password-wrap">
                <input
                  id="signin-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="auth-eye"
                  aria-label={
                    showPassword
                      ? "Hide password"
                      : "Show password"
                  }
                  onClick={() =>
                    setShowPassword((open) => !open)
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
                    {showPassword ? (
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
              </div>
            </div>

            {error ? (
              <p className="auth-error">{error}</p>
            ) : null}

            <button
              className="auth-submit"
              type="submit"
              disabled={loading}
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="auth-foot">
            New here?{" "}
            <Link href="/signup">Create an account</Link>
          </p>
        </section>
      </section>

      <style>{`
        .auth-shell {
          width: 100%;
          height: 100vh;
          height: 100dvh;
          max-height: 100dvh;
          display: grid;
          padding: 0;
          margin: 0;
          box-sizing: border-box;
          overflow: hidden;
          color: #f3f6fb;
          background: #05070c;
        }

        .auth-stage {
          width: 100%;
          height: 100%;
          min-height: 0;
          display: grid;
          grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
          overflow: hidden;
          border: 0;
          border-radius: 0;
          background: #080a0f;
        }

        .auth-hero {
          position: relative;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: clamp(16px, 2.8vh, 28px);
          padding:
            clamp(28px, 5vh, 56px)
            clamp(28px, 4.5vw, 64px);
          min-height: 0;
          background:
            linear-gradient(
              160deg,
              rgba(32, 228, 135, 0.12),
              transparent 42%
            ),
            #070a10;
          overflow: hidden;
        }

        .auth-hero-glow {
          position: absolute;
          width: min(420px, 40vw);
          height: min(420px, 40vw);
          right: -60px;
          bottom: -40px;
          border-radius: 50%;
          background: rgba(32, 228, 135, 0.18);
          filter: blur(40px);
          animation: authPulse 7s ease-in-out infinite;
        }

        .auth-hero-grid {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(
              rgba(255, 255, 255, 0.03) 1px,
              transparent 1px
            ),
            linear-gradient(
              90deg,
              rgba(255, 255, 255, 0.03) 1px,
              transparent 1px
            );
          background-size: 28px 28px;
          mask-image: linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0.55),
            transparent 85%
          );
          pointer-events: none;
        }

        .auth-hero-brand,
        .auth-hero-title,
        .auth-hero-copy {
          position: relative;
          z-index: 1;
        }

        .auth-hero-brand {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .auth-mark {
          width: clamp(42px, 4.2vw, 54px);
          height: clamp(42px, 4.2vw, 54px);
          display: grid;
          place-items: center;
          border-radius: 14px;
          color: #05070c;
          background: #20e487;
          font-size: clamp(16px, 1.5vw, 20px);
          font-weight: 900;
          box-shadow: 0 0 24px rgba(32, 228, 135, 0.28);
        }

        .auth-name {
          margin: 0;
          font-size: clamp(24px, 2.4vw, 32px);
          font-weight: 800;
          letter-spacing: -0.05em;
          line-height: 1;
        }

        .auth-kicker {
          margin: 6px 0 0;
          color: #8b93a0;
          font-size: clamp(11px, 1vw, 12px);
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .auth-hero-title {
          margin: 0;
          max-width: 11ch;
          font-size: clamp(32px, 4.2vw, 56px);
          font-weight: 800;
          letter-spacing: -0.045em;
          line-height: 1.08;
        }

        .auth-hero-title span {
          display: block;
          color: #9fe9c4;
        }

        .auth-hero-copy {
          margin: 0;
          max-width: 38ch;
          color: #a7b0bd;
          font-size: clamp(14px, 1.35vw, 17px);
          line-height: 1.55;
        }

        .auth-panel {
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: clamp(12px, 2vh, 22px);
          padding:
            clamp(24px, 4.5vh, 52px)
            clamp(24px, 4vw, 56px);
          min-height: 0;
          background: #0a0d14;
          border-left: 1px solid rgba(255, 255, 255, 0.06);
          overflow: hidden;
        }

        .auth-panel-head .auth-step {
          margin: 0 0 6px;
          color: #20e487;
          font-size: clamp(11px, 1vw, 12px);
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        .auth-panel-head h2 {
          margin: 0 0 6px;
          font-size: clamp(24px, 2.6vw, 34px);
          letter-spacing: -0.03em;
        }

        .auth-panel-head p {
          margin: 0;
          color: #8b93a0;
          font-size: clamp(13px, 1.2vw, 15px);
          line-height: 1.45;
        }

        .auth-panel-head strong {
          color: #d7dde7;
          font-weight: 700;
        }

        .auth-demo-row {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .auth-demo-chip {
          padding: 8px 12px;
          border: 1px solid rgba(32, 228, 135, 0.28);
          border-radius: 999px;
          color: #9fe9c4;
          background: rgba(32, 228, 135, 0.08);
          font: inherit;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
        }

        .auth-demo-chip:hover {
          background: rgba(32, 228, 135, 0.16);
        }

        .auth-form {
          display: grid;
          gap: clamp(10px, 1.6vh, 16px);
          min-height: 0;
        }

        .auth-field {
          display: grid;
          gap: clamp(4px, 0.8vh, 8px);
        }

        .auth-field label {
          color: #c7ced8;
          font-size: clamp(12px, 1.1vw, 13px);
          font-weight: 700;
        }

        .auth-field input {
          width: 100%;
          padding: clamp(10px, 1.5vh, 15px) 14px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          outline: none;
          color: #f5f7fb !important;
          background: #05070c !important;
          font: inherit;
          font-size: clamp(13px, 1.2vw, 15px);
          -webkit-text-fill-color: #f5f7fb;
          transition:
            border-color 160ms ease,
            box-shadow 160ms ease;
        }

        .auth-field input:-webkit-autofill,
        .auth-field input:-webkit-autofill:hover,
        .auth-field input:-webkit-autofill:focus {
          -webkit-text-fill-color: #f5f7fb;
          caret-color: #f5f7fb;
          box-shadow: 0 0 0 1000px #05070c inset;
          transition: background-color 99999s ease-in-out 0s;
        }

        .auth-field input:focus {
          border-color: #20e487;
          box-shadow: 0 0 0 3px rgba(32, 228, 135, 0.14);
        }

        .auth-password-wrap {
          position: relative;
        }

        .auth-password-wrap input {
          padding-right: 44px;
        }

        .auth-eye {
          position: absolute;
          right: 8px;
          top: 50%;
          transform: translateY(-50%);
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
          padding: 0;
          border: 0;
          border-radius: 8px;
          color: #9fe9c4;
          background: transparent;
          cursor: pointer;
        }

        .auth-eye:hover {
          background: rgba(32, 228, 135, 0.12);
        }

        .auth-submit {
          margin-top: 2px;
          padding: clamp(12px, 1.8vh, 16px) 18px;
          border: 0;
          border-radius: 12px;
          color: #05070c;
          background: linear-gradient(
            135deg,
            #34f09a,
            #20e487 55%,
            #12c973
          );
          font: inherit;
          font-size: clamp(14px, 1.3vw, 16px);
          font-weight: 800;
          cursor: pointer;
          box-shadow: 0 10px 26px rgba(32, 228, 135, 0.22);
        }

        .auth-submit:hover {
          box-shadow: 0 12px 30px rgba(32, 228, 135, 0.3);
        }

        .auth-submit:disabled {
          opacity: 0.65;
          cursor: not-allowed;
        }

        .auth-error {
          margin: 0;
          color: #fca5a5;
          font-size: 14px;
        }

        .auth-foot {
          margin: 0;
          color: #7d8590;
          font-size: clamp(13px, 1.2vw, 14px);
        }

        .auth-foot a {
          color: #20e487;
          font-weight: 700;
          text-decoration: none;
        }

        .auth-foot a:hover {
          text-decoration: underline;
        }

        @keyframes authPulse {
          0%,
          100% {
            opacity: 0.55;
            transform: scale(1);
          }
          50% {
            opacity: 0.9;
            transform: scale(1.08);
          }
        }

        @media (max-height: 760px) {
          .auth-hero-copy {
            display: none;
          }
        }

        @media (max-width: 900px) {
          .auth-shell {
            height: auto;
            min-height: 100dvh;
            max-height: none;
            overflow: auto;
          }

          .auth-stage {
            height: auto;
            grid-template-columns: 1fr;
            overflow: visible;
          }

          .auth-hero {
            min-height: 200px;
            padding: 22px;
          }

          .auth-hero-title {
            max-width: none;
          }

          .auth-panel {
            border-left: 0;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            overflow: visible;
            padding: 22px;
          }
        }
      `}</style>
    </main>
  );
}
