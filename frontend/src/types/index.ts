export type Role = "user" | "assistant";

export type PlanningMode = "off" | "auto" | "approve";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  toolCalls?: ToolCallBlock[];
  toolResults?: ToolResultBlock[];
  artifacts?: Artifact[];
  progress?: ProgressBlock;
  plan?: string;
  awaitingApproval?: boolean;
  userPrompt?: string; // the originating user message (for the approve→execute request)
  isStreaming?: boolean;
  traceId?: string; // Langfuse trace id for this run (enables feedback scoring)
  feedback?: "up" | "down"; // user feedback already submitted for this message
}

export interface ToolCallBlock {
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResultBlock {
  content: string;
}

export interface Artifact {
  artifact_id: string;
  kind: "image" | "pdf" | "video" | "html" | "audio" | "csv";
  url: string;
  mime: string;
}

export interface ProgressBlock {
  label: string;
  pct?: number;
}

// SSE event payloads from the backend — must mirror app/engine/runner.py
export type AgentEvent =
  | { type: "token"; content: string }
  | { type: "trace"; trace_id: string }
  | { type: "agent_selected"; agent: string }
  | { type: "skill_selected"; skill: string }
  | { type: "plan"; plan: string }
  | { type: "awaiting_approval" }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; content: string }
  | { type: "progress"; label: string; pct?: number }
  | { type: "artifact"; artifact_id: string; kind: Artifact["kind"]; url: string; mime: string }
  | { type: "preview"; url: string }
  | { type: "done" }
  | { type: "error"; content: string };
