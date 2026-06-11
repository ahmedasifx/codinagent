import { useState } from "react";

interface Props {
  url: string;
  onClose: () => void;
}

export function PreviewPanel({ url, onClose }: Props) {
  // Cross-origin iframes can't be reloaded directly — remount via key
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <aside className="preview-panel">
      <div className="preview-header">
        <span className="preview-dot" />
        <span className="preview-url" title={url}>
          {url.replace(/^https:\/\//, "")}
        </span>
        <button
          className="preview-btn"
          onClick={() => setReloadKey((k) => k + 1)}
          title="Refresh preview"
        >
          ↻
        </button>
        <a
          className="preview-btn"
          href={url}
          target="_blank"
          rel="noreferrer"
          title="Open in new tab"
        >
          ↗
        </a>
        <button className="preview-btn" onClick={onClose} title="Close preview">
          ✕
        </button>
      </div>
      <iframe
        key={reloadKey}
        className="preview-frame"
        src={url}
        title="Live preview"
        sandbox="allow-scripts allow-same-origin allow-forms"
      />
    </aside>
  );
}
