"use client";
import Link from "next/link";

export type AppSection =
  | "chat"
  | "policies"
  | "dashboard"
  | "live-registry"
  | "allowed"
  | "blocked"
  | "risk"
  | "settings";

interface AppSidebarProps {
  activeSection: AppSection;
  onSectionChange: (section: AppSection) => void;
  onNewChat: () => void;
  isAdmin?: boolean;
  username?: string;
  onLogout?: () => void;
}

export default function AppSidebar({
  activeSection,
  onSectionChange,
  onNewChat,
  isAdmin = false,
  username,
  onLogout,
}: AppSidebarProps) {
  return (
    <aside className="app-sidebar">
      <div>
        <div className="app-brand">
          <div className="app-brand-logo">
            W
          </div>

          <div>
            <h2>WRDN</h2>
            <p>Enterprise Prompt Shield</p>
          </div>
        </div>

        <button
          className="new-chat-button"
          onClick={() => {
            onNewChat();
            onSectionChange("chat");
          }}
        >
          <span>＋</span>
          New Chat
        </button>

        <nav className="app-navigation">
          <Link
            href="/?section=chat"
            className={`nav-link ${
              activeSection === "chat" ? "active" : ""
            }`}
            onClick={() => onSectionChange("chat")}
          >
            AI Chat
          </Link>

          {isAdmin && (
            <Link
              href="/policies"
              className={`nav-link ${
                activeSection === "policies" ? "active" : ""
              }`}
            >
              Policy Upload
            </Link>
          )}

          <Link
            href="/?section=dashboard"
            className={`nav-link ${
              activeSection === "dashboard" ? "active" : ""
            }`}
            onClick={() => onSectionChange("dashboard")}
          >
            Security Dashboard
          </Link>

          <Link
            href="/?section=live-registry"
            className={`nav-link ${
              activeSection === "live-registry" ? "active" : ""
            }`}
            onClick={() =>
              onSectionChange("live-registry")
            }
          >
            Live Registry
          </Link>

          <Link
            href="/?section=allowed"
            className={`nav-link ${
              activeSection === "allowed" ? "active" : ""
            }`}
            onClick={() => onSectionChange("allowed")}
          >
            Allowed Logs
          </Link>

          <Link
            href="/?section=blocked"
            className={`nav-link ${
              activeSection === "blocked" ? "active" : ""
            }`}
            onClick={() => onSectionChange("blocked")}
          >
            Blocked Outputs
          </Link>

          <Link
            href="/?section=risk"
            className={`nav-link ${
              activeSection === "risk" ? "active" : ""
            }`}
            onClick={() => onSectionChange("risk")}
          >
            Risk Analysis
          </Link>

          <Link
            href="/?section=settings"
            className={`nav-link ${
              activeSection === "settings" ? "active" : ""
            }`}
            onClick={() => onSectionChange("settings")}
          >
            Settings
          </Link>
        </nav>
      </div>

      <div className="app-sidebar-bottom">
        <div className="protection-card">
          <span className="protection-dot" />

          <div>
            <strong>
              Protection Active
            </strong>

            <p>
              Gemini output monitoring
            </p>
          </div>
        </div>

        {username && (
          <p
            style={{
              color: "#94a3b8",
              fontSize: 12,
              marginTop: 12,
            }}
          >
            Signed in as {username}
            {isAdmin ? " (ADMIN)" : " (EMPLOYEE)"}
          </p>
        )}

        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            style={{
              marginTop: 8,
              width: "100%",
              padding: 8,
              borderRadius: 8,
              border: "1px solid #334155",
              background: "#111827",
              color: "#e2e8f0",
              cursor: "pointer",
            }}
          >
            Logout
          </button>
        )}

        <p className="sidebar-version">
          WRDN v2.0
        </p>
      </div>
    </aside>
  );
}