"use client";

import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  sendChatMessage,
  type ChatApiResponse,
} from "@/lib/chatApi";

import { getAuthUser } from "@/lib/authApi";

import {
  createChatSessionId,
  getChatSessionById,
  getChatSessionTitle,
  loadVisibleChatSessions,
  upsertChatSession,
  type ChatSession,
  type ChatUserContext,
  type StoredChatMessage,
} from "@/lib/chatHistory";

interface ChatMessage extends StoredChatMessage {}

interface ChatInterfaceProps {
  resetSignal: number;
  loadChatId?: string | null;
  onHistoryChange?: (sessions: ChatSession[]) => void;
  onActiveSessionChange?: (
    sessionId: string | null,
  ) => void;
  recentChats?: Array<{
    id: string;
    title: string;
    ownerUsername?: string;
  }>;
  activeChatId?: string | null;
  onSelectChat?: (chatId: string) => void;
  onNewChat?: () => void;
  isAdmin?: boolean;
}

const starterQuestions = [
  "Explain the company services.",
  "Show me general employee information.",
  "What security protections are active?",
  "Summarize recent company activity.",
];

function createMessageId() {
  return `${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`;
}

function getAssistantContent(data: ChatApiResponse) {
  return (
    data.final_output ||
    data.response ||
    data.answer ||
    "The server returned an empty response."
  );
}

