import { useState, useCallback, useRef } from "react";
import {
  ChatMessage,
  AgentEvent,
  ToolCallBlock,
  ToolResultBlock,
  Artifact,
  PlanningMode,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function makeId() {
  return Math.random().toString(36).slice(2);
}

interface StreamBody {
  message: string;
  history: { role: string; content: string }[];
  planning?: PlanningMode | "execute";
  approved_plan?: string;
}

export function useAgent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [skill, setSkill] = useState<string | null>(null);
  const [agentSlug, setAgentSlug] = useState<string | null>(null);
  const [planningMode, setPlanningMode] = useState<PlanningMode>("off");
  const abortRef = useRef<AbortController | null>(null);

  // Shared SSE consumer: POSTs `body` and folds events into message `assistantId`.
  const runStream = useCallback(
    async (assistantId: string, body: StreamBody) => {
      setIsRunning(true);
      setError(null);
      abortRef.current = new AbortController();
      try {
        const url = agentSlug
          ? `${API_BASE}/agents/${agentSlug}/chat/stream`
          : `${API_BASE}/chat/stream`;

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: abortRef.current.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

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

            if (event.type === "preview") {
              setPreviewUrl(event.url);
              continue;
            }
            if (event.type === "skill_selected") {
              setSkill(event.skill);
              continue;
            }
            if (event.type === "agent_selected") continue;

            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m;
                switch (event.type) {
                  case "token":
                    return { ...m, content: m.content + event.content };
                  case "plan":
                    return { ...m, plan: event.plan };
                  case "awaiting_approval":
                    return { ...m, awaitingApproval: true };
                  case "tool_call": {
                    const tc: ToolCallBlock = { name: event.name, args: event.args };
                    return { ...m, toolCalls: [...(m.toolCalls ?? []), tc] };
                  }
                  case "tool_result": {
                    const tr: ToolResultBlock = { content: event.content };
                    return { ...m, toolResults: [...(m.toolResults ?? []), tr] };
                  }
                  case "progress":
                    return { ...m, progress: { label: event.label, pct: event.pct } };
                  case "artifact": {
                    const art: Artifact = {
                      artifact_id: event.artifact_id, kind: event.kind,
                      url: event.url, mime: event.mime,
                    };
                    return { ...m, artifacts: [...(m.artifacts ?? []), art], progress: undefined };
                  }
                  case "done":
                    return { ...m, isStreaming: false, progress: undefined };
                  case "error":
                    return {
                      ...m, content: m.content + `\n\n⚠️ Error: ${event.content}`,
                      isStreaming: false, progress: undefined,
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
            m.id === assistantId ? { ...m, content: m.content + `\n\n⚠️ ${msg}`, isStreaming: false } : m
          )
        );
      } finally {
        setIsRunning(false);
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m))
        );
      }
    },
    [agentSlug]
  );

  const sendMessage = useCallback(
    async (text: string) => {
      if (isRunning) return;
      const history = messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({ role: m.role, content: m.content }));

      const userMsg: ChatMessage = { id: makeId(), role: "user", content: text };
      const assistantId = makeId();
      const assistantMsg: ChatMessage = {
        id: assistantId, role: "assistant", content: "",
        toolCalls: [], toolResults: [], artifacts: [],
        userPrompt: text, isStreaming: true,
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      await runStream(assistantId, { message: text, history, planning: planningMode });
    },
    [messages, isRunning, planningMode, runStream]
  );

  // Approve a paused plan → execute phase (streams into the same assistant message).
  const approvePlan = useCallback(
    async (assistantId: string, editedPlan: string) => {
      if (isRunning) return;
      let prompt = "";
      let history: { role: string; content: string }[] = [];
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === assistantId);
        if (idx > 0) {
          prompt = prev[idx].userPrompt ?? prev[idx - 1]?.content ?? "";
          history = prev.slice(0, idx - 1)
            .filter((m) => !m.isStreaming)
            .map((m) => ({ role: m.role, content: m.content }));
        }
        return prev.map((m) =>
          m.id === assistantId
            ? { ...m, awaitingApproval: false, plan: editedPlan, isStreaming: true }
            : m
        );
      });
      await runStream(assistantId, {
        message: prompt, history, planning: "execute", approved_plan: editedPlan,
      });
    },
    [isRunning, runStream]
  );

  const rejectPlan = useCallback((assistantId: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === assistantId
          ? { ...m, awaitingApproval: false, isStreaming: false,
              content: m.content + "\n\n_Plan rejected._" }
          : m
      )
    );
  }, []);

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
    setIsRunning(false);
  }, []);

  const clearChat = useCallback(async () => {
    setMessages([]);
    setError(null);
    setPreviewUrl(null);
    setSkill(null);
    await fetch(`${API_BASE}/sandbox`, { method: "DELETE" }).catch(() => {});
  }, []);

  return {
    messages, isRunning, error, previewUrl, skill,
    agentSlug, setAgentSlug, planningMode, setPlanningMode,
    sendMessage, approvePlan, rejectPlan, stopGeneration, clearChat,
    closePreview: () => setPreviewUrl(null),
  };
}
