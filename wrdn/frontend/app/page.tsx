"use client";

import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import AppSidebar, {
  type AppSection,
} from "@/components/AppSidebar";

import ChatInterface from "@/components/ChatInterface";
import RegistryDashboard from "@/components/RegistryDashboard";

import {
  clearAuthSession,
  getAuthUser,
  type AuthUser,
} from "@/lib/authApi";

import {
  loadChatSessions,
  type ChatSession,
} from "@/lib/chatHistory";

export default function Home() {
  const router = useRouter();

  const [user, setUser] = useState<AuthUser | null>(
    null,
  );
  const [checkingAuth, setCheckingAuth] =
    useState(true);

  const [activeSection, setActiveSection] =
    useState<AppSection>("chat");

  const [resetSignal, setResetSignal] =
    useState(0);

  const [recentChats, setRecentChats] = useState<
    ChatSession[]
  >([]);
  const [loadChatId, setLoadChatId] = useState<
    string | null
  >(null);
  const [activeChatId, setActiveChatId] = useState<
    string | null
  >(null);

  const isChat = activeSection === "chat";
  const isAdmin = user?.role === "ADMIN";

  const handleHistoryChange = useCallback(
    (sessions: ChatSession[]) => {
      setRecentChats(sessions);
    },
    [],
  );

  const handleActiveSessionChange = useCallback(
    (sessionId: string | null) => {
      setActiveChatId(sessionId);
    },
    [],
  );

  function startNewChat() {
    setLoadChatId(null);
    setActiveChatId(null);
    setActiveSection("chat");
    setResetSignal((current) => current + 1);
  }

  function handleSelectChat(chatId: string) {
    setActiveSection("chat");
    setActiveChatId(chatId);
    // Re-trigger load even when selecting the same chat.
    setLoadChatId(null);
    window.setTimeout(() => {
      setLoadChatId(chatId);
    }, 0);
  }

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

    setUser(currentUser);
    setCheckingAuth(false);
    setRecentChats(loadChatSessions());
  }, [router]);

  useEffect(() => {
    const section = new URLSearchParams(
      window.location.search,
    ).get("section");

    if (!section || section === "chat") {
      setActiveSection("chat");
      return;
    }

    if (
      section === "dashboard" ||
      section === "live-registry" ||
      section === "allowed" ||
      section === "blocked" ||
      section === "risk" ||
      section === "settings"
    ) {
      setActiveSection(section);
    }
  }, []);

  useEffect(() => {
    if (
      activeSection === "chat" ||
      activeSection === "policies"
    ) {
      return;
    }

    const sectionMap: Record<
      Exclude<AppSection, "chat" | "policies">,
      string
    > = {
      dashboard: "overview-section",
      "live-registry": "live-registry-section",
      allowed: "allowed-section",
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

    return () => window.clearTimeout(timeoutId);
  }, [activeSection]);

  if (checkingAuth || !user) {
    return (
      <div className="wrdn-application">
        <main className="application-content">
          <p style={{ padding: 24 }}>
            Loading dashboard...
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="wrdn-application">
      <AppSidebar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        onNewChat={startNewChat}
        isAdmin={isAdmin}
        username={user.username}
        onLogout={handleLogout}
      />

      <main className="application-content">
        {isChat ? (
          <ChatInterface
            resetSignal={resetSignal}
            loadChatId={loadChatId}
            onHistoryChange={handleHistoryChange}
            onActiveSessionChange={
              handleActiveSessionChange
            }
            recentChats={recentChats.map((chat) => ({
              id: chat.id,
              title: chat.title,
            }))}
            activeChatId={activeChatId}
            onSelectChat={handleSelectChat}
            onNewChat={startNewChat}
          />
        ) : (
          <RegistryDashboard />
        )}
      </main>
    </div>
  );
}
