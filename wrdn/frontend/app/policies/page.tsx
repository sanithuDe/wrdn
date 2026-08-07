"use client";

import { useRouter } from "next/navigation";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";

import AppSidebar from "@/components/AppSidebar";

import {
    activatePolicy,
    analyzeRequirement,
    deletePolicy,
    listPolicies,
    rollbackPolicy,
    uploadRequirement,
    validatePolicy,
} from "@/lib/api";

import type {
    PolicyGenerationResponse,
    PolicyHistoryItem,
} from "@/lib/api";

import {
    clearAuthSession,
    getAuthUser,
    type AuthUser,
} from "@/lib/authApi";

type Step = 1 | 2 | 3 | 4;

type Notice = {
  type: "success" | "error" | "info";
  message: string;
} | null;

const steps: Array<{
  number: Step;
  title: string;
  description: string;
}> = [
  {
    number: 1,
    title: "Requirements",
    description: "Upload file",
  },
  {
    number: 2,
    title: "Generate",
    description: "Gemini policy",
  },
  {
    number: 3,
    title: "Activate",
    description: "Validate policy",
  },
  {
    number: 4,
    title: "History",
    description: "View versions",
  },
];

export default function PoliciesPage() {
  const router = useRouter();

  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  const [activeStep, setActiveStep] = useState<Step>(1);
  const [completedStep, setCompletedStep] = useState(0);

  const [clientId, setClientId] = useState("");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const [requirementId, setRequirementId] = useState("");
  const [filePreview, setFilePreview] = useState("");

  const [generatedPolicy, setGeneratedPolicy] =
    useState<PolicyGenerationResponse | null>(null);

  const [policyHistory, setPolicyHistory] =
    useState<PolicyHistoryItem[]>([]);

  const [notice, setNotice] = useState<Notice>(null);
  const [busyAction, setBusyAction] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{
    policyId: number;
    clientId: string;
    policyName: string;
  } | null>(null);

  const isAdmin = user?.role === "ADMIN";

  function handleLogout() {
    clearAuthSession();
    router.push("/login");
  }

  useEffect(() => {
    const currentUser = getAuthUser();
  
    if (!currentUser) {
      router.push("/login");
      return;
    }
  
    if (currentUser.role !== "ADMIN") {
      router.push("/");
      return;
    }
  
    setUser(currentUser);
    setClientId(currentUser.client_id);
    setCheckingAuth(false);
  }, [router]);
  
  useEffect(() => {
    if (checkingAuth || !clientId.trim()) {
      return;
    }
  
    let cancelled = false;
  
    setBusyAction("history");
  
    void listPolicies(clientId.trim())
      .then((result) => {
        if (cancelled) {
          return;
        }
  
        setPolicyHistory(result);
  
        if (result.length > 0) {
          setCompletedStep(4);
          setActiveStep(4);
        } else {
          setCompletedStep(0);
          setActiveStep(1);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
  
        setNotice({
          type: "error",
          message:
            error instanceof Error
              ? error.message
              : "Could not load policy history.",
        });
      })
      .finally(() => {
        if (!cancelled) {
          setBusyAction("");
        }
      });
  
    return () => {
      cancelled = true;
    };
  }, [checkingAuth, clientId]);

  function showError(error: unknown) {
    setNotice({
      type: "error",
      message:
        error instanceof Error
          ? error.message
          : "Something went wrong.",
    });
  }

  function completeStep(step: Step, nextStep?: Step) {
    setCompletedStep((current) => Math.max(current, step));

    if (nextStep) {
      setActiveStep(nextStep);
    }
  }

  async function handleUpload(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!clientId.trim()) {
      setNotice({
        type: "error",
        message: "No client linked to this admin account.",
      });
      return;
    }

    if (!selectedFile) {
      setNotice({
        type: "error",
        message: "Please select a requirement file.",
      });
      return;
    }

    setBusyAction("upload");
    setNotice(null);

    try {
      const result = await uploadRequirement(
        clientId.trim(),
        selectedFile,
      );

      setRequirementId(String(result.requirement_id));
      setFilePreview(result.text_preview);
      setSelectedFile(null);
      setFileInputKey((currentKey) => currentKey + 1);

      setNotice({
        type: "success",
        message: `${result.filename} uploaded successfully.`,
      });

      completeStep(1, 2);
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }

  async function handleGenerate(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const parsedId = Number(requirementId);

    if (!Number.isInteger(parsedId) || parsedId <= 0) {
      setNotice({
        type: "error",
        message: "Please enter a valid requirement ID.",
      });
      return;
    }

    setBusyAction("generate");
    setNotice(null);

    try {
      const result = await analyzeRequirement(
        parsedId,
        clientId.trim(),
      );

      setGeneratedPolicy({
        ...result,
        client_id: clientId.trim(),
      });

      setNotice({
        type: "success",
        message: `Policy version ${result.version} generated successfully.`,
      });

      completeStep(2, 3);
      await loadHistory();
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }

  async function handleValidate() {
    if (!generatedPolicy) {
      return;
    }

    setBusyAction("validate");
    setNotice(null);

    try {
      const result = await validatePolicy(
        generatedPolicy.policy_id,
        clientId.trim(),
      );

      setGeneratedPolicy((current) =>
        current
          ? {
              ...current,
              status: result.status,
              validation_errors: result.validation_errors,
            }
          : current,
      );

      setNotice({
        type: result.status === "VALIDATED" ? "success" : "error",
        message:
          result.status === "VALIDATED"
            ? "Policy validated successfully."
            : "Policy validation failed.",
      });
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }

  async function handleActivate() {
    if (!generatedPolicy) {
      return;
    }

    setBusyAction("activate");
    setNotice(null);

    try {
      const result = await activatePolicy(
        generatedPolicy.policy_id,
        clientId.trim(),
      );

      setGeneratedPolicy((current) =>
        current
          ? {
              ...current,
              status: result.status,
            }
          : current,
      );

      setNotice({
        type: "success",
        message: "Policy activated successfully.",
      });

      completeStep(3, 4);
      await loadHistory();
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }

  async function loadHistory() {
    setBusyAction("history");

    try {
      const result = await listPolicies(clientId.trim());
      setPolicyHistory(result);
      setCompletedStep(4);
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }
  function askDelete(
    policyId: number,
    policyClientId: string,
    policyName: string,
  ) {
    setDeleteTarget({
      policyId,
      clientId: policyClientId,
      policyName,
    });
  }

  async function confirmDelete() {
    if (!deleteTarget) {
      return;
    }

    const { policyId, clientId: policyClientId } =
      deleteTarget;

    setDeleteTarget(null);
    setBusyAction(`delete-${policyId}`);

    try {
      await deletePolicy(policyId, policyClientId);

      setNotice({
        type: "success",
        message: `Policy ${policyId} deleted.`,
      });

      if (generatedPolicy?.policy_id === policyId) {
        setGeneratedPolicy(null);
      }

      await loadHistory();
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }

  async function handleRollback(
    policyId: number,
    policyClientId: string,
  ) {
    setBusyAction(`rollback-${policyId}`);

    try {
      await rollbackPolicy(policyId, policyClientId);

      setNotice({
        type: "success",
        message: `Policy ${policyId} restored successfully.`,
      });

      await loadHistory();
    } catch (error) {
      showError(error);
    } finally {
      setBusyAction("");
    }
  }

  function openStep(step: Step) {
    setActiveStep(step);

    if (step === 4) {
      void loadHistory();
    }
  }

  if (checkingAuth || !user) {
    return (
      <div className="wrdn-application">
        <main className="application-content">
          <p style={{ padding: 24 }}>Loading policy panel...</p>
        </main>
      </div>
    );
  }

  return (
    <div className="wrdn-application">
      <AppSidebar
        activeSection="policies"
        onSectionChange={(section) => {
          if (section === "policies") {
            return;
          }

          if (section === "chat") {
            router.push("/?section=chat");
            return;
          }

          router.push(`/?section=${section}`);
        }}
        onNewChat={() => router.push("/?section=chat")}
        isAdmin={isAdmin}
        username={user.username}
        onLogout={handleLogout}
      />

      <main className="application-content">
        <section className="policy-page">
          <header className="chat-header">
            <div>
    

              <h1>Client Policy Management</h1>
              <p>
                Build, activate, and restore client-specific
                output-security policies.
              </p>
            </div>

            <div className="chat-header-status">
              <span className="protection-dot" />
              Your client: {clientId.trim() || "—"}
            </div>
          </header>

          <div className="policy-shell">
            <nav className="stepper">
              {steps.map((step) => {
                const completed = step.number <= completedStep;
                const current = step.number === activeStep;

                return (
                  <button
                    key={step.number}
                    type="button"
                    className={`step ${
                      current ? "current" : ""
                    } ${completed ? "completed" : ""}`}
                    onClick={() => openStep(step.number)}
                  >
                    <span className="step-number">
                      {completed ? "✓" : step.number}
                    </span>

                    <span className="step-text">
                      <strong>{step.title}</strong>
                      <small>{step.description}</small>
                    </span>
                  </button>
                );
              })}
            </nav>

            <div className="workspace">
              <section className="main-panel">
                <div className="panel-scroll">
                  {activeStep === 1 && (
                    <>
                      <StepHeader
                        number="01"
                        title="Upload requirements"
                        description="Upload a requirement file for your customer. You can upload again anytime to create a new policy version."
                      />

                      <form
                        onSubmit={handleUpload}
                        className="form"
                      >
                        <label className="dropzone">
                          <input
                            key={fileInputKey}
                            type="file"
                            accept=".pdf,.docx,.txt,.json"
                            onChange={(event) =>
                              setSelectedFile(
                                event.target.files?.[0] || null,
                              )
                            }
                          />

                          <span className="upload-icon">↑</span>

                          <strong>
                            {selectedFile
                              ? selectedFile.name
                              : "Choose requirement file"}
                          </strong>

                          <small>PDF, DOCX, TXT or JSON</small>
                        </label>

                        {filePreview && (
                          <div className="preview">
                            <strong>Extracted text preview</strong>
                            <pre>{filePreview}</pre>
                          </div>
                        )}

                        <div className="actions">
                          <PrimaryButton
                            loading={busyAction === "upload"}
                            text="Upload Requirements"
                            loadingText="Uploading..."
                          />
                        </div>
                      </form>
                    </>
                  )}

                  {activeStep === 2 && (
                    <>
                      <StepHeader
                        number="02"
                        title="Generate Gemini policy"
                        description="Analyze the uploaded requirements and create a draft policy."
                      />

                      <form
                        onSubmit={handleGenerate}
                        className="form"
                      >
                        <Field
                          label="Requirement ID"
                          hint="Automatically added after the upload."
                        >
                          <input
                            type="number"
                            min="1"
                            value={requirementId}
                            onChange={(event) =>
                              setRequirementId(event.target.value)
                            }
                            placeholder="1"
                            required
                          />
                        </Field>

                        <div className="actions">
                          <SecondaryButton
                            text="Back"
                            onClick={() => setActiveStep(1)}
                          />

                          <PrimaryButton
                            loading={busyAction === "generate"}
                            text="Generate Policy"
                            loadingText="Generating with Gemini..."
                          />
                        </div>
                      </form>

                      {generatedPolicy && (
                        <div className="policy-preview">
                          <div className="preview-title">
                            <strong>Generated policy</strong>
                            <StatusBadge
                              status={generatedPolicy.status}
                            />
                          </div>

                          <pre>
                            {JSON.stringify(
                              generatedPolicy.policy,
                              null,
                              2,
                            )}
                          </pre>
                        </div>
                      )}
                    </>
                  )}

                  {activeStep === 3 && (
                    <>
                      <StepHeader
                        number="03"
                        title="Validate and activate"
                        description="Check the generated policy before activating it."
                      />

                      {!generatedPolicy ? (
                        <EmptyState text="Generate a policy in Step 2 first." />
                      ) : (
                        <div className="activation-card">
                          <div className="detail-grid">
                            <Detail
                              label="Policy ID"
                              value={String(
                                generatedPolicy.policy_id,
                              )}
                            />

                            <Detail
                              label="Version"
                              value={String(generatedPolicy.version)}
                            />

                            <Detail
                              label="Client"
                              value={clientId.trim()}
                            />

                            <Detail
                              label="Status"
                              value={generatedPolicy.status}
                            />
                          </div>

                          {generatedPolicy.validation_errors.length >
                            0 && (
                            <div className="error-list">
                              <strong>Validation errors</strong>

                              {generatedPolicy.validation_errors.map(
                                (error) => (
                                  <p key={error}>{error}</p>
                                ),
                              )}
                            </div>
                          )}

                          <div className="actions">
                            <SecondaryButton
                              text="Back"
                              onClick={() => setActiveStep(2)}
                            />

                            <button
                              type="button"
                              className="secondary-button"
                              onClick={handleValidate}
                              disabled={busyAction === "validate"}
                            >
                              {busyAction === "validate"
                                ? "Validating..."
                                : "Validate Policy"}
                            </button>

                            <button
                              type="button"
                              className="primary-button"
                              onClick={handleActivate}
                              disabled={
                                generatedPolicy.status !==
                                  "VALIDATED" ||
                                busyAction === "activate"
                              }
                            >
                              {busyAction === "activate"
                                ? "Activating..."
                                : "Approve and Activate"}
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {activeStep === 4 && (
                    <>
                      <StepHeader
                        number="04"
                        title="Policy history"
                        description="Compare each version’s blocked categories, sensitive patterns, and allowed actions."
                      />

                      <div className="history-header">
                        <span>
                          {policyHistory.length} policy version(s)
                        </span>

                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => void loadHistory()}
                        >
                          {busyAction === "history"
                            ? "Refreshing..."
                            : "Refresh"}
                        </button>
                      </div>

                      <div className="history-list">
                        {policyHistory.length === 0 ? (
                          <EmptyState text="No policies found." />
                        ) : (
                          policyHistory.map((policy) => {
                            const details = policy.Policy;
                            const blocked =
                              details?.blocked_categories || [];
                            const patterns =
                              details?.sensitive_pattern_ids || [];
                            const allowedSecrets =
                              details?.allowed_secret_names || [];
                            const blockedSecrets =
                              details?.blocked_secret_names || [];
                            const allowedSalaries =
                              details?.allowed_employee_salary_names || [];
                            const blockedSalaries =
                              details?.blocked_employee_salary_names || [];
                            const allowed =
                              details?.allowed_actions || [];

                            return (
                              <article
                                className="history-item"
                                key={policy.PolicyID}
                              >
                                <div className="history-item-top">
                                  <div>
                                    <strong>{policy.PolicyName}</strong>

                                    <p>
                                      Client {policy.ClientID} · Version{" "}
                                      {policy.Version} · Policy ID{" "}
                                      {policy.PolicyID}
                                      {details?.risk_threshold != null
                                        ? ` · Risk ${details.risk_threshold}`
                                        : ""}
                                    </p>
                                  </div>

                                  <div className="history-actions">
                                    <StatusBadge
                                      status={policy.Status}
                                    />

                                    {policy.Status === "INACTIVE" && (
                                      <button
                                        type="button"
                                        className="small-button"
                                        onClick={() =>
                                          void handleRollback(
                                            policy.PolicyID,
                                            policy.ClientID,
                                          )
                                        }
                                      >
                                        Restore
                                      </button>
                                    )}

                                    {policy.Status !== "ACTIVE" && (
                                      <button
                                        type="button"
                                        className="small-button delete-button"
                                        disabled={
                                          busyAction ===
                                          `delete-${policy.PolicyID}`
                                        }
                                        onClick={() =>
                                          askDelete(
                                            policy.PolicyID,
                                            policy.ClientID,
                                            policy.PolicyName,
                                          )
                                        }
                                      >
                                        {busyAction ===
                                        `delete-${policy.PolicyID}`
                                          ? "Deleting..."
                                          : "Delete"}
                                      </button>
                                    )}
                                  </div>
                                </div>

                                <div className="history-details">
                                  <div className="history-detail-block">
                                    <span>Blocked categories</span>
                                    <div className="tag-row">
                                      {blocked.length > 0 ? (
                                        blocked.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-b-${item}`}
                                            className="tag tag-blocked"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Sensitive patterns</span>
                                    <div className="tag-row">
                                      {patterns.length > 0 ? (
                                        patterns.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-p-${item}`}
                                            className="tag tag-pattern"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Allowed secrets</span>
                                    <div className="tag-row">
                                      {allowedSecrets.length > 0 ? (
                                        allowedSecrets.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-as-${item}`}
                                            className="tag tag-allowed"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Blocked secrets</span>
                                    <div className="tag-row">
                                      {blockedSecrets.length > 0 ? (
                                        blockedSecrets.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-bs-${item}`}
                                            className="tag tag-blocked"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Allowed salaries</span>
                                    <div className="tag-row">
                                      {allowedSalaries.length > 0 ? (
                                        allowedSalaries.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-asal-${item}`}
                                            className="tag tag-allowed"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Blocked salaries</span>
                                    <div className="tag-row">
                                      {blockedSalaries.length > 0 ? (
                                        blockedSalaries.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-bsal-${item}`}
                                            className="tag tag-blocked"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Allowed actions</span>
                                    <div className="tag-row">
                                      {allowed.length > 0 ? (
                                        allowed.map((item) => (
                                          <em
                                            key={`${policy.PolicyID}-a-${item}`}
                                            className="tag tag-allowed"
                                          >
                                            {item}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None listed</small>
                                      )}
                                    </div>
                                  </div>

                                  {details?.blocked_response && (
                                    <div className="history-detail-block">
                                      <span>Blocked response</span>
                                      <p>{details.blocked_response}</p>
                                    </div>
                                  )}
                                </div>
                              </article>
                            );
                          })
                        )}
                      </div>
                    </>
                  )}
                </div>
              </section>

              <aside className="summary-panel">
                <h2>Workflow status</h2>

                <SummaryRow
                  label="Client"
                  value={clientId.trim() || "—"}
                />

                <SummaryRow
                  label="Requirement"
                  value={
                    requirementId
                      ? `#${requirementId}`
                      : "Not uploaded"
                  }
                />

                <SummaryRow
                  label="Policy"
                  value={
                    generatedPolicy
                      ? `#${generatedPolicy.policy_id}`
                      : "Not generated"
                  }
                />

                <SummaryRow
                  label="Version"
                  value={
                    generatedPolicy
                      ? `v${generatedPolicy.version}`
                      : "—"
                  }
                />

                <SummaryRow
                  label="Status"
                  value={generatedPolicy?.status || "Waiting"}
                />

                <div className="security-note">
                  <span>🛡</span>
                  <div>
                    <strong>Manual activation</strong>
                    <p>
                      Gemini-generated policies never activate
                      automatically.
                    </p>
                  </div>
                </div>
              </aside>
            </div>

            {deleteTarget && (
              <div className="delete-modal-backdrop">
                <div className="delete-modal">
                  <div className="delete-modal-icon">!</div>

                  <h3>Delete this policy?</h3>

                  <p>
                    <strong>{deleteTarget.policyName}</strong>
                    <br />
                    Policy ID {deleteTarget.policyId} will be
                    removed from history permanently.
                  </p>

                  <div className="delete-modal-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => setDeleteTarget(null)}
                    >
                      Keep policy
                    </button>

                    <button
                      type="button"
                      className="delete-confirm-button"
                      onClick={() => void confirmDelete()}
                    >
                      Delete forever
                    </button>
                  </div>
                </div>
              </div>
            )}

            {notice && (
              <div className={`notice ${notice.type}`}>
                {notice.message}

                <button
                  type="button"
                  onClick={() => setNotice(null)}
                >
                  ×
                </button>
              </div>
            )}
          </div>

          <style jsx global>{`
            button,
            input {
              font: inherit;
            }
              .delete-button {
  border-color: rgba(239, 68, 68, 0.35);
  color: #fecaca;
}

.delete-button:hover {
  background: rgba(127, 29, 29, 0.25);
}

.delete-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  background: rgba(5, 7, 12, 0.72);
  backdrop-filter: blur(6px);
}

.delete-modal {
  width: min(420px, calc(100% - 32px));
  padding: 24px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 18px;
  background:
    linear-gradient(
      180deg,
      rgba(239, 68, 68, 0.08),
      transparent 40%
    ),
    #080a0f;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
  text-align: center;
}

.delete-modal-icon {
  width: 46px;
  height: 46px;
  margin: 0 auto 14px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: #05070c;
  background: #f87171;
  font-size: 22px;
  font-weight: 900;
}

.delete-modal h3 {
  margin: 0 0 8px;
  color: #fff;
  font-size: 20px;
  letter-spacing: -0.03em;
}

.delete-modal p {
  margin: 0 0 20px;
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.55;
}

.delete-modal strong {
  color: #e2e8f0;
}

.delete-modal-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.delete-confirm-button {
  padding: 11px 16px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: #dc2626;
  font-weight: 800;
  cursor: pointer;
}

.delete-confirm-button:hover {
  background: #ef4444;
}

            .policy-page {
              height: 100%;
              min-width: 0;
              display: grid;
              grid-template-rows: auto minmax(0, 1fr);
              color: #ffffff;
              background: #080a0f;
            }

            .policy-shell {
              min-height: 0;
              padding: 18px 22px 24px;
              display: grid;
              grid-template-rows: auto minmax(0, 1fr);
              gap: 14px;
            }

            .stepper {
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              overflow: hidden;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 14px;
              background: rgba(8, 10, 15, 0.95);
            }

            .step {
              display: flex;
              align-items: center;
              gap: 10px;
              min-width: 0;
              padding: 14px 12px;
              border: 0;
              border-right: 1px solid rgba(255, 255, 255, 0.06);
              color: #7d8590;
              background: transparent;
              cursor: pointer;
              text-align: left;
              transition: 0.18s ease;
            }

            .step:last-child {
              border-right: 0;
            }

            .step:hover {
              background: rgba(255, 255, 255, 0.03);
            }

            .step.current {
              color: #f8fafc;
              background: rgba(32, 228, 135, 0.1);
            }

            .step.completed {
              color: #cbd5e1;
            }

            .step-number {
              display: grid;
              place-items: center;
              flex: 0 0 30px;
              width: 30px;
              height: 30px;
              border: 1px solid rgba(255, 255, 255, 0.12);
              border-radius: 10px;
              font-size: 12px;
              font-weight: 800;
            }

            .step.current .step-number {
              border-color: transparent;
              color: #05070c;
              background: #20e487;
            }

            .step.completed .step-number {
              border-color: transparent;
              color: #bbf7d0;
              background: #14532d;
            }

            .step-text {
              min-width: 0;
            }

            .step-text strong,
            .step-text small {
              display: block;
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }

            .step-text strong {
              font-size: 12px;
            }

            .step-text small {
              margin-top: 3px;
              color: #64748b;
              font-size: 10px;
            }

            .workspace {
              min-height: 0;
              display: grid;
              grid-template-columns: minmax(0, 1fr) 280px;
              gap: 14px;
            }

            .main-panel,
            .summary-panel {
              min-height: 0;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 14px;
              background: rgba(8, 10, 15, 0.95);
            }

            .main-panel {
              overflow: hidden;
            }

            .panel-scroll {
              height: 100%;
              overflow-y: auto;
              padding: 24px;
            }

            .step-heading {
              display: flex;
              align-items: flex-start;
              gap: 14px;
              margin-bottom: 22px;
            }

            .heading-number {
              display: grid;
              place-items: center;
              flex: 0 0 46px;
              width: 46px;
              height: 46px;
              border-radius: 14px;
              color: #05070c;
              font-weight: 900;
              background: #20e487;
            }

            .step-heading h2 {
              margin: 0 0 4px;
              color: #f8fafc;
              font-size: 21px;
              font-weight: 800;
              letter-spacing: -0.035em;
            }

            .step-heading p {
              margin: 0;
              color: #7d8590;
              font-size: 13px;
            }

            .form {
              display: grid;
              gap: 18px;
            }

            .two-columns {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 16px;
            }

            .field label {
              display: block;
              margin-bottom: 7px;
              color: #e2e8f0;
              font-size: 13px;
              font-weight: 700;
            }

            .field input {
              width: 100%;
              padding: 12px 13px;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 12px;
              outline: none;
              color: #f8fafc;
              background: #05070c;
            }

            .field input:focus {
              border-color: #20e487;
              box-shadow: 0 0 0 3px rgba(32, 228, 135, 0.12);
            }

            .field small {
              display: block;
              margin-top: 6px;
              color: #64748b;
              font-size: 11px;
            }

            .dropzone {
              display: grid;
              place-items: center;
              min-height: 170px;
              padding: 20px;
              border: 1px dashed rgba(32, 228, 135, 0.55);
              border-radius: 14px;
              background: rgba(32, 228, 135, 0.04);
              cursor: pointer;
              text-align: center;
            }

            .dropzone input {
              display: none;
            }

            .upload-icon {
              display: grid;
              place-items: center;
              width: 46px;
              height: 46px;
              margin-bottom: 10px;
              border-radius: 14px;
              color: #05070c;
              background: #20e487;
              font-weight: 900;
            }

            .dropzone small {
              margin-top: 6px;
              color: #64748b;
            }

            .preview,
            .policy-preview {
              padding: 14px;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 14px;
              background: #05070c;
            }

            .preview pre,
            .policy-preview pre {
              max-height: 210px;
              overflow: auto;
              margin: 10px 0 0;
              color: #86efac;
              font-size: 11px;
              line-height: 1.5;
              white-space: pre-wrap;
            }

            .policy-preview {
              margin-top: 18px;
            }

            .preview-title {
              display: flex;
              align-items: center;
              justify-content: space-between;
            }

            .actions {
              display: flex;
              justify-content: flex-end;
              gap: 10px;
              margin-top: 4px;
            }

            .primary-button,
            .secondary-button,
            .small-button {
              padding: 11px 16px;
              border-radius: 12px;
              font-weight: 800;
              cursor: pointer;
            }

            .primary-button {
              border: 0;
              color: #05070c;
              background: #20e487;
            }

            .secondary-button {
              border: 1px solid rgba(255, 255, 255, 0.1);
              color: #cbd5e1;
              background: rgba(255, 255, 255, 0.03);
            }

            .small-button {
              padding: 7px 11px;
              border: 1px solid rgba(255, 255, 255, 0.1);
              color: #cbd5e1;
              background: rgba(255, 255, 255, 0.03);
              font-size: 11px;
            }

            button:disabled {
              opacity: 0.45;
              cursor: not-allowed;
            }

            .summary-panel {
              overflow: auto;
              padding: 18px;
            }

            .summary-panel h2 {
              margin: 0 0 16px;
              font-size: 15px;
            }

            .summary-row {
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 10px;
              padding: 12px 0;
              border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            }

            .summary-row span {
              color: #7d8590;
              font-size: 11px;
            }

            .summary-row strong {
              overflow: hidden;
              color: #e2e8f0;
              font-size: 12px;
              text-overflow: ellipsis;
              white-space: nowrap;
            }

            .security-note {
              display: flex;
              gap: 10px;
              margin-top: 18px;
              padding: 12px;
              border: 1px solid rgba(32, 228, 135, 0.2);
              border-radius: 14px;
              background: rgba(32, 228, 135, 0.07);
            }

            .security-note strong {
              font-size: 12px;
            }

            .security-note p {
              margin: 4px 0 0;
              color: #7d8590;
              font-size: 10px;
              line-height: 1.5;
            }

            .activation-card {
              display: grid;
              gap: 18px;
            }

            .detail-grid {
              display: grid;
              grid-template-columns: repeat(4, minmax(0, 1fr));
              gap: 10px;
            }

            .detail {
              padding: 13px;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 14px;
              background: #05070c;
            }

            .detail span,
            .detail strong {
              display: block;
            }

            .detail span {
              margin-bottom: 5px;
              color: #7d8590;
              font-size: 10px;
              text-transform: uppercase;
            }

            .detail strong {
              overflow: hidden;
              color: #f8fafc;
              text-overflow: ellipsis;
            }

            .error-list {
              padding: 12px;
              border: 1px solid #7f1d1d;
              border-radius: 12px;
              color: #fecaca;
              background: rgba(127, 29, 29, 0.2);
            }

            .error-list p {
              margin: 7px 0 0;
              font-size: 12px;
            }

            .status-badge {
              display: inline-block;
              padding: 5px 10px;
              border-radius: 999px;
              color: #dbeafe;
              background: #1e3a8a;
              font-size: 10px;
              font-weight: 800;
            }

            .status-badge.active,
            .status-badge.validated {
              color: #bbf7d0;
              background: #14532d;
            }

            .status-badge.inactive {
              color: #ddd6fe;
              background: #4c1d95;
            }

            .status-badge.rejected {
              color: #fecaca;
              background: #7f1d1d;
            }

            .history-header {
              display: flex;
              align-items: center;
              justify-content: space-between;
              margin-bottom: 12px;
              color: #94a3b8;
              font-size: 12px;
            }

            .history-list {
              display: grid;
              gap: 10px;
            }

            .history-item {
              display: grid;
              gap: 14px;
              padding: 14px;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 14px;
              background: #05070c;
            }

            .history-item-top {
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              gap: 12px;
            }

            .history-item p {
              margin: 4px 0 0;
              color: #64748b;
              font-size: 11px;
            }

            .history-details {
              display: grid;
              gap: 12px;
              padding-top: 4px;
              border-top: 1px solid rgba(255, 255, 255, 0.06);
            }

            .history-detail-block span {
              display: block;
              margin-bottom: 6px;
              color: #9aa4b2;
              font-size: 10px;
              font-weight: 800;
              letter-spacing: 0.06em;
              text-transform: uppercase;
            }

            .history-detail-block p {
              margin: 0;
              color: #cbd5e1;
              font-size: 12px;
              line-height: 1.5;
            }

            .history-detail-block small {
              color: #64748b;
              font-size: 11px;
            }

            .tag-row {
              display: flex;
              flex-wrap: wrap;
              gap: 6px;
            }

            .tag {
              display: inline-block;
              padding: 4px 8px;
              border-radius: 999px;
              font-size: 10px;
              font-style: normal;
              font-weight: 700;
            }

            .tag-blocked {
              color: #fecaca;
              background: rgba(127, 29, 29, 0.35);
            }

            .tag-pattern {
              color: #fde68a;
              background: rgba(120, 53, 15, 0.35);
            }

            .tag-allowed {
              color: #bbf7d0;
              background: rgba(20, 83, 45, 0.4);
            }

            .history-actions {
              display: flex;
              align-items: center;
              gap: 8px;
            }

            .empty-state {
              display: grid;
              place-items: center;
              min-height: 150px;
              border: 1px dashed rgba(255, 255, 255, 0.12);
              border-radius: 14px;
              color: #64748b;
              text-align: center;
            }

            .notice {
              position: fixed;
              right: 22px;
              bottom: 22px;
              z-index: 100;
              display: flex;
              align-items: center;
              gap: 18px;
              max-width: 430px;
              padding: 12px 15px;
              border-radius: 12px;
              color: white;
              font-size: 12px;
              box-shadow: 0 15px 40px rgba(0, 0, 0, 0.35);
            }

            .notice.success {
              background: #166534;
            }

            .notice.error {
              background: #991b1b;
            }

            .notice.info {
              background: #14532d;
            }

            .notice button {
              border: 0;
              color: white;
              background: transparent;
              cursor: pointer;
              font-size: 18px;
            }

            @media (max-width: 900px) {
              .stepper {
                overflow-x: auto;
                grid-template-columns: repeat(4, minmax(150px, 1fr));
              }

              .workspace {
                grid-template-columns: 1fr;
              }

              .summary-panel {
                order: -1;
              }

              .two-columns,
              .detail-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
              }
            }

            @media (max-width: 600px) {
              .two-columns,
              .detail-grid {
                grid-template-columns: 1fr;
              }

              .actions {
                align-items: stretch;
                flex-direction: column;
              }

              .actions button {
                width: 100%;
              }
            }
          `}</style>
        </section>
      </main>
    </div>
  );
}

function StepHeader({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <header className="step-heading">
      <span className="heading-number">{number}</span>

      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </header>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      <small>{hint}</small>
    </div>
  );
}

function PrimaryButton({
  loading,
  text,
  loadingText,
}: {
  loading: boolean;
  text: string;
  loadingText: string;
}) {
  return (
    <button
      type="submit"
      className="primary-button"
      disabled={loading}
    >
      {loading ? loadingText : text}
    </button>
  );
}

function SecondaryButton({
  text,
  onClick,
}: {
  text: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="secondary-button"
      onClick={onClick}
    >
      {text}
    </button>
  );
}

function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="summary-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="detail">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`status-badge ${status.toLowerCase()}`}>
      {status}
    </span>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}