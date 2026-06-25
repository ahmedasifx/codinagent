import { useState, useRef, useEffect, useCallback, KeyboardEvent } from "react";
import { useAgent } from "./hooks/useAgent";
import { MessageBubble } from "./components/MessageBubble";
import { PreviewPanel } from "./components/PreviewPanel";
import { AgentBuilder } from "./components/AgentBuilder";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const EXAMPLES = [
  "Build a landing page for a specialty coffee shop with a hero, menu and contact section",
  "Build a FastAPI todo API with a small frontend to add and complete todos",
  "Install pandas and matplotlib, then create a bar chart of random sales data",
  "Write a merge sort implementation and test it with a random list",
];

interface AgentInfo {
  slug: string;
  name: string;
  planning?: "off" | "auto" | "approve";
}

export default function App() {
  const {
    messages,
    isRunning,
    error,
    previewUrl,
    skill,
    agentSlug,
    setAgentSlug,
    planningMode,
    setPlanningMode,
    sendMessage,
    approvePlan,
    rejectPlan,
    stopGeneration,
    clearChat,
    submitFeedback,
    closePreview,
  } = useAgent();
  const [input, setInput] = useState("");
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [showBuilder, setShowBuilder] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load available agents for the picker
  const loadAgents = useCallback(() => {
    fetch(`${API_BASE}/agents`)
      .then((r) => r.json())
      .then((data: AgentInfo[]) => setAgents(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isRunning) return;
    setInput("");
    sendMessage(text);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`app ${previewUrl ? "has-preview" : ""}`}>
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-bracket">[</span>
            <span className="logo-text">coding agent</span>
            <span className="logo-bracket">]</span>
          </div>
          <div className="stack-badges">
            <span className="badge">E2B</span>
            <span className="badge">LangGraph</span>
            <span className="badge">OpenRouter</span>
            {skill && <span className="badge workflow-badge">{skill}</span>}
          </div>
        </div>
        <div className="header-right">
          <select
            className="agent-select"
            value={agentSlug ?? ""}
            onChange={(e) => {
              const slug = e.target.value || null;
              setAgentSlug(slug);
              const a = agents.find((x) => x.slug === slug);
              if (a?.planning) setPlanningMode(a.planning);
            }}
            disabled={isRunning}
            title="Select agent"
          >
            <option value="">Default (coding agent)</option>
            {agents.map((a) => (
              <option key={a.slug} value={a.slug}>
                {a.name}
              </option>
            ))}
          </select>
          <select
            className="agent-select"
            value={planningMode}
            onChange={(e) => setPlanningMode(e.target.value as typeof planningMode)}
            disabled={isRunning}
            title="Planning mode"
          >
            <option value="off">Plan: off</option>
            <option value="auto">Plan: auto</option>
            <option value="approve">Plan: approve</option>
          </select>
          <button
            className="clear-btn"
            onClick={() => setShowBuilder(true)}
            disabled={isRunning}
            title="Create a custom agent"
          >
            ＋ New
          </button>
          <button
            className="clear-btn"
            onClick={clearChat}
            disabled={isRunning || messages.length === 0}
            title="Clear chat & reset sandbox"
          >
            Reset
          </button>
        </div>
      </header>

      <div className={`content-row ${previewUrl ? "split" : ""}`}>
        <div className="chat-col">
          {/* Messages */}
          <main className="messages-area">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-title">Ask me to write and run code</div>
            <div className="empty-grid">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  className="example-btn"
                  onClick={() => sendMessage(ex)}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onApprove={approvePlan}
            onReject={rejectPlan}
            onFeedback={submitFeedback}
          />
        ))}

        {error && (
          <div className="error-bar">⚠️ {error}</div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* Input */}
      <footer className="input-area">
        <div className="input-row">
          <textarea
            ref={textareaRef}
            className="input-box"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me to write or run code… (Shift+Enter for newline)"
            rows={1}
            disabled={isRunning}
          />
          <button
            className={`send-btn ${isRunning ? "stop" : ""}`}
            onClick={isRunning ? stopGeneration : handleSend}
            disabled={!isRunning && !input.trim()}
          >
            {isRunning ? "■ Stop" : "Send ↵"}
          </button>
        </div>
            <div className="input-hint">
              Code runs in a secure E2B sandbox · variables persist within session
            </div>
          </footer>
        </div>

        {previewUrl && <PreviewPanel url={previewUrl} onClose={closePreview} />}
      </div>

      {showBuilder && (
        <AgentBuilder
          onClose={() => setShowBuilder(false)}
          onCreated={(slug) => {
            setShowBuilder(false);
            loadAgents();
            setAgentSlug(slug);
          }}
        />
      )}
    </div>
  );
}
