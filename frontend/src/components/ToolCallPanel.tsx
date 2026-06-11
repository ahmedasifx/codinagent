import { useState } from "react";
import { ToolCallBlock, ToolResultBlock } from "../types";

interface Props {
  toolCalls: ToolCallBlock[];
  toolResults: ToolResultBlock[];
}

const TOOL_ICONS: Record<string, string> = {
  execute_python: "⚡",
  install_package: "📦",
  write_file: "📝",
  read_file: "📖",
  list_files: "🗂️",
  run_command: "💻",
  start_server: "🌐",
  stop_server: "🛑",
};

export function ToolCallPanel({ toolCalls, toolResults }: Props) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!toolCalls.length) return null;

  return (
    <div className="tool-calls">
      {toolCalls.map((tc, i) => {
        const result = toolResults[i];
        const isOpen = openIndex === i;
        const icon = TOOL_ICONS[tc.name] ?? "🔧";

        // Check if the result contains a base64 chart
        const chartMatch = result?.content?.match(
          /CHART\[\d+\]: (data:image\/png;base64,[A-Za-z0-9+/=]+)/
        );
        const previewMatch = result?.content?.match(/PREVIEW_URL: (https:\/\/\S+)/);

        return (
          <div key={i} className={`tool-block ${result ? "done" : "running"}`}>
            <button
              className="tool-header"
              onClick={() => setOpenIndex(isOpen ? null : i)}
            >
              <span className="tool-icon">{icon}</span>
              <span className="tool-name">{tc.name}</span>
              {result ? (
                <span className="tool-status done">✓</span>
              ) : (
                <span className="tool-status running">
                  <span className="spinner" />
                </span>
              )}
              <span className="tool-chevron">{isOpen ? "▲" : "▼"}</span>
            </button>

            {isOpen && (
              <div className="tool-body">
                <div className="tool-section">
                  <span className="tool-label">INPUT</span>
                  <pre className="tool-code">
                    {tc.name === "execute_python" || tc.name === "write_file"
                      ? (tc.args.code as string) ||
                        (tc.args.content as string) ||
                        JSON.stringify(tc.args, null, 2)
                      : JSON.stringify(tc.args, null, 2)}
                  </pre>
                </div>

                {result && (
                  <div className="tool-section">
                    <span className="tool-label">OUTPUT</span>
                    {chartMatch ? (
                      <img
                        src={chartMatch[1]}
                        alt="Generated chart"
                        className="tool-chart"
                      />
                    ) : (
                      <pre className="tool-code output">
                        {result.content.replace(
                          /CHART\[\d+\]: data:image\/png;base64,[A-Za-z0-9+/=]+/g,
                          "[chart rendered above]"
                        )}
                      </pre>
                    )}
                    {previewMatch && (
                      <a
                        className="tool-preview-link"
                        href={previewMatch[1]}
                        target="_blank"
                        rel="noreferrer"
                      >
                        🌐 {previewMatch[1]}
                      </a>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
