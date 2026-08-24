"use client";

import {
    useRegistryData,
    type RegistryLog,
} from "@/hooks/useRegistryData";
import { useEffect, useMemo, useState } from "react";

import {
    Area,
    AreaChart,
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

type TimeFilter = "1h" | "24h" | "7d" | "all";

const TIME_FILTERS: TimeFilter[] = ["1h", "24h", "7d", "all"];

/** Survives section navigation; resets to "all" on full page refresh. */
let persistedTimeFilter: TimeFilter = "all";

function isTimeFilter(value: string): value is TimeFilter {
  return TIME_FILTERS.includes(value as TimeFilter);
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

function parseRegistryTime(
  timestamp: string,
): Date | null {
  if (!timestamp) {
    return null;
  }

  // SQLite CURRENT_TIMESTAMP is stored in UTC.
  const normalized = timestamp.includes("T")
    ? timestamp
    : timestamp.replace(" ", "T");

  const utcTimestamp =
    normalized.endsWith("Z")
      ? normalized
      : `${normalized}Z`;

  const date = new Date(utcTimestamp);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date;
}

function formatDateTime(timestamp: string): string {
  const date = parseRegistryTime(timestamp);

  if (!date) {
    return timestamp || "Unknown";
  }

  return date.toLocaleString();
}

function getTimeWindowMs(filter: TimeFilter): number | null {
  if (filter === "1h") {
    return 60 * 60 * 1000;
  }

  if (filter === "24h") {
    return 24 * 60 * 60 * 1000;
  }

  if (filter === "7d") {
    return 7 * 24 * 60 * 60 * 1000;
  }

  return null;
}

function getBucketKey(date: Date, filter: TimeFilter): string {
  if (filter === "1h") {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (filter === "24h") {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

export default function RegistryDashboard({
  isAdmin = false,
  clientId = "clientA",
  username = "",
}: {
  isAdmin?: boolean;
  clientId?: string;
  username?: string;
}) {
  const {
    registryData,
    loading,
    error,
    lastUpdated,
    refresh,
  } = useRegistryData();

  const [timeFilter, setTimeFilter] = useState<TimeFilter>(
    persistedTimeFilter,
  );
  const [protectionEnabled, setProtectionEnabled] =
    useState(true);
  const [protectionBusy, setProtectionBusy] =
    useState(false);
  const [protectionMessage, setProtectionMessage] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    void fetch(
      `${API_URL}/api/protection-status?client_id=${encodeURIComponent(
        clientId,
      )}`,
    )
      .then(async (response) => {
        const data = await response.json();
        if (!cancelled && response.ok) {
          setProtectionEnabled(
            Boolean(data.protection_enabled),
          );
          setProtectionMessage(
            String(data.message || ""),
          );
        }
      })
      .catch(() => {
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  async function toggleProtection() {
    if (!isAdmin || protectionBusy) {
      return;
    }

    setProtectionBusy(true);
    setProtectionMessage("");

    try {
      const response = await fetch(
        `${API_URL}/api/admin/protection-status`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            client_id: clientId,
            enabled: !protectionEnabled,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Could not update protection status.",
        );
      }

      setProtectionEnabled(
        Boolean(data.protection_enabled),
      );
      setProtectionMessage(
        String(data.message || ""),
      );
    } catch (toggleError) {
      setProtectionMessage(
        toggleError instanceof Error
          ? toggleError.message
          : "Could not update protection status.",
      );
    } finally {
      setProtectionBusy(false);
    }
  }

  function handleTimeFilterChange(value: string) {
    if (!isTimeFilter(value)) {
      return;
    }

    persistedTimeFilter = value;
    setTimeFilter(value);
  }

  function scrollToSection(sectionId: string) {
    document.getElementById(sectionId)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  const calculatedData = useMemo(() => {
    const allowedLogs = registryData?.allowed_logs ?? [];
    const blockedLogs = registryData?.blocked_logs ?? [];

    const allLogs = [
      ...allowedLogs.map((log: RegistryLog) => ({
        ...log,
        logType: "allowed" as const,
        parsedDate: parseRegistryTime(log.timestamp),
      })),

      ...blockedLogs.map((log: RegistryLog) => ({
        ...log,
        logType: "blocked" as const,
        parsedDate: parseRegistryTime(log.timestamp),
      })),
    ]
      .filter((log) => log.parsedDate !== null)
      .sort(
        (first, second) =>
          second.parsedDate!.getTime() -
          first.parsedDate!.getTime(),
      );

    if (allLogs.length === 0) {
      return {
        filteredAllowed: [],
        filteredBlocked: [],
        activityChartData: [],
        riskChartData: [],
        highestRiskScore: 0,
        averageRiskScore: 0,
        totalEvents: 0,
        blockRate: 0,
        criticalCount: 0,
        topReasons: [] as { reason: string; count: number }[],
        latestBlocked: [] as typeof allLogs,
      };
    }

    const windowMs = getTimeWindowMs(timeFilter);
    const currentTime = Date.now();

    const filteredLogs =
      windowMs === null
        ? allLogs
        : allLogs.filter((log) => {
            const logTime = log.parsedDate!.getTime();

            return currentTime - logTime <= windowMs;
          });

    const filteredAllowed = filteredLogs.filter(
      (log) => log.logType === "allowed",
    );

    const filteredBlocked = filteredLogs.filter(
      (log) => log.logType === "blocked",
    );

    const bucketMap = new Map<
      string,
      {
        time: string;
        allowed: number;
        blocked: number;
        totalRisk: number;
        highestRisk: number;
        totalLogs: number;
      }
    >();

    filteredLogs.forEach((log) => {
      const bucket = getBucketKey(
        log.parsedDate!,
        timeFilter,
      );

      if (!bucketMap.has(bucket)) {
        bucketMap.set(bucket, {
          time: bucket,
          allowed: 0,
          blocked: 0,
          totalRisk: 0,
          highestRisk: 0,
          totalLogs: 0,
        });
      }

      const bucketRecord = bucketMap.get(bucket)!;
      const riskScore = Number(log.risk_score || 0);

      bucketRecord.totalLogs += 1;
      bucketRecord.totalRisk += riskScore;
      bucketRecord.highestRisk = Math.max(
        bucketRecord.highestRisk,
        riskScore,
      );

      if (log.logType === "allowed") {
        bucketRecord.allowed += 1;
      }

      if (log.logType === "blocked") {
        bucketRecord.blocked += 1;
      }
    });

    const bucketValues = Array.from(bucketMap.values());

    const activityChartData = bucketValues.map((bucket) => ({
      time: bucket.time,
      allowed: bucket.allowed,
      blocked: bucket.blocked,
    }));

    const riskChartData = bucketValues.map((bucket) => ({
      time: bucket.time,
      highestRisk: bucket.highestRisk,
      averageRisk:
        bucket.totalLogs > 0
          ? Math.round(bucket.totalRisk / bucket.totalLogs)
          : 0,
    }));

    const riskScores = filteredLogs.map((log) =>
      Number(log.risk_score || 0),
    );

    const highestRiskScore =
      riskScores.length > 0 ? Math.max(...riskScores) : 0;

    const averageRiskScore =
      riskScores.length > 0
        ? Math.round(
            riskScores.reduce(
              (total, score) => total + score,
              0,
            ) / riskScores.length,
          )
        : 0;

    const totalEvents = filteredLogs.length;
    const blockRate =
      totalEvents > 0
        ? Math.round((filteredBlocked.length / totalEvents) * 100)
        : 0;
    const criticalCount = filteredLogs.filter(
      (log) => Number(log.risk_score || 0) >= 90,
    ).length;

    const reasonCounts = new Map<string, number>();
    filteredBlocked.forEach((log) => {
      const reason = String(log.detection_reason || "")
        .replace(/\s+/g, " ")
        .trim();
      const lower = reason.toLowerCase();

      if (
        !reason ||
        lower.includes("no high semantic") ||
        lower.includes("passed all")
      ) {
        return;
      }

      reasonCounts.set(reason, (reasonCounts.get(reason) || 0) + 1);
    });

    const topReasons = Array.from(reasonCounts.entries())
      .map(([reason, count]) => ({ reason, count }))
      .sort((first, second) => second.count - first.count)
      .slice(0, 3);

    return {
      filteredAllowed,
      filteredBlocked,
      activityChartData,
      riskChartData,
      highestRiskScore,
      averageRiskScore,
      totalEvents,
      blockRate,
      criticalCount,
      topReasons,
      latestBlocked: filteredBlocked.slice(0, 3),
    };
  }, [registryData, timeFilter]);

  if (loading) {
    return (
      <div className="loading-box">
        Loading local WRDN registry...
      </div>
    );
  }

  if (error || !registryData) {
    return (
      <div className="error-box">
        <h2>Registry Connection Failed</h2>

        <p>
          {error ||
            "The backend did not return registry data."}
        </p>

        <button type="button" onClick={refresh}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="dashboard-content-page">
      {/* <div className="dashboard-section-navigation">
        <button
          type="button"
          onClick={() => scrollToSection("overview-section")}
        >
          Overview
        </button>

        <button
          type="button"
          onClick={() => scrollToSection("charts-section")}
        >
          Graphs
        </button>

        <button
          type="button"
          onClick={() => scrollToSection("allowed-section")}
        >
          Allowed Logs
        </button>

        <button
          type="button"
          onClick={() => scrollToSection("blocked-section")}
        >
          Blocked Logs
        </button>

        <button
          type="button"
          onClick={() => scrollToSection("risk-section")}
        >
          Risk Analysis
        </button>

        <button
          type="button"
          onClick={() => scrollToSection("settings-section")}
        >
          Settings
        </button>
      </div> */}

      <main
        className="main-content"
        id="live-registry-section"
      >
        <header className="topbar">
          <div>
            <h1>Live Governance Registry</h1>

            <p>
              {isAdmin
                ? `Admin scope: all chat/shield activity for client ${clientId}${
                    username ? ` (signed in as ${username})` : ""
                  }.`
                : `Employee scope: only your own shield activity${
                    username ? ` (${username})` : ""
                  } on client ${clientId}.`}
            </p>
          </div>

          <div className="topbar-right">
            <span className="live-status">
              Registry Live
            </span>

            <select
              className="filter-select"
              value={timeFilter}
              onChange={(event) =>
                handleTimeFilterChange(event.target.value)
              }
            >
              <option value="1h">Last 1 hour</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="all">All records</option>
            </select>

            <button type="button" onClick={refresh}>
              Refresh
            </button>
          </div>
        </header>

        <section
          id="overview-section"
          className="cards-grid section-offset"
        >
          <div className="card">
            <p>Allowed</p>

            <h2 className="secure-text">
              {calculatedData.filteredAllowed.length}
            </h2>

            <span>Passed WRDN checks</span>
          </div>

          <div className="card">
            <p>Blocked</p>

            <h2 className="danger-text">
              {calculatedData.filteredBlocked.length}
            </h2>

            <span>Stopped by WRDN</span>
          </div>

          <div className="card">
            <p>Block rate</p>

            <h2>
              {calculatedData.blockRate}%
            </h2>

            <span>
              {calculatedData.totalEvents} events in this window
            </span>
          </div>

          <div className="card">
            <p>Highest risk</p>

            <h2 className="danger-text">
              {calculatedData.highestRiskScore}
            </h2>

            <span>
              {calculatedData.criticalCount} event
              {calculatedData.criticalCount === 1 ? "" : "s"} scored 90+
            </span>
          </div>
        </section>

        <p className="registry-insight">
          WRDN allowed{" "}
          <strong>{calculatedData.filteredAllowed.length}</strong>{" "}
          and blocked{" "}
          <strong>{calculatedData.filteredBlocked.length}</strong>{" "}
          ({calculatedData.blockRate}% blocked). Highest risk score is{" "}
          <strong>{calculatedData.highestRiskScore}/100</strong>.
        </p>

        <p className="last-updated">
          Last updated:{" "}
          {lastUpdated
            ? lastUpdated.toLocaleTimeString()
            : "Waiting..."}
        </p>

        <section
          id="charts-section"
          className="charts-grid section-offset"
        >
          <div className="chart-card">
            <div className="panel-header">
              <h3>Allowed and Blocked Activity</h3>

              <p>
                WRDN decisions during the selected time
                period.
              </p>
            </div>

            <div className="chart-wrapper">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <AreaChart
                  data={calculatedData.activityChartData}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.08)"
                  />

                  <XAxis
                    dataKey="time"
                    stroke="#8d96a5"
                  />

                  <YAxis
                    stroke="#8d96a5"
                    allowDecimals={false}
                  />

                  <Tooltip
                    contentStyle={{
                      background: "#111318",
                      border:
                        "1px solid rgba(255,255,255,0.12)",
                      borderRadius: "12px",
                      color: "#ffffff",
                    }}
                  />

                  <Area
                    type="monotone"
                    dataKey="allowed"
                    name="Allowed"
                    stroke="#20e487"
                    fill="rgba(32,228,135,0.18)"
                    strokeWidth={2}
                  />

                  <Area
                    type="monotone"
                    dataKey="blocked"
                    name="Blocked"
                    stroke="#ff506d"
                    fill="rgba(255,80,109,0.16)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="chart-card">
            <div className="panel-header">
              <h3>Risk Score Trend</h3>

              <p>
                Highest and average risk score for each
                period.
              </p>
            </div>

            <div className="chart-wrapper">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={calculatedData.riskChartData}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.08)"
                  />

                  <XAxis
                    dataKey="time"
                    stroke="#8d96a5"
                  />

                  <YAxis
                    stroke="#8d96a5"
                    domain={[0, 100]}
                  />

                  <Tooltip
                    contentStyle={{
                      background: "#111318",
                      border:
                        "1px solid rgba(255,255,255,0.12)",
                      borderRadius: "12px",
                      color: "#ffffff",
                    }}
                  />

                  <Line
                    type="monotone"
                    dataKey="highestRisk"
                    name="Highest risk"
                    stroke="#ff506d"
                    strokeWidth={3}
                    dot
                  />

                  <Line
                    type="monotone"
                    dataKey="averageRisk"
                    name="Average risk"
                    stroke="#ffca55"
                    strokeWidth={2}
                    dot
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        <section
          id="allowed-section"
          className="panel section-offset"
        >
          <div className="panel-header">
            <h3>Allowed Logs</h3>

            <p>
              Responses that passed the WRDN security
              checks.
            </p>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>User Prompt</th>
                  <th>AI Output</th>
                  <th>Status</th>
                  <th>Risk Score</th>
                </tr>
              </thead>

              <tbody>
                {calculatedData.filteredAllowed.length ===
                0 ? (
                  <tr>
                    <td colSpan={6}>
                      No allowed logs found for this time
                      range.
                    </td>
                  </tr>
                ) : (
                  calculatedData.filteredAllowed.map(
                    (log) => (
                      <tr key={log.id}>
                        <td>
                          {formatDateTime(log.timestamp)}
                        </td>

                        <td>
                          {log.username || "—"}
                        </td>

                        <td className="long-text">
                          {log.user_prompt}
                        </td>

                        <td className="long-text">
                          {log.raw_ai_output}
                        </td>

                        <td>
                          <span className="allowed-badge">
                            {String(
                              log.shield_status || "ALLOWED",
                            ).toUpperCase()}
                          </span>
                        </td>

                        <td>{log.risk_score}/100</td>
                      </tr>
                    ),
                  )
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section
          id="blocked-section"
          className="panel section-offset"
        >
          <div className="panel-header">
            <h3>Blocked Logs</h3>

            <p>
              Responses blocked or stopped by WRDN.
            </p>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>User Prompt</th>
                  <th>Status</th>
                  <th>Risk Score</th>
                  <th>Detection Reason</th>
                </tr>
              </thead>

              <tbody>
                {calculatedData.filteredBlocked.length ===
                0 ? (
                  <tr>
                    <td colSpan={6}>
                      No blocked logs found for this time
                      range.
                    </td>
                  </tr>
                ) : (
                  calculatedData.filteredBlocked.map(
                    (log) => (
                      <tr key={log.id}>
                        <td>
                          {formatDateTime(log.timestamp)}
                        </td>

                        <td>
                          {log.username || "—"}
                        </td>

                        <td className="long-text">
                          {log.user_prompt}
                        </td>

                        <td>
                          <span
                            className={
                              String(log.shield_status)
                                .toUpperCase() === "ALLOWED"
                                ? "allowed-badge"
                                : "risk-badge"
                            }
                          >
                            {String(
                              log.shield_status || "UNKNOWN",
                            ).toUpperCase()}
                          </span>
                        </td>

                        <td>{log.risk_score}/100</td>

                        <td className="long-text">
                          {log.detection_reason}
                        </td>
                      </tr>
                    ),
                  )
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section
          id="risk-section"
          className="panel section-offset"
        >
          <div className="panel-header">
            <h3>Risk Analysis</h3>

            <p>
              Simple view of how much was allowed, how much was
              blocked, and why.
            </p>
          </div>

          <p className="registry-insight">
            {calculatedData.totalEvents === 0
              ? "No shield events in this time range."
              : `Of ${calculatedData.totalEvents} events, ${calculatedData.filteredAllowed.length} were allowed and ${calculatedData.filteredBlocked.length} were blocked (${calculatedData.blockRate}%). Average risk ${calculatedData.averageRiskScore}/100. Highest ${calculatedData.highestRiskScore}/100.`}
          </p>

          <div
            className="risk-split"
            aria-label="Allowed versus blocked"
          >
            <div className="risk-split-bar">
              <span
                className="allowed"
                style={{
                  width: `${
                    calculatedData.totalEvents > 0
                      ? (calculatedData.filteredAllowed.length /
                          calculatedData.totalEvents) *
                        100
                      : 50
                  }%`,
                }}
              />
              <span
                className="blocked"
                style={{
                  width: `${
                    calculatedData.totalEvents > 0
                      ? (calculatedData.filteredBlocked.length /
                          calculatedData.totalEvents) *
                        100
                      : 50
                  }%`,
                }}
              />
            </div>
            <div className="risk-split-legend">
              <span className="secure-text">
                Allowed {calculatedData.filteredAllowed.length}
              </span>
              <span className="danger-text">
                Blocked {calculatedData.filteredBlocked.length}
              </span>
            </div>
          </div>

          <div className="cards-grid">
            <div className="card">
              <p>Highest risk</p>
              <h2 className="danger-text">
                {calculatedData.highestRiskScore}
              </h2>
              <span>Worst score in this window</span>
            </div>

            <div className="card">
              <p>Average risk</p>
              <h2>{calculatedData.averageRiskScore}</h2>
              <span>Mean across all events</span>
            </div>

            <div className="card">
              <p>Critical (90+)</p>
              <h2 className="danger-text">
                {calculatedData.criticalCount}
              </h2>
              <span>Events that need attention first</span>
            </div>

            <div className="card">
              <p>Protection</p>
              <h2
                className={
                  protectionEnabled
                    ? "secure-text"
                    : "danger-text"
                }
              >
                {protectionEnabled ? "ON" : "OFF"}
              </h2>
              <span>
                {protectionEnabled
                  ? "Shield is checking output"
                  : "Shield is bypassed"}
              </span>
            </div>
          </div>

          <div className="risk-simple-grid">
            <div className="risk-simple-box">
              <h4>Why it was blocked</h4>
              <p>Most common reasons in this window.</p>

              {calculatedData.topReasons.length === 0 ? (
                <p className="empty-hint">No blocks to explain.</p>
              ) : (
                <ol className="risk-reason-list">
                  {calculatedData.topReasons.map((item) => (
                    <li key={item.reason}>
                      <span>
                        {item.reason.length > 140
                          ? `${item.reason.slice(0, 140).trim()}…`
                          : item.reason}
                      </span>
                      <strong>{item.count}</strong>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <div className="risk-simple-box">
              <h4>Latest blocks</h4>
              <p>Newest blocked events. Full list is under Blocked Outputs.</p>

              {calculatedData.latestBlocked.length === 0 ? (
                <p className="empty-hint">No blocked events in this window.</p>
              ) : (
                <ul className="risk-latest-list">
                  {calculatedData.latestBlocked.map((log) => (
                    <li key={log.id}>
                      <div>
                        <span className="risk-badge">
                          {String(log.shield_status || "BLOCKED").toUpperCase()}
                        </span>
                        <em>{log.risk_score}/100</em>
                      </div>
                      <p>
                        {String(log.detection_reason || log.user_prompt || "—")
                          .replace(/\s+/g, " ")
                          .trim()
                          .slice(0, 160)}
                        {String(log.detection_reason || log.user_prompt || "")
                          .length > 160
                          ? "…"
                          : ""}
                      </p>
                      <small>
                        {formatDateTime(log.timestamp)}
                        {log.username ? ` · ${log.username}` : ""}
                      </small>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </section>

        <section
          id="settings-section"
          className="panel section-offset"
        >
          <div className="panel-header">
            <h3>Settings</h3>

            <p>
              Non-sensitive workspace preferences and WRDN
              protection controls.
            </p>
          </div>

          <div className="settings-grid">
            <div className="setting-row protection-setting-row">
              <div>
                <span>WRDN Protection</span>
                <p className="protection-setting-help">
                  {protectionEnabled
                    ? "Enabled: shield blocks unsafe AI output (normal secure mode)."
                    : "Disabled: raw AI output is shown (BYPASSED) for demo comparison."}
                </p>
                {protectionMessage ? (
                  <p className="protection-setting-message">
                    {protectionMessage}
                  </p>
                ) : null}
              </div>

              {isAdmin ? (
                <button
                  type="button"
                  className={`protection-toggle-button ${
                    protectionEnabled
                      ? "enabled"
                      : "disabled"
                  }`}
                  disabled={protectionBusy}
                  onClick={() => void toggleProtection()}
                >
                  {protectionBusy
                    ? "Updating..."
                    : protectionEnabled
                      ? "Disable Protection"
                      : "Enable Protection"}
                </button>
              ) : (
                <strong>
                  {protectionEnabled
                    ? "ENABLED"
                    : "DISABLED"}
                </strong>
              )}
            </div>

            <div className="setting-row">
              <span>Signed-in role</span>
              <strong>
                {isAdmin ? "ADMIN" : "EMPLOYEE"}
              </strong>
            </div>

            <div className="setting-row">
              <span>Application</span>
              <strong>WRDN Enterprise Prompt Shield</strong>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}