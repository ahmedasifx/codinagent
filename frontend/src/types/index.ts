export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  toolCalls?: ToolCallBlock[];
  toolResults?: ToolResultBlock[];
  isStreaming?: boolean;
}

export interface ToolCallBlock {
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResultBlock {
  content: string;
}

export type Workflow = "landing_page" | "fullstack" | "general";

// SSE event payloads from the backend
export type AgentEvent =
  | { type: "token"; content: string }
  | { type: "workflow"; workflow: Workflow }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; content: string }
  | { type: "preview"; url: string }
  | { type: "done" }
  | { type: "error"; content: string };
