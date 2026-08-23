"use client";

import type { HrHistoryItem } from "@/lib/api";

type HrHistoryPanelProps = {
  history: HrHistoryItem[];
  historyBusy: boolean;
  historyError: string;
  expandedHistoryId: number | null;
  onRefresh: () => void;
  onToggleExpand: (id: number | null) => void;
};

function statusColor(status: string): string {
  if (status === "BLOCKED") {
    return "#ff8f8f";
  }
  if (status === "BYPASSED") {
    return "#ffd27a";
  }
  if (status === "ALLOWED") {
    return "#7dffb2";
  }
  return "#e8edf5";
}

export default function HrHistoryPanel({
  history,
  historyBusy,
  historyError,
  expandedHistoryId,
  onRefresh,
  onToggleExpand,
}: HrHistoryPanelProps) {
  const subtitle = historyBusy
    ? "Loading recent HR runs…"
    : historyError
      ? historyError
      : history.length === 0
        ? "No HR runs yet for this client. Process a CV to build history."
        : `${history.length} recent run(s) for this client — inbound blocks and outbound shield decisions.`;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: 14,
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 16,
        background: "rgba(255,255,255,0.03)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <h2
            style={{
              margin: "0 0 4px",
              fontSize: 16,
              color: "#e8edf5",
            }}
          >
            Processing history
          </h2>
          <p
            style={{
              margin: 0,
              color: "#7d8694",
              fontSize: 12,
            }}
          >
            {subtitle}
          </p>
        </div>
        <button
          type="button"
          disabled={historyBusy}
          onClick={onRefresh}
          style={{
            flexShrink: 0,
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: 10,
            background: "rgba(255,255,255,0.04)",
            color: "#e8edf5",
            padding: "8px 12px",
            fontSize: 12,
            cursor: historyBusy ? "wait" : "pointer",
          }}
        >
          {historyBusy ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {historyBusy && history.length === 0 ? (
        <p style={{ margin: 0, color: "#9aa3b2", fontSize: 13 }}>
          Fetching history…
        </p>
      ) : null}

      {!historyBusy && history.length === 0 ? (
        <p style={{ margin: 0, color: "#9aa3b2", fontSize: 13 }}>
          {historyError
            ? "Could not load history. Click Refresh to try again."
            : "No HR runs yet. Process a CV to start building history."}
        </p>
      ) : null}

      {history.length > 0 ? (
        <div
          style={{
            maxHeight: 420,
            overflow: "auto",
            borderRadius: 12,
            border: "1px solid rgba(255,255,255,0.1)",
            background: "#0b0e14",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              color: "#e8edf5",
              fontSize: 13,
            }}
          >
            <thead>
              <tr
                style={{
                  textAlign: "left",
                  color: "#9aa3b2",
                  fontSize: 11,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                  background: "#10141c",
                }}
              >
                <th style={{ padding: "10px 12px" }}>When</th>
                <th style={{ padding: "10px 12px" }}>Role / stage</th>
                <th style={{ padding: "10px 12px" }}>Status</th>
                <th style={{ padding: "10px 12px" }}>Risk</th>
                <th style={{ padding: "10px 12px" }}>Candidate</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => {
                const status = (
                  item.shield_status || "UNKNOWN"
                ).toUpperCase();
                const open = expandedHistoryId === item.id;
                const color = statusColor(status);

                return (
                  <tr
                    key={item.id}
                    onClick={() =>
                      onToggleExpand(open ? null : item.id)
                    }
                    style={{
                      cursor: "pointer",
                      borderTop: "1px solid rgba(255,255,255,0.08)",
                      background: open
                        ? "rgba(32,228,135,0.06)"
                        : "transparent",
                    }}
                  >
                    <td
                      style={{
                        padding: 12,
                        color: "#c5ccd6",
                        whiteSpace: "nowrap",
                        verticalAlign: "top",
                      }}
                    >
                      <div>{item.timestamp || "—"}</div>
                      {item.username ? (
                        <div style={{ color: "#9aa3b2", fontSize: 12 }}>
                          {item.username}
                        </div>
                      ) : null}
                      {open ? (
                        <div
                          style={{
                            marginTop: 10,
                            maxWidth: 520,
                            color: "#d5dbe5",
                            fontSize: 12,
                            lineHeight: 1.45,
                            whiteSpace: "normal",
                          }}
                        >
                          <div style={{ color: "#7d8694", marginBottom: 2 }}>
                            LAYER
                          </div>
                          <div>{item.detection_layer || "—"}</div>
                          <div
                            style={{
                              color: "#7d8694",
                              margin: "8px 0 2px",
                            }}
                          >
                            SUBJECT
                          </div>
                          <div>{item.subject || "—"}</div>
                          <div
                            style={{
                              color: "#7d8694",
                              margin: "8px 0 2px",
                            }}
                          >
                            REASON
                          </div>
                          <div>{item.detection_reason || "—"}</div>
                        </div>
                      ) : null}
                    </td>
                    <td
                      style={{
                        padding: 12,
                        color: "#f3f6fb",
                        fontWeight: 600,
                        verticalAlign: "top",
                      }}
                    >
                      {item.target_role || "Candidate run"}
                      <span style={{ color: "#9aa3b2", fontWeight: 400 }}>
                        {item.stage === "inbound"
                          ? " · inbound"
                          : " · outbound"}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: 12,
                        color,
                        fontWeight: 700,
                        letterSpacing: "0.04em",
                        verticalAlign: "top",
                      }}
                    >
                      {status}
                    </td>
                    <td
                      style={{
                        padding: 12,
                        color: "#9aa3b2",
                        verticalAlign: "top",
                      }}
                    >
                      {item.risk_score}
                    </td>
                    <td
                      style={{
                        padding: 12,
                        color: "#c5ccd6",
                        maxWidth: 220,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        verticalAlign: "top",
                      }}
                    >
                      {item.candidate_email || item.filename || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
