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
  submitRequirementChecklist,
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
    description: "Allow / block checklist",
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

const POLICY_SECTORS: Array<{
  id: string;
  label: string;
  hint: string;
}> = [
  {
    id: "credentials",
    label: "Credentials & secrets",
    hint: "Passwords, API keys, tokens, private keys",
  },
  {
    id: "financial_records",
    label: "Financial records",
    hint: "Salaries, bank details, invoices, budgets",
  },
  {
    id: "employee_information",
    label: "Employee information",
    hint: "HR records, roles, contact details, payroll",
  },
  {
    id: "personal_information",
    label: "Personal data (PII)",
    hint: "NIC, phone, address, private identity data",
  },
  {
    id: "customer_information",
    label: "Customer information",
    hint: "Client lists, contracts, customer secrets",
  },
  {
    id: "internal_documents",
    label: "Internal documents",
    hint: "Policies, memos, confidential files",
  },
  {
    id: "source_code",
    label: "Source code & IP",
    hint: "Repos, repos, proprietary algorithms",
  },
  {
    id: "malware",
    label: "Malware / exploit content",
    hint: "Attack code, payloads, weaponized files",
  },
  {
    id: "violence",
    label: "Violence & harm",
    hint: "Violent or dangerous instructions",
  },
  {
    id: "illegal_activity",
    label: "Illegal activity",
    hint: "Fraud, crime, prohibited assistance",
  },
];

const SENSITIVE_PATTERN_OPTIONS: Array<{
  id: string;
  label: string;
}> = [
  { id: "api_key", label: "API key" },
  { id: "password", label: "Password" },
  { id: "access_token", label: "Access / bearer token" },
  { id: "private_key", label: "Private key" },
  { id: "email_address", label: "Email address" },
  { id: "phone_number", label: "Phone number" },
  { id: "sri_lankan_nic", label: "Sri Lankan NIC" },
  { id: "bank_account", label: "Bank account" },
];

function buildChecklistRequirementText(
  allowed: string[],
  blocked: string[],
  patterns: string[],
  extraInfo: string,
): string {
  const labelFor = (id: string) =>
    POLICY_SECTORS.find((sector) => sector.id === id)?.label
    || id;

  const blockedLines = blocked.length
    ? blocked
        .map((id) => `- ${id} — ${labelFor(id)}`)
        .join("\n")
    : "- (none)";

  const allowedLines = allowed.length
    ? allowed
        .map((id) => `- ${id} — ${labelFor(id)}`)
        .join("\n")
    : "- (none)";

  const patternLines = patterns.length
    ? patterns.map((id) => `- ${id}`).join("\n")
    : "- (none)";

  const extra = extraInfo.trim() || "(none provided)";

  return `
WRDN Client Security Requirements
Source: Admin allow/block checklist (no file upload)

IMPORTANT FOR POLICY JSON (must match Policy History card):
1. Put EVERY blocked sector id below into blocked_categories exactly
   (same ids shown as red tags: e.g. financial_records, malware).
2. Do NOT put allowed sector ids into blocked_categories.
3. Put selected sensitive pattern ids into sensitive_pattern_ids
   (same ids shown as orange tags on Policy History).
   If the list is (none), leave sensitive_pattern_ids as [].
   Do not invent extra patterns.
4. Fill allowed_secret_names / blocked_secret_names /
   allowed_employee_salary_names / blocked_employee_salary_names
   only when EXTRA INFORMATION names them.
5. Keep allowed_actions as ["ALLOW", "REDACT", "BLOCK"].
6. Write a clear blocked_response for end users.

BLOCKED CATEGORIES (exact ids for blocked_categories):
${blockedLines}

ALLOWED CATEGORIES (must NOT appear in blocked_categories):
${allowedLines}

SENSITIVE PATTERNS (exact ids for sensitive_pattern_ids):
${patternLines}

EXTRA INFORMATION FROM ADMIN
${extra}
`.trim();
}

