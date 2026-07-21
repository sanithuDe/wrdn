"use client";

import { useEffect, useState } from "react";

import AppSidebar, {
    type AppSection,
} from "@/components/AppSidebar";

import ChatInterface from "@/components/ChatInterface";
import RegistryDashboard from "@/components/RegistryDashboard";

export default function Home() {
  const [activeSection, setActiveSection] =
    useState<AppSection>("chat");

  const [resetSignal, setResetSignal] =
    useState(0);

  const isChat = activeSection === "chat";

  function startNewChat() {
    setResetSignal((current) => current + 1);
  }

  useEffect(() => {
    if (activeSection === "chat") {
      return;
    }

    const sectionMap: Record<
      Exclude<AppSection, "chat">,
      string
    > = {
      dashboard: "overview-section",
      "live-registry": "live-registry-section",
      blocked: "blocked-section",
      risk: "risk-section",
      settings: "settings-section",
    };

    const sectionId = sectionMap[activeSection];

    const timeoutId = window.setTimeout(() => {
      document
        .getElementById(sectionId)
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
    }, 100);

    return () =>
      window.clearTimeout(timeoutId);
  }, [activeSection]);

  return (
    <div className="wrdn-application">
      <AppSidebar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        onNewChat={startNewChat}
      />

      <main className="application-content">
        {isChat ? (
          <ChatInterface
            resetSignal={resetSignal}
          />
        ) : (
          <RegistryDashboard />
        )}
      </main>
    </div>
  );
}