export default function ChatInterface({
  resetSignal,
  loadChatId = null,
  onHistoryChange,
  onActiveSessionChange,
  recentChats = [],
  activeChatId = null,
  onSelectChat,
  onNewChat,
  isAdmin = false,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(
    [],
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [clientId, setClientId] = useState("");
  const [username, setUsername] = useState("");
  const [userRole, setUserRole] = useState("");
  const [viewOnlyOwner, setViewOnlyOwner] = useState<
    string | null
  >(null);
  const [protectionEnabled, setProtectionEnabled] =
    useState(true);
  const [sessionId, setSessionId] = useState(() =>
    createChatSessionId(),
  );

  const messageEndRef = useRef<HTMLDivElement | null>(
    null,
  );
  const messagesRef = useRef<ChatMessage[]>([]);
  const sessionIdRef = useRef(sessionId);
  const lastHandledReset = useRef(resetSignal);
  const lastLoadedChatId = useRef<string | null>(null);

  function getChatCtx(): ChatUserContext | null {
    if (!username.trim() || !clientId.trim()) {
      return null;
    }

    return {
      username: username.trim(),
      role: userRole || "EMPLOYEE",
      clientId: clientId.trim(),
    };
  }

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    const ctx = getChatCtx();
    if (!ctx) {
      return;
    }
    onHistoryChange?.(loadVisibleChatSessions(ctx));
  }, [onHistoryChange, username, clientId, userRole]);

  function publishHistory(
    sessions: ChatSession[],
    activeId: string | null,
  ) {
    onHistoryChange?.(sessions);
    onActiveSessionChange?.(activeId);
  }

  function persistMessages(
    nextMessages: ChatMessage[],
    id = sessionIdRef.current,
    options: { silent?: boolean } = {},
  ) {
    const ctx = getChatCtx();
    if (!ctx) {
      return [];
    }

    if (viewOnlyOwner) {
      if (!options.silent) {
        publishHistory(loadVisibleChatSessions(ctx), id);
      }
      return loadVisibleChatSessions(ctx);
    }

    if (nextMessages.length === 0) {
      if (!options.silent) {
        publishHistory(loadVisibleChatSessions(ctx), id);
      }
      return loadVisibleChatSessions(ctx);
    }

    const existing = getChatSessionById(id, ctx);
    const session: ChatSession = {
      id,
      title: getChatSessionTitle(nextMessages),
      createdAt:
        existing?.createdAt || existing?.updatedAt,
      updatedAt: new Date().toISOString(),
      messages: nextMessages,
    };

    const sessions = upsertChatSession(session, ctx);
    if (options.silent) {
      onHistoryChange?.(sessions);
    } else {
      publishHistory(sessions, id);
    }
    return sessions;
  }

  function startBlankChat() {
    const nextId = createChatSessionId();
    sessionIdRef.current = nextId;
    setSessionId(nextId);
    setMessages([]);
    messagesRef.current = [];
    setInput("");
    setError("");
    setSending(false);
    setViewOnlyOwner(null);
    onActiveSessionChange?.(null);
  }

  useEffect(() => {
    if (resetSignal === lastHandledReset.current) {
      return;
    }

    lastHandledReset.current = resetSignal;
    if (!viewOnlyOwner) {
      persistMessages(messagesRef.current);
    }
    startBlankChat();
    const ctx = getChatCtx();
    if (ctx) {
      publishHistory(loadVisibleChatSessions(ctx), null);
    }
  }, [resetSignal]);

  useEffect(() => {
    if (!loadChatId) {
      lastLoadedChatId.current = null;
      return;
    }

    const ctx = getChatCtx();
    if (!ctx) {
      return;
    }

    if (
      sessionIdRef.current !== loadChatId &&
      messagesRef.current.length > 0 &&
      !viewOnlyOwner
    ) {
      persistMessages(
        messagesRef.current,
        sessionIdRef.current,
        { silent: true },
      );
    }

    const session = getChatSessionById(loadChatId, ctx);
    if (!session) {
      return;
    }

    if (lastLoadedChatId.current === loadChatId) {
      return;
    }

    lastLoadedChatId.current = loadChatId;
    sessionIdRef.current = session.id;
    setSessionId(session.id);
    setMessages(session.messages);
    messagesRef.current = session.messages;
    setInput("");
    setError("");
    setSending(false);

    const owner = (session.ownerUsername || "").trim();
    if (
      owner &&
      owner.toLowerCase() !== ctx.username.toLowerCase()
    ) {
      setViewOnlyOwner(owner);
    } else {
      setViewOnlyOwner(null);
    }

    onActiveSessionChange?.(session.id);
  }, [loadChatId, username, clientId, userRole]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, sending]);

  useEffect(() => {
    const user = getAuthUser();

    if (!user?.client_id) {
      setError("Please login first.");
      setClientId("");
      setUsername("");
      setUserRole("");
      return;
    }

    setClientId(user.client_id);
    setUsername(user.username);
    setUserRole(user.role);
  }, []);

  useEffect(() => {
    if (!clientId.trim()) {
      return;
    }

    let cancelled = false;

    void fetch(
      `${
        process.env.NEXT_PUBLIC_API_URL?.replace(
          /\/$/,
          "",
        ) || "http://localhost:18000"
      }/api/protection-status?client_id=${encodeURIComponent(
        clientId.trim(),
      )}`,
    )
      .then(async (response) => {
        const data = await response.json();
        if (!cancelled && response.ok) {
          setProtectionEnabled(
            Boolean(data.protection_enabled),
          );
        }
      })
      .catch(() => {
        // Keep default enabled.
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  async function submitMessage(promptOverride?: string) {
    const prompt = (promptOverride ?? input).trim();

    if (!prompt || sending || viewOnlyOwner) {
      return;
    }

    if (!clientId.trim() || !username.trim()) {
      setError("Please login first.");
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: prompt,
    };

    const withUser = [...messagesRef.current, userMessage];

    messagesRef.current = withUser;
    setMessages(withUser);
    setInput("");
    setError("");
    setSending(true);
    persistMessages(withUser);

    try {
      const data = await sendChatMessage(
        prompt,
        clientId.trim(),
        username.trim(),
      );

      if (typeof data.protection_enabled === "boolean") {
        setProtectionEnabled(data.protection_enabled);
      }

      const assistantMessage: ChatMessage = {
        id: createMessageId(),
        role: "assistant",
        content: getAssistantContent(data),
        status: data.shield_status || "UNKNOWN",
        riskScore: data.risk_score ?? 0,
        detectionLayer:
          data.detection_layer || "WRDN Security",
        detectionReason: data.detection_reason,
        detectionLog: data.detection_log,
      };

      const withAssistant = [...withUser, assistantMessage];

      messagesRef.current = withAssistant;
      setMessages(withAssistant);
      persistMessages(withAssistant);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Failed to connect to the chat server.";

      setError(message);

      const withError: ChatMessage[] = [
        ...withUser,
        {
          id: createMessageId(),
          role: "assistant",
          content:
            "I could not connect to the WRDN chat server. Please confirm that the FastAPI backend is running.",
          status: "ERROR",
          riskScore: 0,
          detectionLayer: "Connection Error",
        },
      ];

      messagesRef.current = withError;
      setMessages(withError);
      persistMessages(withError);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage();
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  function getStatusClass(status?: string) {
    const normalized = status?.toUpperCase();

    if (
      normalized === "BLOCKED" ||
      normalized === "ERROR"
    ) {
      return "blocked";
    }

    if (
      normalized === "REDACTED" ||
      normalized === "SANITIZED"
    ) {
      return "sanitized";
    }

    if (
      normalized === "BYPASSED" ||
      normalized === "UNPROTECTED"
    ) {
      return "bypassed";
    }

    return "allowed";
  }

  const historyLimit = isAdmin ? 12 : 5;

  return (
    <section className="chat-page">
      <header className="chat-header">
        <div>
          <h1>WRDN AI Assistant</h1>
          <p>
            {isAdmin
              ? "Admin view: your chats are private to you. You can also open employee chats from this client on the right (view only)."
              : "Employee view: your chats stay private to your account. Admins on your client can review them."}
          </p>
        </div>

        <div
          className={`chat-header-status${
            protectionEnabled ? "" : " protection-off"
          }`}
        >
          <span className="protection-dot" />
          {protectionEnabled
            ? "WRDN protection enabled"
            : "WRDN protection disabled (raw output)"}
        </div>
      </header>

      <div className="chat-body">
        <div className="chat-main">
          <div className="chat-content">
            {viewOnlyOwner ? (
              <p className="chat-error" style={{ margin: "0 0 12px" }}>
                Viewing {viewOnlyOwner}&apos;s chat
                (read-only). Start a New chat to ask your
                own questions.
              </p>
            ) : null}

            {messages.length === 0 ? (
              <div className="chat-welcome">
                <div className="welcome-logo">W</div>
                <h2>How can WRDN help you?</h2>
                <p>
                  Ask questions about your organization.
                  Every generated answer is checked before
                  it is displayed.
                </p>

                <div className="starter-grid">
                  {starterQuestions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() =>
                        void submitMessage(question)
                      }
                      disabled={
                        sending ||
                        !clientId.trim() ||
                        Boolean(viewOnlyOwner)
                      }
                    >
                      <span>{question}</span>
                      <strong>→</strong>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="messages-container">
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={`chat-message ${message.role}`}
                  >
                    <div className="message-avatar">
                      {message.role === "user" ? "U" : "W"}
                    </div>

                    <div className="message-body">
                      <div className="message-heading">
                        <strong>
                          {message.role === "user"
                            ? viewOnlyOwner || "You"
                            : "WRDN Assistant"}
                        </strong>

                        {message.role === "assistant" &&
                          message.status && (
                            <span
                              className={`shield-badge ${getStatusClass(
                                message.status,
                              )}`}
                            >
                              {message.status}
                            </span>
                          )}
                      </div>

                      <p className="message-text">
                        {message.content}
                      </p>

                      {message.role === "assistant" && (
                        <div className="security-details">
                          <div>
                            <span>Risk Score</span>
                            <strong>
                              {message.riskScore ?? 0}/100
                            </strong>
                          </div>
                          <div>
                            <span>Detection Layer</span>
                            <strong>
                              {message.detectionLayer ||
                                "WRDN Security"}
                            </strong>
                          </div>
                          {message.detectionReason && (
                            <div>
                              <span>Detection Reason</span>
                              <strong>
                                {message.detectionReason}
                              </strong>
                            </div>
                          )}
                          {message.detectionLog?.length ? (
                            <div className="chat-layer-log">
                              <span>Layer log</span>
                              <ol>
                                {message.detectionLog.map(
                                  (layer) => (
                                    <li
                                      key={`${layer.step}-${layer.name}`}
                                    >
                                      {layer.step}.{" "}
                                      {layer.name}:{" "}
                                      {layer.status}
                                      {layer.detail
                                        ? ` — ${layer.detail}`
                                        : ""}
                                    </li>
                                  ),
                                )}
                              </ol>
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </article>
                ))}

                {sending && (
                  <article className="chat-message assistant">
                    <div className="message-avatar">W</div>
                    <div className="message-body">
                      <p className="message-text">
                        Thinking…
                      </p>
                    </div>
                  </article>
                )}

                <div ref={messageEndRef} />
              </div>
            )}
          </div>

          {error && <p className="chat-error">{error}</p>}

          <div className="chat-input-area">
            <form
              className="chat-form"
              onSubmit={handleSubmit}
            >
              <textarea
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                onKeyDown={handleKeyDown}
                placeholder={
                  viewOnlyOwner
                    ? "Read-only employee chat — click New to chat"
                    : "Ask WRDN a question…"
                }
                rows={1}
                disabled={
                  sending ||
                  !clientId.trim() ||
                  Boolean(viewOnlyOwner)
                }
              />
              <button
                type="submit"
                disabled={
                  sending ||
                  !input.trim() ||
                  !clientId.trim() ||
                  Boolean(viewOnlyOwner)
                }
                aria-label="Send message"
              >
                →
              </button>
            </form>
            <p className="chat-disclaimer">
              WRDN checks every answer before it is shown.
            </p>
          </div>
        </div>

        <aside className="chat-history-panel">
          <div className="chat-history-dock">
            <div className="chat-history-header">
              <p className="chat-history-label">
                {isAdmin
                  ? "My + team chats"
                  : "Your recent chats"}
              </p>
              <button
                type="button"
                className="chat-history-new"
                onClick={() => onNewChat?.()}
              >
                New
              </button>
            </div>

            <div className="chat-history-list">
              {recentChats.length === 0 ? (
                <p className="chat-history-empty">
                  {isAdmin
                    ? "Your chats and employee chats for this client appear here."
                    : "Send a message, then start a new chat to keep it here."}
                </p>
              ) : (
                recentChats
                  .slice(0, historyLimit)
                  .map((chat) => (
                    <button
                      key={chat.id}
                      type="button"
                      className={`chat-history-item${
                        activeChatId === chat.id
                          ? " active"
                          : ""
                      }`}
                      title={chat.title}
                      onClick={() =>
                        onSelectChat?.(chat.id)
                      }
                    >
                      <span className="chat-history-item-title">
                        {chat.title}
                      </span>
                    </button>
                  ))
              )}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