export default function PoliciesPage() {
  const router = useRouter();

  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  const [activeStep, setActiveStep] = useState<Step>(1);
  const [completedStep, setCompletedStep] = useState(0);

  const [clientId, setClientId] = useState("");

  const [allowedSectors, setAllowedSectors] = useState<
    string[]
  >([]);
  const [blockedSectors, setBlockedSectors] = useState<
    string[]
  >([
    "credentials",
    "financial_records",
    "employee_information",
    "personal_information",
    "malware",
    "illegal_activity",
  ]);
  const [selectedPatterns, setSelectedPatterns] = useState<
    string[]
  >([
    "api_key",
    "password",
    "access_token",
    "private_key",
    "bank_account",
  ]);
  const [extraRequirementInfo, setExtraRequirementInfo] =
    useState("");

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
    router.push("/signin");
  }

  useEffect(() => {
    const currentUser = getAuthUser();
  
    if (!currentUser) {
      router.push("/signin");
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

  useEffect(() => {
    function applyActivationResult(
      payload?: {
        status?: string;
        policy_id?: number;
      } | null,
    ) {
      let data = payload;

      if (!data) {
        const raw = localStorage.getItem(
          "wrdn_policy_activation_result",
        );

        if (!raw) {
          return;
        }

        try {
          data = JSON.parse(raw) as {
            status?: string;
            policy_id?: number;
          };
        } catch {
          localStorage.removeItem(
            "wrdn_policy_activation_result",
          );
          return;
        }
      }

      localStorage.removeItem(
        "wrdn_policy_activation_result",
      );

      setGeneratedPolicy((current) =>
        current &&
        data?.policy_id &&
        current.policy_id === data.policy_id
          ? {
              ...current,
              status: data.status || current.status,
            }
          : current,
      );

      setNotice({
        type:
          data?.status === "ACTIVE"
            ? "success"
            : data?.status === "REJECTED"
              ? "error"
              : "info",
        message:
          data?.status === "ACTIVE"
            ? "Policy activated from email confirmation."
            : data?.status === "REJECTED"
              ? "Policy activation was rejected. Status is now REJECTED."
              : "Activation was rejected from email.",
      });

      if (clientId.trim()) {
        void listPolicies(clientId.trim()).then(
          (result) => {
            setPolicyHistory(result);
            setActiveStep(4);
            setCompletedStep(4);
          },
        );
      }
    }

    applyActivationResult();

    function onStorage(event: StorageEvent) {
      if (event.key === "wrdn_policy_activation_result") {
        applyActivationResult();
      }
    }

    let channel: BroadcastChannel | null = null;

    try {
      channel = new BroadcastChannel(
        "wrdn-policy-activation",
      );
      channel.onmessage = (event) => {
        const message = event.data as {
          type?: string;
          status?: string;
          policy_id?: number;
        };

        if (message?.type === "FOCUS_POLICY_PAGE") {
          window.focus();
          return;
        }

        if (message?.status && message?.policy_id) {
          applyActivationResult(message);
          window.focus();
        }
      };
    } catch {
      channel = null;
    }

    window.addEventListener("storage", onStorage);

    function onFocus() {
      applyActivationResult();
    }

    window.addEventListener("focus", onFocus);

    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", onFocus);
      channel?.close();
    };
  }, [clientId]);

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

  function toggleSector(
    sectorId: string,
    column: "allowed" | "blocked",
  ) {
    if (column === "allowed") {
      setAllowedSectors((current) => {
        if (current.includes(sectorId)) {
          return current.filter((id) => id !== sectorId);
        }
        return [...current, sectorId];
      });
      setBlockedSectors((current) =>
        current.filter((id) => id !== sectorId),
      );
      return;
    }

    setBlockedSectors((current) => {
      if (current.includes(sectorId)) {
        return current.filter((id) => id !== sectorId);
      }
      return [...current, sectorId];
    });
    setAllowedSectors((current) =>
      current.filter((id) => id !== sectorId),
    );
  }

  function togglePattern(patternId: string) {
    setSelectedPatterns((current) => {
      if (current.includes(patternId)) {
        return current.filter((id) => id !== patternId);
      }
      return [...current, patternId];
    });
  }

  async function handleChecklistSubmit(
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

    if (
      allowedSectors.length === 0
      && blockedSectors.length === 0
      && selectedPatterns.length === 0
      && !extraRequirementInfo.trim()
    ) {
      setNotice({
        type: "error",
        message:
          "Select at least one sector or sensitive pattern, or add extra information.",
      });
      return;
    }

    setBusyAction("upload");
    setNotice(null);

    try {
      const requirementText = buildChecklistRequirementText(
        allowedSectors,
        blockedSectors,
        selectedPatterns,
        extraRequirementInfo,
      );

      const result = await submitRequirementChecklist(
        clientId.trim(),
        requirementText,
      );

      setRequirementId(String(result.requirement_id));
      setFilePreview(result.text_preview);

      setNotice({
        type: "success",
        message:
          "Checklist requirements saved. Continue to generate the policy.",
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
        message:
          result.message ||
          "Confirmation email sent. Check your admin inbox and confirm to activate.",
      });

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

          if (section === "hr") {
            router.push("/hr");
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
                        title="Select security requirements"
                        description="Tick Allowed for topics chat may answer. Tick Blocked to refuse those topics. Unchecked sensitive patterns stay unused — they will not be added automatically."
                      />

                      <form
                        onSubmit={handleChecklistSubmit}
                        className="form"
                      >
                        <div className="sector-table">
                          <div className="sector-table-head">
                            <span>Sector</span>
                            <span>Allowed</span>
                            <span>Blocked</span>
                          </div>

                          {POLICY_SECTORS.map((sector) => {
                            const isAllowed =
                              allowedSectors.includes(sector.id);
                            const isBlocked =
                              blockedSectors.includes(sector.id);

                            return (
                              <div
                                key={sector.id}
                                className="sector-row"
                              >
                                <div>
                                  <strong>{sector.label}</strong>
                                  <small>{sector.hint}</small>
                                </div>

                                <label className="sector-check">
                                  <input
                                    type="checkbox"
                                    checked={isAllowed}
                                    onChange={() =>
                                      toggleSector(
                                        sector.id,
                                        "allowed",
                                      )
                                    }
                                  />
                                  <span>Allow</span>
                                </label>

                                <label className="sector-check">
                                  <input
                                    type="checkbox"
                                    checked={isBlocked}
                                    onChange={() =>
                                      toggleSector(
                                        sector.id,
                                        "blocked",
                                      )
                                    }
                                  />
                                  <span>Block</span>
                                </label>
                              </div>
                            );
                          })}
                        </div>

                        <div className="pattern-block">
                          <div className="pattern-block-head">
                            <strong>Sensitive patterns</strong>
                            <small>
                              These become the orange tags on Policy
                              History (sensitive_pattern_ids).
                            </small>
                          </div>
                          <div className="pattern-grid">
                            {SENSITIVE_PATTERN_OPTIONS.map(
                              (pattern) => {
                                const checked =
                                  selectedPatterns.includes(
                                    pattern.id,
                                  );
                                return (
                                  <label
                                    key={pattern.id}
                                    className="pattern-check"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() =>
                                        togglePattern(pattern.id)
                                      }
                                    />
                                    <span>{pattern.label}</span>
                                  </label>
                                );
                              },
                            )}
                          </div>
                        </div>

                        <Field
                          label="Extra information"
                          hint="Optional notes (company name, extra rules). These are stored with the requirement."
                        >
                          <textarea
                            rows={5}
                            value={extraRequirementInfo}
                            onChange={(event) =>
                              setExtraRequirementInfo(
                                event.target.value,
                              )
                            }
                            placeholder="Example: Block all employee salaries except directory name/role questions. Keep customer support answers helpful."
                          />
                        </Field>

                        {filePreview ? (
                          <div className="preview">
                            <strong>Saved checklist preview</strong>
                            <pre>{filePreview}</pre>
                          </div>
                        ) : null}

                        <div className="actions">
                          <PrimaryButton
                            loading={busyAction === "upload"}
                            text="Save checklist"
                            loadingText="Saving..."
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
                        description="Analyze the checklist requirements and create a draft policy."
                      />

                      <form
                        onSubmit={handleGenerate}
                        className="form"
                      >
                        <Field
                          label="Requirement ID"
                          hint="Automatically added after you save the checklist."
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
                        description="Validate the policy, then request email confirmation before it goes live."
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

                          {generatedPolicy.status ===
                            "PENDING_ACTIVATION" && (
                            <div className="pending-activation-box">
                              Waiting for email confirmation.
                              Check the admin inbox (and Spam),
                              then click Confirm Activation.
                              The policy is not live yet.
                            </div>
                          )}

                          {generatedPolicy.status ===
                            "REJECTED" && (
                            <div className="rejected-activation-box">
                              Activation was rejected. This
                              policy is marked REJECTED and is
                              not live. You can request
                              activation again.
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
                                (generatedPolicy.status !==
                                  "VALIDATED" &&
                                  generatedPolicy.status !==
                                    "REJECTED" &&
                                  generatedPolicy.status !==
                                    "PENDING_ACTIVATION") ||
                                busyAction === "activate"
                              }
                            >
                              {busyAction === "activate"
                                ? "Sending email..."
                                : generatedPolicy.status ===
                                    "PENDING_ACTIVATION"
                                  ? "Resend Confirmation Email"
                                  : generatedPolicy.status ===
                                      "REJECTED"
                                    ? "Request Activation Again"
                                    : "Request Activation"}
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
                        description="Each version shows what chat may discuss (allowed) and what WRDN blocks, plus activation status."
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
                            const blockedSet = new Set(
                              blocked.map((item) =>
                                String(item).trim().toLowerCase(),
                              ),
                            );
                            const allowedSectors =
                              POLICY_SECTORS.filter(
                                (sector) =>
                                  !blockedSet.has(sector.id),
                              );
                            const blockedSectors =
                              POLICY_SECTORS.filter((sector) =>
                                blockedSet.has(sector.id),
                              );

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

                                    <p className="history-timestamps">
                                      Created:{" "}
                                      {formatPolicyDateTime(
                                        policy.CreatedAt,
                                      )}
                                      {" · "}
                                      Activated:{" "}
                                      {formatPolicyDateTime(
                                        policy.ActivatedAt,
                                      )}
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
                                    <span>Allowed categories</span>
                                    <div className="tag-row">
                                      {allowedSectors.length > 0 ? (
                                        allowedSectors.map((sector) => (
                                          <em
                                            key={`${policy.PolicyID}-a-${sector.id}`}
                                            className="tag tag-allowed"
                                          >
                                            {sector.label}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None</small>
                                      )}
                                    </div>
                                  </div>

                                  <div className="history-detail-block">
                                    <span>Blocked categories</span>
                                    <div className="tag-row">
                                      {blockedSectors.length > 0 ? (
                                        blockedSectors.map((sector) => (
                                          <em
                                            key={`${policy.PolicyID}-b-${sector.id}`}
                                            className="tag tag-blocked"
                                          >
                                            {sector.label}
                                          </em>
                                        ))
                                      ) : (
                                        <small>None</small>
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
                      : "Not saved"
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
                    <strong>Email confirmation required</strong>
                    <p>
                      Policies go live only after the admin
                      confirms from the email link.
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

            .field input,
            .field textarea {
              width: 100%;
              padding: 12px 13px;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 12px;
              outline: none;
              color: #f8fafc;
              background: #05070c;
              font: inherit;
              resize: vertical;
            }

            .field input:focus,
            .field textarea:focus {
              border-color: #20e487;
              box-shadow: 0 0 0 3px rgba(32, 228, 135, 0.12);
            }

            .field small {
              display: block;
              margin-top: 6px;
              color: #64748b;
              font-size: 11px;
            }

            .sector-table {
              display: grid;
              gap: 8px;
            }

            .sector-table-head,
            .sector-row {
              display: grid;
              grid-template-columns: minmax(0, 1fr) 88px 88px;
              gap: 10px;
              align-items: center;
            }

            .sector-table-head {
              padding: 0 4px 6px;
              color: #64748b;
              font-size: 11px;
              text-transform: uppercase;
              letter-spacing: 0.04em;
            }

            .sector-row {
              padding: 12px 12px;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 12px;
              background: rgba(255, 255, 255, 0.02);
            }

            .sector-row strong {
              display: block;
              color: #e2e8f0;
              font-size: 13px;
            }

            .sector-row small {
              display: block;
              margin-top: 4px;
              color: #64748b;
              font-size: 11px;
              line-height: 1.4;
            }

            .sector-check {
              display: flex;
              align-items: center;
              justify-content: center;
              gap: 6px;
              color: #94a3b8;
              font-size: 12px;
              cursor: pointer;
            }

            .sector-check input {
              width: 16px;
              height: 16px;
              accent-color: #20e487;
            }

            .pattern-block {
              padding: 14px;
              border: 1px solid rgba(255, 255, 255, 0.08);
              border-radius: 12px;
              background: rgba(255, 255, 255, 0.02);
            }

            .pattern-block-head {
              margin-bottom: 12px;
            }

            .pattern-block-head strong {
              display: block;
              color: #e2e8f0;
              font-size: 13px;
            }

            .pattern-block-head small {
              display: block;
              margin-top: 4px;
              color: #64748b;
              font-size: 11px;
              line-height: 1.4;
            }

            .pattern-grid {
              display: grid;
              grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: 8px 12px;
            }

            .pattern-check {
              display: flex;
              align-items: center;
              gap: 8px;
              color: #94a3b8;
              font-size: 12px;
              cursor: pointer;
            }

            .pattern-check input {
              width: 16px;
              height: 16px;
              accent-color: #f59e0b;
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

            .status-badge.pending_activation {
              color: #fde68a;
              background: #92400e;
            }

            .pending-activation-box {
              margin: 12px 0;
              padding: 12px 14px;
              border: 1px solid rgba(251, 191, 36, 0.35);
              border-radius: 12px;
              color: #fde68a;
              background: rgba(146, 64, 14, 0.25);
              font-size: 13px;
              line-height: 1.45;
            }

            .status-badge.inactive {
              color: #ddd6fe;
              background: #4c1d95;
            }

            .status-badge.rejected {
              color: #fecaca;
              background: #7f1d1d;
              border: 1px solid rgba(248, 113, 113, 0.45);
            }

            .rejected-activation-box {
              margin: 12px 0;
              padding: 12px 14px;
              border: 1px solid rgba(248, 113, 113, 0.4);
              border-radius: 12px;
              color: #fecaca;
              background: rgba(127, 29, 29, 0.35);
              font-size: 13px;
              line-height: 1.45;
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

            .history-timestamps {
              margin-top: 6px !important;
              color: #94a3b8 !important;
              font-size: 11px !important;
              line-height: 1.45;
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

              .sector-table-head,
              .sector-row {
                grid-template-columns: minmax(0, 1fr) 72px 72px;
              }

              .pattern-grid {
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
  const normalized = (status || "UNKNOWN").toUpperCase();
  const className = normalized.toLowerCase();

  return (
    <span className={`status-badge ${className}`}>
      {normalized}
    </span>
  );
}

function formatPolicyDateTime(
  value?: string | null,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(
    value.includes("T") || value.endsWith("Z")
      ? value
      : `${value.replace(" ", "T")}Z`,
  );

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-LK", {
    timeZone: "Asia/Colombo",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}