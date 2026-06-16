export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  toolCalls?: ToolCallBlock[];
  toolResults?: ToolResultBlock[];
  artifacts?: Artifact[];
  progress?: ProgressBlock;
  isStreaming?: boolean;
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
  kind: "image" | "pdf" | "video" | "html" | "audio";
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
  | { type: "agent_selected"; agent: string }
  | { type: "skill_selected"; skill: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; content: string }
  | { type: "progress"; label: string; pct?: number }
  | { type: "artifact"; artifact_id: string; kind: Artifact["kind"]; url: string; mime: string }
  | { type: "preview"; url: string }
  | { type: "done" }
  | { type: "error"; content: string };
