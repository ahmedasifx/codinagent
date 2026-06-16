import { Artifact } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface Props {
  artifacts: Artifact[];
  progress?: { label: string; pct?: number };
}

function fullUrl(url: string) {
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

export function ArtifactPanel({ artifacts, progress }: Props) {
  if (!artifacts.length && !progress) return null;

  return (
    <div className="artifact-panel">
      {progress && (
        <div className="artifact-progress">
          <span>{progress.label}</span>
          {progress.pct != null && (
            <div className="artifact-progress-bar">
              <div style={{ width: `${Math.round(progress.pct)}%` }} />
            </div>
          )}
        </div>
      )}

      {artifacts.map((art) => {
        const href = fullUrl(art.url);
        return (
          <div key={art.artifact_id} className="artifact">
            {art.kind === "video" && (
              <video src={href} controls className="artifact-media" />
            )}
            {art.kind === "image" && (
              <img src={href} alt="artifact" className="artifact-media" />
            )}
            {art.kind === "audio" && <audio src={href} controls />}
            <a className="artifact-download" href={href} download>
              ↓ Download {art.kind} ({art.mime})
            </a>
          </div>
        );
      })}
    </div>
  );
}
