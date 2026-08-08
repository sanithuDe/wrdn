"use client";

import { useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import AppSidebar from "@/components/AppSidebar";

import {
  getHrSampleCvs,
  getProtectionStatus,
  processHrCvUpload,
  setProtectionStatus,
  type HrProcessResult,
  type HrSampleCvsResponse,
} from "@/lib/api";

import {
  clearAuthSession,
  getAuthUser,
  type AuthUser,
} from "@/lib/authApi";

export default function HrCandidatesPage() {
  const router = useRouter();

  const [user, setUser] = useState<AuthUser | null>(
    null,
  );
  const [checkingAuth, setCheckingAuth] =
    useState(true);

  const [cvFile, setCvFile] = useState<File | null>(
    null,
  );
  const [fileInputKey, setFileInputKey] = useState(0);
  const [targetRole, setTargetRole] = useState(
    "Software Engineer",
  );
  const [samples, setSamples] =
    useState<HrSampleCvsResponse | null>(null);
  const [result, setResult] =
    useState<HrProcessResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [protectionEnabled, setProtectionEnabled] =
    useState(true);
  const [protectionBusy, setProtectionBusy] =
    useState(false);

  const isAdmin = user?.role === "ADMIN";
  const clientId = user?.client_id || "default";

  useEffect(() => {
    const authUser = getAuthUser();

    if (!authUser) {
      router.replace("/login");
      return;
    }

    setUser(authUser);
    setCheckingAuth(false);
  }, [router]);

  useEffect(() => {
    if (!user) {
      return;
    }

    void (async () => {
      try {
        const [sampleData, protection] =
          await Promise.all([
            getHrSampleCvs(),
            getProtectionStatus(clientId),
          ]);
        setSamples(sampleData);
        setProtectionEnabled(
          Boolean(protection.protection_enabled),
        );
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Failed to load HR samples.",
        );
      }
    })();
  }, [user, clientId]);

  function handleLogout() {
    clearAuthSession();
    router.push("/login");
  }

  async function toggleProtection() {
    if (!isAdmin || protectionBusy) {
      return;
    }

    setProtectionBusy(true);
    setError("");

    try {
      const response = await setProtectionStatus(
        clientId,
        !protectionEnabled,
      );
      setProtectionEnabled(
        Boolean(response.protection_enabled),
      );
    } catch (toggleError) {
      setError(
        toggleError instanceof Error
          ? toggleError.message
          : "Could not update protection.",
      );
    } finally {
      setProtectionBusy(false);
    }
  }

  function handleCvFileChange(file: File | null) {
    if (!file) {
      return;
    }

    setError("");
    setCvFile(file);
    setResult(null);
  }

  function clearUploadedCv() {
    setCvFile(null);
    setFileInputKey((current) => current + 1);
    setResult(null);
  }

  function loadSampleAsFile(
    sampleId: "safe" | "attack",
  ) {
    if (!samples) {
      return;
    }

    const sample =
      sampleId === "safe"
        ? samples.safe
        : samples.attack;

    const file = new File(
      [sample.cv_text],
      `${sample.id}_sample.txt`,
      { type: "text/plain" },
    );

    setCvFile(file);
    setFileInputKey((current) => current + 1);
    setResult(null);
    setError("");
  }

  async function handleProcess(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!cvFile || busy) {
      return;
    }

    setBusy(true);
    setError("");
    setResult(null);

    try {
      const response = await processHrCvUpload({
        file: cvFile,
        clientId,
        targetRole:
          targetRole.trim() || "Software Engineer",
      });
      setResult(response);
      setProtectionEnabled(
        Boolean(response.protection_enabled),
      );
    } catch (processError) {
      setError(
        processError instanceof Error
          ? processError.message
          : "HR processing failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  function shieldClass(status: string) {
    const normalized = status.toUpperCase();
    if (normalized === "BLOCKED") {
      return "hr-badge blocked";
    }
    if (normalized === "BYPASSED") {
      return "hr-badge bypassed";
    }
    return "hr-badge allowed";
  }

  if (checkingAuth || !user) {
    return (
      <div className="wrdn-application">
        <main className="application-content">
          <p style={{ padding: 24 }}>
            Loading HR processor...
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="wrdn-application">
      <AppSidebar
        activeSection="hr"
        onSectionChange={(section) => {
          if (section === "hr") {
            return;
          }
          if (section === "policies") {
            router.push("/policies");
            return;
          }
          if (section === "chat") {
            router.push("/?section=chat");
            return;
          }
          router.push(`/?section=${section}`);
        }}
        onNewChat={() =>
          router.push("/?section=chat")
        }
        isAdmin={isAdmin}
        username={user.username}
        onLogout={handleLogout}
      />

      <main className="application-content">
        <section className="hr-page">
          <header className="chat-header">
            <div>
              <h1>HR Candidate Processor</h1>
              <p>
                CV upload → two agents → outbound
                email, with WRDN shielding the leak
                path.
              </p>
            </div>

            <div
              className={`chat-header-status${
                protectionEnabled
                  ? ""
                  : " protection-off"
              }`}
            >
              <span className="protection-dot" />
              {protectionEnabled
                ? "WRDN protection ON"
                : "WRDN protection OFF (BYPASSED)"}
            </div>
          </header>

          <div className="hr-shell">
            <div className="hr-demo-strip">
              <p>
                <strong>Demo flow:</strong> load
                Attack CV → Process. With protection
                OFF the email may leak (BYPASSED).
                With protection ON the leak is
                BLOCKED.
              </p>

              {isAdmin && (
                <button
                  type="button"
                  className="hr-toggle"
                  disabled={protectionBusy}
                  onClick={() =>
                    void toggleProtection()
                  }
                >
                  {protectionBusy
                    ? "Updating…"
                    : protectionEnabled
                      ? "Disable WRDN"
                      : "Enable WRDN"}
                </button>
              )}
            </div>

            <div className="hr-layout">
              <form
                className="hr-panel"
                onSubmit={handleProcess}
              >
                <div className="hr-panel-head">
                  <h2>1. Candidate CV</h2>
                  <p>
                    Upload a PDF, DOCX, or TXT file.
                    The file is sent to the backend for
                    AI evaluation — no text paste needed.
                  </p>
                </div>

                <div className="hr-upload-box">
                  <div className="hr-upload-head">
                    <strong>Upload CV</strong>
                    <span>
                      PDF, DOCX, or TXT
                    </span>
                  </div>

                  <input
                    key={fileInputKey}
                    type="file"
                    accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    disabled={busy}
                    onChange={(event) => {
                      const file =
                        event.target.files?.[0] ||
                        null;
                      handleCvFileChange(file);
                    }}
                  />

                  {cvFile ? (
                    <div className="hr-upload-meta">
                      <p>
                        Ready:{" "}
                        <strong>{cvFile.name}</strong>
                        <span className="hr-file-size">
                          {" "}
                          (
                          {Math.max(
                            1,
                            Math.round(
                              cvFile.size / 1024,
                            ),
                          )}{" "}
                          KB)
                        </span>
                      </p>
                      <button
                        type="button"
                        className="hr-sample-btn"
                        onClick={clearUploadedCv}
                      >
                        Clear file
                      </button>
                    </div>
                  ) : (
                    <p className="hr-hint">
                      Choose a CV file from{" "}
                      <code>wrdn/hr_demo_cvs</code>{" "}
                      or your own resume.
                    </p>
                  )}
                </div>

                <div className="hr-sample-row">
                  <button
                    type="button"
                    className="hr-sample-btn"
                    disabled={!samples || busy}
                    onClick={() =>
                      loadSampleAsFile("safe")
                    }
                  >
                    Load safe CV
                  </button>
                  <button
                    type="button"
                    className="hr-sample-btn attack"
                    disabled={!samples || busy}
                    onClick={() =>
                      loadSampleAsFile("attack")
                    }
                  >
                    Load attack CV
                  </button>
                </div>

                {samples?.attack.description ? (
                  <p className="hr-hint">
                    {samples.attack.description}
                  </p>
                ) : null}

                <label className="hr-field">
                  <span>Target role</span>
                  <input
                    value={targetRole}
                    onChange={(event) =>
                      setTargetRole(
                        event.target.value,
                      )
                    }
                    placeholder="Software Engineer"
                  />
                </label>

                <button
                  type="submit"
                  className="hr-submit"
                  disabled={busy || !cvFile}
                >
                  {busy
                    ? "Uploading & running agents…"
                    : "Process uploaded CV → Agents → Email"}
                </button>

                {error ? (
                  <p className="hr-error">{error}</p>
                ) : null}
              </form>

              <div className="hr-results">
                {!result && !busy ? (
                  <div className="hr-empty">
                    <h2>Pipeline idle</h2>
                    <p>
                      Upload a CV file. The backend
                      extracts it, Agent 1 evaluates,
                      Agent 2 drafts the candidate
                      email, and WRDN shields that
                      outbound email before dispatch.
                    </p>
                  </div>
                ) : null}

                {busy ? (
                  <div className="hr-empty">
                    <h2>Processing</h2>
                    <p>
                      Agent 1 evaluating → Agent 2
                      drafting email → WRDN
                      shielding…
                    </p>
                  </div>
                ) : null}

                {result ? (
                  <>
                    <div className="hr-panel">
                      <div className="hr-panel-head row">
                        <div>
                          <h2>
                            WRDN email shield
                          </h2>
                          <p>
                            {result.shield.layer}
                          </p>
                        </div>
                        <span
                          className={shieldClass(
                            result.shield.status,
                          )}
                        >
                          {result.shield.status}
                        </span>
                      </div>

                      <div className="hr-meta-grid">
                        <div>
                          <span>Risk</span>
                          <strong>
                            {result.shield.risk_score}
                          </strong>
                        </div>
                        <div>
                          <span>Dispatched</span>
                          <strong>
                            {result.email_dispatched
                              ? "Yes"
                              : "No"}
                          </strong>
                        </div>
                        <div>
                          <span>Protection</span>
                          <strong>
                            {result.protection_enabled
                              ? "ON"
                              : "OFF"}
                          </strong>
                        </div>
                      </div>

                      <p className="hr-reason">
                        {result.shield.reason}
                      </p>

                      {result.email_send ? (
                        <p className="hr-hint">
                          Mailtrap:{" "}
                          {result.email_send.message}
                          {result.email_send.sent &&
                          result.email_send.delivered_to
                            ? ` Check inbox for ${result.email_send.delivered_to}.`
                            : ""}
                        </p>
                      ) : null}

                      {result.shield.leak_findings
                        .length > 0 ? (
                        <ul className="hr-findings">
                          {result.shield.leak_findings.map(
                            (finding) => (
                              <li key={finding}>
                                {finding}
                              </li>
                            ),
                          )}
                        </ul>
                      ) : null}

                      <p className="hr-hint">
                        {result.demo_hint}
                      </p>
                    </div>

                    <div className="hr-panel">
                      <div className="hr-panel-head">
                        <h2>
                          2. {result.agent_1.name}
                        </h2>
                        <p>
                          Internal evaluation (not
                          emailed to the candidate).
                        </p>
                      </div>
                      <pre className="hr-json">
                        {JSON.stringify(
                          result.agent_1.evaluation,
                          null,
                          2,
                        )}
                      </pre>
                    </div>

                    <div className="hr-panel">
                      <div className="hr-panel-head">
                        <h2>
                          3. {result.agent_2.name}
                        </h2>
                        <p>
                          Outbound email after WRDN
                          decision.
                        </p>
                      </div>

                      <div className="hr-email-meta">
                        <p>
                          <span>To</span>{" "}
                          {result.agent_2.email.to}
                        </p>
                        <p>
                          <span>Subject</span>{" "}
                          {
                            result.agent_2.email
                              .subject
                          }
                        </p>
                      </div>

                      <div className="hr-email-split">
                        <div>
                          <h3>Raw agent draft</h3>
                          <pre className="hr-email-body">
                            {
                              result.agent_2.email
                                .body_raw
                            }
                          </pre>
                        </div>
                        <div>
                          <h3>Final (shielded)</h3>
                          <pre className="hr-email-body">
                            {
                              result.agent_2.email
                                .body_final
                            }
                          </pre>
                        </div>
                      </div>
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        </section>
      </main>

      <style>{`
        .hr-page {
          display: flex;
          flex-direction: column;
          gap: 16px;
          min-height: 100%;
          padding: 18px 20px 28px;
        }

        .hr-shell {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .hr-demo-strip {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 14px;
          padding: 12px 14px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 14px;
          background: rgba(32, 228, 135, 0.06);
        }

        .hr-demo-strip p {
          margin: 0;
          color: #aeb6c2;
          font-size: 13px;
          line-height: 1.45;
        }

        .hr-toggle {
          flex-shrink: 0;
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.04);
          color: #e8edf5;
          padding: 8px 12px;
          font-size: 12px;
          cursor: pointer;
        }

        .hr-layout {
          display: grid;
          grid-template-columns: minmax(280px, 0.95fr) minmax(0, 1.15fr);
          gap: 14px;
          align-items: start;
        }

        .hr-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 14px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          background: rgba(255, 255, 255, 0.03);
        }

        .hr-panel-head h2 {
          margin: 0 0 4px;
          font-size: 16px;
          color: #e8edf5;
        }

        .hr-panel-head p {
          margin: 0;
          color: #7d8694;
          font-size: 12px;
        }

        .hr-panel-head.row {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
        }

        .hr-sample-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .hr-upload-box {
          display: grid;
          gap: 10px;
          padding: 12px;
          border: 1px dashed rgba(32, 228, 135, 0.35);
          border-radius: 12px;
          background: rgba(32, 228, 135, 0.04);
        }

        .hr-upload-head {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 10px;
        }

        .hr-upload-head strong {
          color: #e8edf5;
          font-size: 13px;
        }

        .hr-upload-head span {
          color: #8b93a0;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .hr-upload-box input[type="file"] {
          width: 100%;
          color: #b9c0ca;
          font-size: 12px;
        }

        .hr-upload-meta {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
        }

        .hr-upload-meta p {
          margin: 0;
          color: #b9c0ca;
          font-size: 12px;
        }

        .hr-upload-meta strong {
          color: #20e487;
        }

        .hr-file-size {
          color: #8b93a0;
          font-weight: 400;
        }

        .hr-upload-box code {
          color: #d5dbe5;
          font-size: 11px;
        }

        .hr-sample-btn {
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.04);
          color: #d5dbe5;
          padding: 8px 11px;
          font-size: 12px;
          cursor: pointer;
        }

        .hr-sample-btn.attack {
          border-color: rgba(255, 107, 107, 0.35);
          color: #ffb4b4;
        }

        .hr-field {
          display: grid;
          gap: 6px;
        }

        .hr-field span {
          color: #8b93a0;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .hr-field input,
        .hr-field textarea {
          width: 100%;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          background: rgba(0, 0, 0, 0.25);
          color: #e8edf5;
          padding: 10px 12px;
          font: inherit;
          resize: vertical;
        }

        .hr-submit {
          border: 0;
          border-radius: 12px;
          background: #20e487;
          color: #06140d;
          font-weight: 700;
          padding: 11px 14px;
          cursor: pointer;
        }

        .hr-submit:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }

        .hr-error {
          margin: 0;
          color: #ff8f8f;
          font-size: 13px;
        }

        .hr-hint {
          margin: 0;
          color: #8b93a0;
          font-size: 12px;
          line-height: 1.4;
        }

        .hr-results {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .hr-empty {
          padding: 28px 18px;
          border: 1px dashed rgba(255, 255, 255, 0.12);
          border-radius: 16px;
          color: #8b93a0;
        }

        .hr-empty h2 {
          margin: 0 0 8px;
          color: #d5dbe5;
          font-size: 16px;
        }

        .hr-empty p {
          margin: 0;
          font-size: 13px;
          line-height: 1.5;
        }

        .hr-badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 5px 10px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.04em;
        }

        .hr-badge.allowed {
          background: rgba(32, 228, 135, 0.15);
          color: #20e487;
        }

        .hr-badge.blocked {
          background: rgba(255, 92, 92, 0.18);
          color: #ff8f8f;
        }

        .hr-badge.bypassed {
          background: rgba(255, 184, 77, 0.18);
          color: #ffb84d;
        }

        .hr-meta-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
        }

        .hr-meta-grid > div {
          padding: 10px 11px;
          border-radius: 12px;
          border: 1px solid rgba(255, 255, 255, 0.06);
          background: rgba(255, 255, 255, 0.03);
          display: grid;
          gap: 4px;
        }

        .hr-meta-grid span {
          color: #6f7884;
          font-size: 10px;
          text-transform: uppercase;
        }

        .hr-meta-grid strong {
          color: #d5dbe5;
          font-size: 13px;
        }

        .hr-reason {
          margin: 0;
          color: #b9c0ca;
          font-size: 13px;
          line-height: 1.45;
        }

        .hr-findings {
          margin: 0;
          padding-left: 18px;
          color: #ffb4b4;
          font-size: 12px;
        }

        .hr-json,
        .hr-email-body {
          margin: 0;
          padding: 12px;
          border-radius: 12px;
          background: rgba(0, 0, 0, 0.28);
          border: 1px solid rgba(255, 255, 255, 0.06);
          color: #c5ccd6;
          font-size: 12px;
          line-height: 1.45;
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 280px;
          overflow: auto;
        }

        .hr-email-meta p {
          margin: 0 0 6px;
          color: #d5dbe5;
          font-size: 13px;
        }

        .hr-email-meta span {
          color: #6f7884;
          text-transform: uppercase;
          font-size: 10px;
          margin-right: 6px;
        }

        .hr-email-split {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }

        .hr-email-split h3 {
          margin: 0 0 8px;
          color: #8b93a0;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        @media (max-width: 980px) {
          .hr-layout,
          .hr-email-split,
          .hr-meta-grid {
            grid-template-columns: 1fr;
          }

          .hr-demo-strip {
            flex-direction: column;
            align-items: stretch;
          }
        }
      `}</style>
    </div>
  );
}
