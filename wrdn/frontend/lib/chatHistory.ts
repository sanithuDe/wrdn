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
  ownerUsername?: string;
  ownerRole?: string;
  clientId?: string;
}

export type ChatUserContext = {
  username: string;
  role: string;
  clientId: string;
};

export const MAX_CHAT_SESSIONS = 5;
const MAX_TEAM_CHAT_SESSIONS = 20;

function canUseStorage() {
  return typeof window !== "undefined";
}

function personalKey(username: string) {
  return `wrdn_chat_v2:${username.trim().toLowerCase()}`;
}

function teamKey(clientId: string) {
  return `wrdn_team_chats_v2:${clientId.trim().toLowerCase()}`;
}

function parseSessions(raw: string | null): ChatSession[] {
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter(
      (item) =>
        item &&
        typeof item.id === "string" &&
        typeof item.title === "string" &&
        Array.isArray(item.messages) &&
        item.messages.length > 0,
    ) as ChatSession[];
  } catch {
    return [];
  }
}

function readKey(key: string): ChatSession[] {
  if (!canUseStorage()) {
    return [];
  }

  return parseSessions(
    window.localStorage.getItem(key),
  );
}

function writeKey(
  key: string,
  sessions: ChatSession[],
  max: number,
) {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.setItem(
    key,
    JSON.stringify(sessions.slice(0, max)),
  );
}

function withOwner(
  session: ChatSession,
  ctx: ChatUserContext,
): ChatSession {
  return {
    ...session,
    ownerUsername: ctx.username,
    ownerRole: ctx.role,
    clientId: ctx.clientId,
  };
}

/** Personal chats for one user only. */
export function loadPersonalChatSessions(
  ctx: ChatUserContext,
): ChatSession[] {
  return readKey(personalKey(ctx.username)).slice(
    0,
    MAX_CHAT_SESSIONS,
  );
}

/**
 * What the signed-in user may see in Recent Chats.
 * Employee: own chats only.
 * Admin: own chats + other users on the same client.
 */
export function loadVisibleChatSessions(
  ctx: ChatUserContext,
): ChatSession[] {
  const personal = loadPersonalChatSessions(ctx).map(
    (session) => withOwner(session, ctx),
  );

  const isAdmin =
    ctx.role.trim().toUpperCase() === "ADMIN";

  if (!isAdmin) {
    return personal;
  }

  const team = readKey(teamKey(ctx.clientId)).filter(
    (session) =>
      (session.ownerUsername || "")
        .trim()
        .toLowerCase() !==
        ctx.username.trim().toLowerCase() &&
      (session.clientId || ctx.clientId) ===
        ctx.clientId,
  );

  const merged = [...personal, ...team].sort(
    (a, b) =>
      Date.parse(b.updatedAt || "") -
      Date.parse(a.updatedAt || ""),
  );

  // Keep a bit more for admins so team history is visible.
  return merged.slice(0, MAX_CHAT_SESSIONS + 10);
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

export function displayChatTitle(
  session: ChatSession,
  viewerUsername: string,
): string {
  const owner = (session.ownerUsername || "").trim();
  const base = session.title || "Chat";

  if (
    owner &&
    owner.toLowerCase() !==
      viewerUsername.trim().toLowerCase()
  ) {
    return `[${owner}] ${base}`;
  }

  return base;
}

export function upsertChatSession(
  session: ChatSession,
  ctx: ChatUserContext,
): ChatSession[] {
  if (!session.messages.length) {
    return loadVisibleChatSessions(ctx);
  }

  const owned = withOwner(session, ctx);

  const personal = loadPersonalChatSessions(ctx).filter(
    (item) => item.id !== owned.id,
  );
  const nextPersonal = [owned, ...personal].slice(
    0,
    MAX_CHAT_SESSIONS,
  );
  writeKey(
    personalKey(ctx.username),
    nextPersonal,
    MAX_CHAT_SESSIONS,
  );

  // Mirror into client team store so admins can review
  // employee (and peer) activity on this client.
  const team = readKey(teamKey(ctx.clientId)).filter(
    (item) => item.id !== owned.id,
  );
  writeKey(
    teamKey(ctx.clientId),
    [owned, ...team],
    MAX_TEAM_CHAT_SESSIONS,
  );

  return loadVisibleChatSessions(ctx);
}

export function getChatSessionById(
  sessionId: string,
  ctx: ChatUserContext,
): ChatSession | null {
  return (
    loadVisibleChatSessions(ctx).find(
      (item) => item.id === sessionId,
    ) ?? null
  );
}

export function createChatSessionId() {
  return `chat-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

/** @deprecated use loadVisibleChatSessions with user ctx */
export function loadChatSessions(): ChatSession[] {
  return [];
}
