"use client";

export type AppSection =
  | "chat"
  | "dashboard"
  | "live-registry"
  | "allowed"
  | "blocked"
  | "risk"
  | "settings";

interface AppSidebarProps {
  activeSection: AppSection;
  onSectionChange: (
    section: AppSection,
  ) => void;
  onNewChat: () => void;
}

export default function AppSidebar({
  activeSection,
  onSectionChange,
  onNewChat,
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
          <button
            className={
              activeSection === "chat"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("chat")
            }
          >
            AI Chat
          </button>

          <button
            className={
              activeSection === "dashboard"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("dashboard")
            }
          >
            Security Dashboard
          </button>

          <button
            className={
              activeSection === "live-registry"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("live-registry")
            }
          >
            Live Registry
          </button>

          <button
            className={
              activeSection === "allowed"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("allowed")
            }
          >
            Allowed Logs
          </button>

          <button
            className={
              activeSection === "blocked"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("blocked")
            }
          >
            Blocked Outputs
          </button>

          <button
            className={
              activeSection === "risk"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("risk")
            }
          >
            Risk Analysis
          </button>

          <button
            className={
              activeSection === "settings"
                ? "active"
                : ""
            }
            onClick={() =>
              onSectionChange("settings")
            }
          >
            Settings
          </button>
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

        <p className="sidebar-version">
          WRDN v2.0
        </p>
      </div>
    </aside>
  );
}