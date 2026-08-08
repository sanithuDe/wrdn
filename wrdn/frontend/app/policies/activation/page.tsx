"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import {
  confirmPolicyActivation,
  rejectPolicyActivation,
} from "@/lib/api";

const ACTIVATION_CHANNEL = "wrdn-policy-activation";
const ACTIVATION_STORAGE_KEY =
  "wrdn_policy_activation_result";

type ResultState = {
  tone: "success" | "warning" | "error";
  title: string;
  subtitle: string;
  rows: Array<[string, string]>;
};

function notifyOriginalPolicyPage(payload: {
  status: string;
  policy_id: number;
  client_id: string;
}) {
  const message = {
    ...payload,
    at: Date.now(),
  };

  localStorage.setItem(
    ACTIVATION_STORAGE_KEY,
    JSON.stringify(message),
  );

  try {
    const channel = new BroadcastChannel(ACTIVATION_CHANNEL);
    channel.postMessage(message);
    channel.close();
  } catch {
    // BroadcastChannel may be unavailable in some browsers.
  }
}

function returnToOriginalPolicyPage() {
  // Tell the original Policy Upload tab (page A) to refresh,
  // then close THIS email-confirmation tab.
  try {
    const channel = new BroadcastChannel(ACTIVATION_CHANNEL);
    channel.postMessage({
      type: "FOCUS_POLICY_PAGE",
      at: Date.now(),
    });
    channel.close();
  } catch {
    // ignore
  }

  window.close();
}

