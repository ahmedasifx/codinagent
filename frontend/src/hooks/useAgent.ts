import { useState, useCallback, useRef } from "react";
import {
  ChatMessage,
  AgentEvent,
  ToolCallBlock,
  ToolResultBlock,
  Workflow,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function makeId() {
  return Math.random().toString(36).slice(2);
}

export function useAgent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (isRunning) return;
      setError(null);

      // Add user message
      const userMsg: ChatMessage = { id: makeId(), role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);

      // Placeholder for streaming assistant message
      const assistantId = makeId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        toolResults: [],
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      setIsRunning(true);
      abortRef.current = new AbortController();

      try {
        // Build history (exclude the streaming placeholder)
        const history = messages
          .filter((m) => !m.isStreaming)
          .map((m) => ({ role: m.role, content: m.content }));

        const response = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, history }),
          signal: abortRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            const raw = line.slice(5).trim();
            if (!raw) continue;

            let event: AgentEvent;
            try {
              event = JSON.parse(raw);
            } catch {
              continue;
            }

            // Session-level events (not tied to the message)
            if (event.type === "preview") {
              setPreviewUrl(event.url);
              continue;
            }
            if (event.type === "workflow") {
              setWorkflow(event.workflow);
              continue;
            }

            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m;

                switch (event.type) {
                  case "token":
                    return { ...m, content: m.content + event.content };

                  case "tool_call": {
                    const tc: ToolCallBlock = { name: event.name, args: event.args };
                    return { ...m, toolCalls: [...(m.toolCalls ?? []), tc] };
                  }

                  case "tool_result": {
                    const tr: ToolResultBlock = { content: event.content };
                    return { ...m, toolResults: [...(m.toolResults ?? []), tr] };
                  }

                  case "done":
                    return { ...m, isStreaming: false };

                  case "error":
                    return {
                      ...m,
                      content: m.content + `\n\n⚠️ Error: ${event.content}`,
                      isStreaming: false,
                    };

                  default:
                    return m;
                }
              })
            );
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `⚠️ ${msg}`, isStreaming: false }
              : m
          )
        );
      } finally {
        setIsRunning(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m
          )
        );
      }
    },
    [messages, isRunning]
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    setIsRunning(false);
  }, []);

  const clearChat = useCallback(async () => {
    setMessages([]);
    setError(null);
    setPreviewUrl(null);
    setWorkflow(null);
    // Also reset the E2B sandbox
    await fetch(`${API_BASE}/sandbox`, { method: "DELETE" }).catch(() => {});
  }, []);

  return {
    messages,
    isRunning,
    error,
    previewUrl,
    workflow,
    sendMessage,
    stopGeneration,
    clearChat,
    closePreview: () => setPreviewUrl(null),
  };
}
