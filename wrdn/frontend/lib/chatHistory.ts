export interface StoredChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  riskScore?: number;
  detectionLayer?: string;
  detectionReason?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  updatedAt: string;
  messages: StoredChatMessage[];
}

const STORAGE_KEY = "wrdn_chat_history_v1";
export const MAX_CHAT_SESSIONS = 5;

function canUseStorage() {
  return typeof window !== "undefined";
}

export function loadChatSessions(): ChatSession[] {
  if (!canUseStorage()) {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(
      STORAGE_KEY,
    );

    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter(
        (item) =>
          item &&
          typeof item.id === "string" &&
          typeof item.title === "string" &&
          Array.isArray(item.messages) &&
          item.messages.length > 0,
      )
      .slice(0, MAX_CHAT_SESSIONS) as ChatSession[];
  } catch {
    return [];
  }
}

function saveChatSessions(
  sessions: ChatSession[],
) {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(
      sessions.slice(0, MAX_CHAT_SESSIONS),
    ),
  );
}

export function getChatSessionTitle(
  messages: StoredChatMessage[],
): string {
  const firstUser = messages.find(
    (message) => message.role === "user",
  );

  if (!firstUser?.content?.trim()) {
    return "New chat";
  }

  const text = firstUser.content.trim();

  return text.length > 36
    ? `${text.slice(0, 36)}…`
    : text;
}

export function upsertChatSession(
  session: ChatSession,
): ChatSession[] {
  if (!session.messages.length) {
    return loadChatSessions();
  }

  const current = loadChatSessions().filter(
    (item) => item.id !== session.id,
  );

  const next = [session, ...current].slice(
    0,
    MAX_CHAT_SESSIONS,
  );

  saveChatSessions(next);
  return next;
}

export function getChatSessionById(
  sessionId: string,
): ChatSession | null {
  return (
    loadChatSessions().find(
      (item) => item.id === sessionId,
    ) ?? null
  );
}

export function createChatSessionId() {
  return `chat-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}
