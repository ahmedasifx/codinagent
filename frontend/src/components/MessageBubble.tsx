import { ChatMessage } from "../types";
import { ToolCallPanel } from "./ToolCallPanel";
import { ArtifactPanel } from "./ArtifactPanel";
import { PlanPanel } from "./PlanPanel";

interface Props {
  message: ChatMessage;
  onApprove?: (id: string, editedPlan: string) => void;
  onReject?: (id: string) => void;
  onFeedback?: (id: string, traceId: string, value: "up" | "down") => void;
}

// Minimal markdown-ish rendering: fenced code blocks + inline `code`
function renderContent(text: string) {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  const fenceRe = /```(\w*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = fenceRe.exec(text)) !== null) {
    // Text before the fence
    const before = text.slice(lastIndex, match.index);
    if (before) parts.push(<span key={key++}>{renderInline(before)}</span>);

    parts.push(
      <div key={key++} className="code-block">
        {match[1] && <span className="code-lang">{match[1]}</span>}
        <pre>
          <code>{match[2]}</code>
        </pre>
      </div>
    );
    lastIndex = match.index + match[0].length;
  }

  const tail = text.slice(lastIndex);
  if (tail) parts.push(<span key={key++}>{renderInline(tail)}</span>);

  return parts;
}

function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /`([^`]+)`/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<span key={key++}>{text.slice(last, m.index)}</span>);
    parts.push(<code key={key++} className="inline-code">{m[1]}</code>);
    last = m.index + m[0].length;
  }

  if (last < text.length) parts.push(<span key={key++}>{text.slice(last)}</span>);
  return parts;
}

export function MessageBubble({ message, onApprove, onReject, onFeedback }: Props) {
  const isUser = message.role === "user";
  const showFeedback = !isUser && !message.isStreaming && !!message.traceId && !!onFeedback;

  return (
    <div className={`message ${isUser ? "user" : "assistant"}`}>
      <div className="message-avatar">{isUser ? "You" : "AI"}</div>
      <div className="message-body">
        {/* Plan (auto or awaiting approval) shown first */}
        {!isUser && message.plan && (
          <PlanPanel
            plan={message.plan}
            awaitingApproval={message.awaitingApproval}
            onApprove={(edited) => onApprove?.(message.id, edited)}
            onReject={() => onReject?.(message.id)}
          />
        )}

        {/* Tool calls before text for assistant */}
        {!isUser && (
          <ToolCallPanel
            toolCalls={message.toolCalls ?? []}
            toolResults={message.toolResults ?? []}
          />
        )}

        {message.content && (
          <div className={`message-text ${isUser ? "user-text" : "assistant-text"}`}>
            {isUser ? message.content : renderContent(message.content)}
            {message.isStreaming && <span className="cursor" />}
          </div>
        )}

        {!message.content && message.isStreaming && (
          <div className="message-text assistant-text thinking">
            <span className="dot-1">•</span>
            <span className="dot-2">•</span>
            <span className="dot-3">•</span>
          </div>
        )}

        {!isUser && (
          <ArtifactPanel
            artifacts={message.artifacts ?? []}
            progress={message.progress}
          />
        )}

        {showFeedback && (
          <div className="feedback-row">
            <button
              className={`feedback-btn ${message.feedback === "up" ? "active" : ""}`}
              title="Good response"
              onClick={() => onFeedback!(message.id, message.traceId!, "up")}
            >
              👍
            </button>
            <button
              className={`feedback-btn ${message.feedback === "down" ? "active" : ""}`}
              title="Bad response"
              onClick={() => onFeedback!(message.id, message.traceId!, "down")}
            >
              👎
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
