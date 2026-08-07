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
  loadChatSessions,
  upsertChatSession,
  type ChatSession,
  type StoredChatMessage,
} from "@/lib/chatHistory";

interface ChatMessage extends StoredChatMessage {}

interface ChatInterfaceProps {
  resetSignal: number;
  loadChatId?: string | null;
  onHistoryChange?: (sessions: ChatSession[]) => void;
  onActiveSessionChange?: (sessionId: string | null) => void;
  recentChats?: Array<{
    id: string;
    title: string;
  }>;
  activeChatId?: string | null;
  onSelectChat?: (chatId: string) => void;
  onNewChat?: () => void;
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

function getAssistantContent(
  data: ChatApiResponse,
) {
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
}: ChatInterfaceProps) {
  const [messages, setMessages] =
    useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [clientId, setClientId] = useState("");
  const [sessionId, setSessionId] = useState(
    () => createChatSessionId(),
  );

  const messageEndRef =
    useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  const sessionIdRef = useRef(sessionId);
  const lastHandledReset = useRef(resetSignal);
  const lastLoadedChatId = useRef<string | null>(
    null,
  );

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    const sessions = loadChatSessions();
    onHistoryChange?.(sessions);
  }, [onHistoryChange]);

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
  ) {
    if (nextMessages.length === 0) {
      publishHistory(loadChatSessions(), id);
      return loadChatSessions();
    }

    const session: ChatSession = {
      id,
      title: getChatSessionTitle(nextMessages),
      updatedAt: new Date().toISOString(),
      messages: nextMessages,
    };

    const sessions = upsertChatSession(session);
    publishHistory(sessions, id);
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
    onActiveSessionChange?.(null);
  }

  // New Chat button
  useEffect(() => {
    if (resetSignal === lastHandledReset.current) {
      return;
    }

    lastHandledReset.current = resetSignal;
    persistMessages(messagesRef.current);
    startBlankChat();
    publishHistory(loadChatSessions(), null);
  }, [resetSignal]);

  // Open a recent chat from sidebar
  useEffect(() => {
    if (!loadChatId) {
      lastLoadedChatId.current = null;
      return;
    }

    if (
      sessionIdRef.current !== loadChatId &&
      messagesRef.current.length > 0
    ) {
      persistMessages(
        messagesRef.current,
        sessionIdRef.current,
      );
    }

    const session = getChatSessionById(loadChatId);

    if (!session) {
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
    onActiveSessionChange?.(session.id);
  }, [loadChatId]);

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
      return;
    }

    setClientId(user.client_id);
  }, []);

  async function submitMessage(
    promptOverride?: string,
  ) {
    const prompt = (
      promptOverride ?? input
    ).trim();

    if (!prompt || sending) {
      return;
    }

    if (!clientId.trim()) {
      setError("Please login first.");
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: prompt,
    };

    const withUser = [
      ...messagesRef.current,
      userMessage,
    ];

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
      );

      const assistantMessage: ChatMessage = {
        id: createMessageId(),
        role: "assistant",
        content: getAssistantContent(data),
        status: data.shield_status || "UNKNOWN",
        riskScore: data.risk_score ?? 0,
        detectionLayer:
          data.detection_layer || "WRDN Security",
        detectionReason: data.detection_reason,
      };

      const withAssistant = [
        ...withUser,
        assistantMessage,
      ];

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

  function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
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

    return "allowed";
  }

  return (
    <section className="chat-page">
      <header className="chat-header">
        <div>
          <h1>WRDN AI Assistant</h1>
          <p>
            Secure company intelligence protected by
            WRDN. Your last 5 chats are kept on the
            right.
          </p>
        </div>

        <div className="chat-header-status">
          <span className="protection-dot" />
          WRDN protection enabled
        </div>
      </header>

      <div className="chat-body">
        <div className="chat-content">
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
                      sending || !clientId.trim()
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
                    {message.role === "user"
                      ? "U"
                      : "W"}
                  </div>

                  <div className="message-body">
                    <div className="message-heading">
                      <strong>
                        {message.role === "user"
                          ? "You"
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

        <aside className="chat-history-panel">
          <div className="chat-history-header">
            <p className="chat-history-label">
              Recent chats
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
                Send a message, then start a new chat to
                keep it here.
              </p>
            ) : (
              recentChats.slice(0, 5).map((chat) => (
                <button
                  key={chat.id}
                  type="button"
                  className={`chat-history-item${
                    activeChatId === chat.id
                      ? " active"
                      : ""
                  }`}
                  title={chat.title}
                  onClick={() => onSelectChat?.(chat.id)}
                >
                  {chat.title}
                </button>
              ))
            )}
          </div>
        </aside>
      </div>

      {error && (
        <p className="chat-error">{error}</p>
      )}

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
            placeholder="Ask WRDN a question…"
            rows={1}
            disabled={sending || !clientId.trim()}
          />
          <button
            type="submit"
            disabled={
              sending ||
              !input.trim() ||
              !clientId.trim()
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
    </section>
  );
}
