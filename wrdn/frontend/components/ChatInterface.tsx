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

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  riskScore?: number;
  detectionLayer?: string;
  detectionReason?: string;
}

interface ChatInterfaceProps {
  resetSignal: number;
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
}: ChatInterfaceProps) {
  const [messages, setMessages] =
    useState<ChatMessage[]>([]);

  const [input, setInput] = useState("");
  const [sending, setSending] =
    useState(false);

  const [error, setError] = useState("");

  const messageEndRef =
    useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages([]);
    setInput("");
    setError("");
  }, [resetSignal]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, sending]);

  async function submitMessage(
    promptOverride?: string,
  ) {
    const prompt = (
      promptOverride ?? input
    ).trim();

    if (!prompt || sending) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: prompt,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setInput("");
    setError("");
    setSending(true);

    try {
      const data =
        await sendChatMessage(prompt);

      const assistantMessage: ChatMessage = {
        id: createMessageId(),
        role: "assistant",
        content: getAssistantContent(data),
        status:
          data.shield_status ||
          "UNKNOWN",
        riskScore:
          data.risk_score ?? 0,
        detectionLayer:
          data.detection_layer ||
          "WRDN Security",
        detectionReason:
          data.detection_reason,
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Failed to connect to the chat server.";

      setError(message);

      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: "assistant",
          content:
            "I could not connect to the WRDN chat server. Please confirm that the FastAPI backend is running.",
          status: "ERROR",
          riskScore: 0,
          detectionLayer:
            "Connection Error",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    submitMessage();
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      submitMessage();
    }
  }

  function getStatusClass(
    status?: string,
  ) {
    const normalized =
      status?.toUpperCase();

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
            Secure company intelligence
            protected by WRDN.
          </p>
        </div>

        <div className="chat-header-status">
          <span className="protection-dot" />
          WRDN protection enabled
        </div>
      </header>

      <div className="chat-content">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <div className="welcome-logo">
              W
            </div>

            <h2>
              How can WRDN help you?
            </h2>

            <p>
              Ask questions about your
              organization. Every generated
              answer is checked before it is
              displayed.
            </p>

            <div className="starter-grid">
              {starterQuestions.map(
                (question) => (
                  <button
                    key={question}
                    onClick={() =>
                      submitMessage(question)
                    }
                    disabled={sending}
                  >
                    <span>
                      {question}
                    </span>

                    <strong>→</strong>
                  </button>
                ),
              )}
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

                    {message.role ===
                      "assistant" &&
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

                  {message.role ===
                    "assistant" && (
                    <div className="security-details">
                      <div>
                        <span>
                          Risk Score
                        </span>

                        <strong>
                          {message.riskScore ??
                            0}
                          /100
                        </strong>
                      </div>

                      <div>
                        <span>
                          Detection Layer
                        </span>

                        <strong>
                          {message.detectionLayer}
                        </strong>
                      </div>

                      {message.detectionReason && (
                        <div className="reason-row">
                          <span>
                            Detection Reason
                          </span>

                          <strong>
                            {
                              message.detectionReason
                            }
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
                <div className="message-avatar">
                  W
                </div>

                <div className="message-body">
                  <div className="message-heading">
                    <strong>
                      WRDN Assistant
                    </strong>
                  </div>

                  <div className="typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>

                  <p className="checking-text">
                    Generating and checking the
                    response...
                  </p>
                </div>
              </article>
            )}

            <div ref={messageEndRef} />
          </div>
        )}
      </div>

      <div className="chat-input-area">
        {error && (
          <p className="chat-error">
            {error}
          </p>
        )}

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
            placeholder="Ask a question about your organization..."
            rows={1}
            disabled={sending}
          />

          <button
            type="submit"
            disabled={
              sending || !input.trim()
            }
            aria-label="Send message"
          >
            {sending ? "..." : "➤"}
          </button>
        </form>

        <p className="chat-disclaimer">
          WRDN can block or sanitize responses
          containing sensitive company data.
        </p>
      </div>
    </section>
  );
}