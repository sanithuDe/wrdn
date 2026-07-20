"use client";

import { useRegistryData } from "@/hooks/useRegistryData";
import { useMemo, useState } from "react";
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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function parseRegistryTime(timestamp: string) {
  if (!timestamp) return null;

  const normalized = timestamp.replace(" ", "T");
  const date = new Date(normalized);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date;
}

function formatBucket(date: Date, filter: TimeFilter) {
  if (filter === "1h" || filter === "24h") {
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

function getTimeWindowMs(filter: TimeFilter) {
  if (filter === "1h") return 60 * 60 * 1000;
  if (filter === "24h") return 24 * 60 * 60 * 1000;
  if (filter === "7d") return 7 * 24 * 60 * 60 * 1000;

  return null;
}

export default function RegistryDashboard() {
  const {
    registryData,
    loading,
    error,
    lastUpdated,
    refresh,
  } = useRegistryData();

  const [timeFilter, setTimeFilter] =
    useState<TimeFilter>("all");

  function scrollToSection(sectionId: string) {
    const element = document.getElementById(sectionId);

    if (element) {
      element.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }

  const candidateEvaluations =
    registryData?.candidate_evaluations || [];

  const blockedEmails =
    registryData?.blocked_emails || [];

  const filteredData = useMemo(() => {
    const allEvents = [
      ...candidateEvaluations.map((item: any) => ({
        ...item,
        eventType: "candidate",
        date: parseRegistryTime(item.timestamp),
      })),

      ...blockedEmails.map((item: any) => ({
        ...item,
        eventType: "blocked",
        date: parseRegistryTime(item.timestamp),
      })),
    ].filter((item: any) => item.date);

    if (allEvents.length === 0) {
      return {
        filteredCandidates: [],
        filteredBlocked: [],
        activityChartData: [],
        riskChartData: [],
      };
    }

    const latestTime = Math.max(
      ...allEvents.map((item: any) =>
        item.date.getTime(),
      ),
    );

    const windowMs = getTimeWindowMs(timeFilter);

    const filteredEvents =
      windowMs === null
        ? allEvents
        : allEvents.filter(
            (item: any) =>
              latestTime - item.date.getTime() <=
              windowMs,
          );

    const filteredCandidates =
      filteredEvents.filter(
        (item: any) =>
          item.eventType === "candidate",
      );

    const filteredBlocked =
      filteredEvents.filter(
        (item: any) =>
          item.eventType === "blocked",
      );

    const bucketMap = new Map<
      string,
      {
        time: string;
        candidates: number;
        blocked: number;
        maxRisk: number;
      }
    >();

    filteredEvents.forEach((item: any) => {
      const bucket = formatBucket(
        item.date,
        timeFilter,
      );

      if (!bucketMap.has(bucket)) {
        bucketMap.set(bucket, {
          time: bucket,
          candidates: 0,
          blocked: 0,
          maxRisk: 0,
        });
      }

      const existing = bucketMap.get(bucket)!;

      if (item.eventType === "candidate") {
        existing.candidates += 1;
      }

      if (item.eventType === "blocked") {
        existing.blocked += 1;

        existing.maxRisk = Math.max(
          existing.maxRisk,
          item.risk_score || 0,
        );
      }
    });

    const activityChartData =
      Array.from(bucketMap.values());

    const riskChartData =
      activityChartData.map((item) => ({
        time: item.time,
        riskScore: item.maxRisk,
      }));

    return {
      filteredCandidates,
      filteredBlocked,
      activityChartData,
      riskChartData,
    };
  }, [
    candidateEvaluations,
    blockedEmails,
    timeFilter,
  ]);

  if (loading) {
    return (
      <div className="loading-box">
        Loading WRDN registry...
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-box">
        <h2>Registry Connection Failed</h2>

        <p>{error}</p>

        <button onClick={refresh}>
          Retry
        </button>
      </div>
    );
  }

  const highestRiskScore =
    filteredData.filteredBlocked.length > 0
      ? Math.max(
          ...filteredData.filteredBlocked.map(
            (item: any) =>
              item.risk_score || 0,
          ),
        )
      : 0;

  return (
    <div className="dashboard-page">
      <aside className="sidebar">
        <div>
          <h2>WRDN</h2>

          <nav>
            <button
              className="active"
              onClick={() =>
                scrollToSection(
                  "overview-section",
                )
              }
            >
              Overview
            </button>

            <button
              onClick={() =>
                scrollToSection(
                  "live-registry-section",
                )
              }
            >
              Live Registry
            </button>

            <button
              onClick={() =>
                scrollToSection(
                  "charts-section",
                )
              }
            >
              Charts
            </button>

            <button
              onClick={() =>
                scrollToSection(
                  "candidate-section",
                )
              }
            >
              Candidate Logs
            </button>

            <button
              onClick={() =>
                scrollToSection(
                  "blocked-section",
                )
              }
            >
              Blocked Outputs
            </button>

            <button
              onClick={() =>
                scrollToSection(
                  "risk-section",
                )
              }
            >
              Risk Analysis
            </button>

            <button
              onClick={() =>
                scrollToSection(
                  "settings-section",
                )
              }
            >
              Settings
            </button>
          </nav>
        </div>

        <p className="sidebar-footer">
          Prompt Injection Defense
        </p>
      </aside>

      <main
        className="main-content"
        id="live-registry-section"
      >
        <header className="topbar">
          <div>
            <h1>Live Governance Registry</h1>

            <p>
              Real-time WRDN monitoring
              dashboard
            </p>
          </div>

          <div className="topbar-right">
            <span className="live-status">
              System Secure
            </span>

            <select
              className="filter-select"
              value={timeFilter}
              onChange={(event) =>
                setTimeFilter(
                  event.target
                    .value as TimeFilter,
                )
              }
            >
              <option value="1h">
                Last 1 hour
              </option>

              <option value="24h">
                Last 24 hours
              </option>

              <option value="7d">
                Last 7 days
              </option>

              <option value="all">
                All records
              </option>
            </select>

            <button onClick={refresh}>
              Refresh
            </button>
          </div>
        </header>

        <section
          id="overview-section"
          className="cards-grid section-offset"
        >
          <div className="card">
            <p>Company</p>

            <h2>
              {registryData.company_name}
            </h2>

            <span>Protected by WRDN</span>
          </div>

          <div className="card">
            <p>Database Status</p>

            <h2 className="secure-text">
              {registryData.database_status}
            </h2>

            <span>
              Live registry active
            </span>
          </div>

          <div className="card">
            <p>Candidate Evaluations</p>

            <h2>
              {
                filteredData
                  .filteredCandidates.length
              }
            </h2>

            <span>Filtered records</span>
          </div>

          <div className="card">
            <p>Blocked Emails</p>

            <h2 className="danger-text">
              {
                filteredData
                  .filteredBlocked.length
              }
            </h2>

            <span>
              Filtered sanitized outputs
            </span>
          </div>
        </section>

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
              <h3>
                Registry Activity Trend
              </h3>

              <p>
                Candidate evaluations and
                blocked outputs over time.
              </p>
            </div>

            <div className="chart-wrapper">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <AreaChart
                  data={
                    filteredData
                      .activityChartData
                  }
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
                    dataKey="candidates"
                    name="Candidate logs"
                    stroke="#20e487"
                    fill="rgba(32, 228, 135, 0.18)"
                    strokeWidth={2}
                  />

                  <Area
                    type="monotone"
                    dataKey="blocked"
                    name="Blocked outputs"
                    stroke="#ff506d"
                    fill="rgba(255, 80, 109, 0.16)"
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
                Highest blocked-output risk
                score per time bucket.
              </p>
            </div>

            <div className="chart-wrapper">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={
                    filteredData.riskChartData
                  }
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
                    dataKey="riskScore"
                    name="Risk score"
                    stroke="#ff506d"
                    strokeWidth={3}
                    dot
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        <section
          id="candidate-section"
          className="panel section-offset"
        >
          <div className="panel-header">
            <h3>
              Candidate Evaluation Registry
            </h3>

            <p>
              Approved salary decisions
              generated through WRDN workflow.
            </p>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Candidate</th>
                  <th>Email</th>
                  <th>Approved Offer</th>
                  <th>Justification</th>
                </tr>
              </thead>

              <tbody>
                {filteredData
                  .filteredCandidates.length ===
                0 ? (
                  <tr>
                    <td colSpan={5}>
                      No candidate records found
                      for this time range.
                    </td>
                  </tr>
                ) : (
                  filteredData.filteredCandidates.map(
                    (
                      item: any,
                      index: number,
                    ) => (
                      <tr
                        key={`${item.email}-${index}`}
                      >
                        <td>
                          {item.timestamp}
                        </td>

                        <td>
                          {item.candidate}
                        </td>

                        <td>{item.email}</td>

                        <td>
                          <span className="salary-badge">
                            {
                              item.approved_max_salary_offer
                            }
                          </span>
                        </td>

                        <td className="long-text">
                          {item.justification}
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
          id="blocked-section"
          className="panel section-offset"
        >
          <div className="panel-header">
            <h3>Blocked Email Registry</h3>

            <p>
              High-risk output attempts
              blocked by WRDN sanitizer.
            </p>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Recipient</th>
                  <th>Subject</th>
                  <th>Risk Score</th>
                  <th>Block Reason</th>
                </tr>
              </thead>

              <tbody>
                {filteredData.filteredBlocked
                  .length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      No blocked outputs found
                      for this time range.
                    </td>
                  </tr>
                ) : (
                  filteredData.filteredBlocked.map(
                    (
                      item: any,
                      index: number,
                    ) => (
                      <tr
                        key={`${item.recipient}-${index}`}
                      >
                        <td>
                          {item.timestamp}
                        </td>

                        <td>
                          {item.recipient}
                        </td>

                        <td>
                          {item.subject}
                        </td>

                        <td>
                          <span className="risk-badge">
                            {item.risk_score}
                          </span>
                        </td>

                        <td>
                          {item.block_reason}
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
              Live security summary based on
              selected time range.
            </p>
          </div>

          <div className="cards-grid">
            <div className="card">
              <p>Highest Risk Score</p>

              <h2 className="danger-text">
                {highestRiskScore}
              </h2>

              <span>
                Maximum detected risk
              </span>
            </div>

            <div className="card">
              <p>Blocked Attempts</p>

              <h2>
                {
                  filteredData
                    .filteredBlocked.length
                }
              </h2>

              <span>
                Total sanitized outputs
              </span>
            </div>

            <div className="card">
              <p>Protection Layer</p>

              <h2>Sanitizer</h2>

              <span>
                Output filtering active
              </span>
            </div>

            <div className="card">
              <p>Registry Mode</p>

              <h2 className="secure-text">
                LIVE
              </h2>

              <span>
                Auto refresh enabled
              </span>
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
              Current WRDN frontend and backend
              connection details.
            </p>
          </div>

          <div className="settings-grid">
            <div className="setting-row">
              <span>Frontend</span>

              <strong>
                Next.js Dashboard
              </strong>
            </div>

            <div className="setting-row">
              <span>Backend API</span>

              <strong>
                {API_URL}/api/registry
              </strong>
            </div>

            <div className="setting-row">
              <span>Refresh Interval</span>

              <strong>3 Seconds</strong>
            </div>

            <div className="setting-row">
              <span>
                Selected Time Range
              </span>

              <strong>{timeFilter}</strong>
            </div>

            <div className="setting-row">
              <span>
                Protection Status
              </span>

              <strong className="secure-text">
                Enabled
              </strong>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}