function ActivationContent() {
  const searchParams = useSearchParams();
  const [result, setResult] = useState<ResultState | null>(
    null,
  );
  const [busy, setBusy] = useState(true);
  const [closeBlocked, setCloseBlocked] = useState(false);

  useEffect(() => {
    const action = searchParams.get("action");
    const token = searchParams.get("token");

    if (!token || (action !== "confirm" && action !== "reject")) {
      setResult({
        tone: "error",
        title: "Invalid activation link",
        subtitle:
          "This link is missing required details. Go back to your Policy Upload tab and request activation again.",
        rows: [],
      });
      setBusy(false);
      return;
    }

    let cancelled = false;

    async function run() {
      try {
        if (action === "confirm") {
          const data = await confirmPolicyActivation(token!);

          if (cancelled) {
            return;
          }

          notifyOriginalPolicyPage({
            status: "ACTIVE",
            policy_id: data.policy_id,
            client_id: data.client_id,
          });

          setResult({
            tone: "success",
            title: "Policy activated successfully",
            subtitle:
              "Your original Policy Upload tab is updated. Click the button below to close this tab and go back to that page.",
            rows: [
              ["Client", String(data.client_id)],
              ["Policy ID", String(data.policy_id)],
              ["Status", "ACTIVE"],
              [
                "Confirmed at (SL)",
                data.confirmed_at_display || "—",
              ],
              [
                "Activated at (SL)",
                data.activated_at_display || "—",
              ],
            ],
          });
        } else {
          const data = await rejectPolicyActivation(token!);

          if (cancelled) {
            return;
          }

          notifyOriginalPolicyPage({
            status: "VALIDATED",
            policy_id: data.policy_id,
            client_id: data.client_id,
          });

          setResult({
            tone: "warning",
            title: "Activation rejected",
            subtitle:
              "Your original Policy Upload tab is updated. Click the button below to close this tab and go back to that page.",
            rows: [
              ["Client", String(data.client_id)],
              ["Policy ID", String(data.policy_id)],
              ["Status", "VALIDATED (not live)"],
              [
                "Rejected at (SL)",
                data.rejected_at_display || "—",
              ],
            ],
          });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        setResult({
          tone: "error",
          title:
            action === "confirm"
              ? "Activation failed"
              : "Rejection failed",
          subtitle:
            error instanceof Error
              ? error.message
              : "Something went wrong.",
          rows: [],
        });
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    }

    void run();

    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  function handleReturnClick() {
    returnToOriginalPolicyPage();

    // Browsers often block window.close() for tabs opened from email.
    // If this tab is still open, show how to use the old Policy Upload tab.
    window.setTimeout(() => {
      if (!window.closed) {
        setCloseBlocked(true);
      }
    }, 250);
  }

  const accent =
    result?.tone === "success"
      ? "#20e487"
      : result?.tone === "warning"
        ? "#fbbf24"
        : "#ff6f86";

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
        background:
          "radial-gradient(circle at top left, rgba(32,228,135,0.12), transparent 36%), #05070c",
        color: "#f5f7fb",
        fontFamily: "Arial, Helvetica, sans-serif",
      }}
    >
      <section
        style={{
          width: "min(480px, 100%)",
          padding: "32px 28px",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 22,
          background: "rgba(12,15,22,0.92)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.45)",
          textAlign: "center",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 22,
            color: "#9aa4b2",
            fontSize: 13,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              display: "grid",
              placeItems: "center",
              borderRadius: 11,
              color: "#05070c",
              background: "#20e487",
              fontWeight: 900,
            }}
          >
            W
          </div>
          WRDN Security
        </div>

        {busy || !result ? (
          <>
            <h1 style={{ margin: "0 0 10px", fontSize: 22 }}>
              Processing…
            </h1>
            <p style={{ color: "#8d96a5", fontSize: 14 }}>
              Please wait while WRDN finishes this request.
            </p>
          </>
        ) : (
          <>
            <div
              style={{
                width: 64,
                height: 64,
                margin: "0 auto 18px",
                display: "grid",
                placeItems: "center",
                borderRadius: "50%",
                color: accent,
                background: `${accent}22`,
                border: `1px solid ${accent}59`,
                fontSize: 28,
                fontWeight: 900,
              }}
            >
              {result.tone === "success"
                ? "✓"
                : result.tone === "warning"
                  ? "!"
                  : "×"}
            </div>

            <h1
              style={{
                margin: "0 0 10px",
                fontSize: 24,
                fontWeight: 800,
              }}
            >
              {result.title}
            </h1>

            <p
              style={{
                margin: "0 0 22px",
                color: "#8d96a5",
                fontSize: 14,
                lineHeight: 1.55,
              }}
            >
              {result.subtitle}
            </p>

            {result.rows.length > 0 && (
              <div
                style={{
                  display: "grid",
                  gap: 10,
                  margin: "0 0 24px",
                  padding: 14,
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.03)",
                  textAlign: "left",
                }}
              >
                {result.rows.map(([label, value]) => (
                  <div
                    key={label}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 16,
                      fontSize: 13,
                    }}
                  >
                    <span style={{ color: "#7d8590" }}>
                      {label}
                    </span>
                    <strong style={{ color: "#e8edf5" }}>
                      {value}
                    </strong>
                  </div>
                ))}
              </div>
            )}

            {result.tone !== "error" && (
              <button
                type="button"
                onClick={handleReturnClick}
                style={{
                  width: "100%",
                  padding: "13px 18px",
                  border: "none",
                  borderRadius: 12,
                  color: "#05070c",
                  background: "#20e487",
                  fontSize: 14,
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                Close and go back to Policy Upload
              </button>
            )}

            {closeBlocked && (
              <p
                style={{
                  margin: "14px 0 0",
                  padding: 12,
                  borderRadius: 12,
                  border: "1px solid rgba(251,191,36,0.35)",
                  background: "rgba(146,64,14,0.25)",
                  color: "#fde68a",
                  fontSize: 13,
                  lineHeight: 1.45,
                }}
              >
                Browser blocked closing this tab. Switch to your
                old Policy Upload tab (the one where you clicked
                Request Activation). It already has the new
                status. Then close this tab manually.
              </p>
            )}

            <p
              style={{
                margin: "18px 0 0",
                color: "#565e69",
                fontSize: 11,
              }}
            >
              Does not open a new WRDN page · Sri Lanka time
              (UTC+5:30)
            </p>
          </>
        )}
      </section>
    </main>
  );
}

export default function PolicyActivationPage() {
  return (
    <Suspense
      fallback={
        <main
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            background: "#05070c",
            color: "#fff",
          }}
        >
          Loading…
        </main>
      }
    >
      <ActivationContent />
    </Suspense>
  );
}
