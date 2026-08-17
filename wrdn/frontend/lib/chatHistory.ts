export interface StoredChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  riskScore?: number;
  detectionLayer?: string;
  detectionReason?: string;
  detectionLog?: Array<{
    step: number;
    name: string;
    status: string;
    risk_score: number;
    detail: string;
  }>;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt?: string;
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

function sessionCreatedAt(session: ChatSession) {
  return Date.parse(
    session.createdAt || session.updatedAt || "",
  );
}

function sortNewestFirst(sessions: ChatSession[]) {
  return [...sessions].sort(
    (a, b) => sessionCreatedAt(b) - sessionCreatedAt(a),
  );
}

function upsertIntoList(
  sessions: ChatSession[],
  next: ChatSession,
  max: number,
) {
  const existingIndex = sessions.findIndex(
    (item) => item.id === next.id,
  );

  if (existingIndex >= 0) {
    const previous = sessions[existingIndex];
    const updated = {
      ...next,
      createdAt:
        previous.createdAt ||
        previous.updatedAt ||
        next.createdAt ||
        next.updatedAt,
    };
    const locked = [...sessions];
    locked[existingIndex] = updated;
    return locked.slice(0, max);
  }

  return [
    {
      ...next,
      createdAt:
        next.createdAt || next.updatedAt,
    },
    ...sessions,
  ].slice(0, max);
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

export function loadPersonalChatSessions(
  ctx: ChatUserContext,
): ChatSession[] {
  return readKey(personalKey(ctx.username)).slice(
    0,
    MAX_CHAT_SESSIONS,
  );
}

export function loadVisibleChatSessions(
  ctx: ChatUserContext,
): ChatSession[] {
  const personal = loadPersonalChatSessions(ctx).map(
    (session) => withOwner(session, ctx),
  );

  const isAdmin =
    ctx.role.trim().toUpperCase() === "ADMIN";

  if (!isAdmin) {
    return sortNewestFirst(personal);
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

  return sortNewestFirst([...personal, ...team]).slice(
    0,
    MAX_CHAT_SESSIONS + 10,
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

  const nextPersonal = upsertIntoList(
    loadPersonalChatSessions(ctx),
    owned,
    MAX_CHAT_SESSIONS,
  );
  writeKey(
    personalKey(ctx.username),
    nextPersonal,
    MAX_CHAT_SESSIONS,
  );

  const nextTeam = upsertIntoList(
    readKey(teamKey(ctx.clientId)),
    owned,
    MAX_TEAM_CHAT_SESSIONS,
  );
  writeKey(
    teamKey(ctx.clientId),
    nextTeam,
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
