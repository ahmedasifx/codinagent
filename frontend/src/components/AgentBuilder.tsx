import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface Item {
  slug: string;
  name?: string;
  is_core?: boolean;
}

interface Props {
  onClose: () => void;
  onCreated: (slug: string) => void;
}

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

export function AgentBuilder({ onClose, onCreated }: Props) {
  const [skills, setSkills] = useState<Item[]>([]);
  const [tools, setTools] = useState<Item[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [personality, setPersonality] = useState("");
  const [selSkills, setSelSkills] = useState<string[]>([]);
  const [selTools, setSelTools] = useState<string[]>([]);
  const [planning, setPlanning] = useState<"off" | "auto" | "approve">("off");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/skills`).then((r) => r.json()).then(setSkills).catch(() => {});
    fetch(`${API_BASE}/tools`).then((r) => r.json()).then(setTools).catch(() => {});
  }, []);

  const toggle = (arr: string[], set: (v: string[]) => void, slug: string) =>
    set(arr.includes(slug) ? arr.filter((x) => x !== slug) : [...arr, slug]);

  const submit = async () => {
    setErr(null);
    if (!name.trim()) return setErr("Name is required");
    setBusy(true);
    try {
      const slug = slugify(name);
      const res = await fetch(`${API_BASE}/agents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug, name, description, system_prompt: systemPrompt, personality,
          skills: selSkills, tools: selTools, config: { planning },
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      onCreated(slug);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="builder-overlay" onClick={onClose}>
      <div className="builder" onClick={(e) => e.stopPropagation()}>
        <div className="builder-head">
          <h2>Create custom agent</h2>
          <button className="builder-x" onClick={onClose}>×</button>
        </div>

        <label className="builder-label">Name</label>
        <input className="builder-input" value={name} onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Tweet Writer" />
        {name && <div className="builder-hint">slug: {slugify(name)}</div>}

        <label className="builder-label">Description</label>
        <input className="builder-input" value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this agent do?" />

        <label className="builder-label">System prompt</label>
        <textarea className="builder-textarea" value={systemPrompt} rows={4}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="You are an expert at…" />

        <label className="builder-label">Personality (optional)</label>
        <input className="builder-input" value={personality} onChange={(e) => setPersonality(e.target.value)}
          placeholder="e.g. concise and witty" />

        <label className="builder-label">Skills ({selSkills.length})</label>
        <div className="builder-chips">
          {skills.map((s) => (
            <button key={s.slug} type="button"
              className={`chip ${selSkills.includes(s.slug) ? "chip-on" : ""}`}
              onClick={() => toggle(selSkills, setSelSkills, s.slug)}>
              {s.name || s.slug}
            </button>
          ))}
        </div>

        <label className="builder-label">Tools ({selTools.length})</label>
        <div className="builder-chips">
          {tools.map((t) => (
            <button key={t.slug} type="button"
              className={`chip ${selTools.includes(t.slug) ? "chip-on" : ""}`}
              onClick={() => toggle(selTools, setSelTools, t.slug)}>
              {t.slug}
            </button>
          ))}
        </div>

        <label className="builder-label">Planning default</label>
        <select className="builder-input" value={planning}
          onChange={(e) => setPlanning(e.target.value as typeof planning)}>
          <option value="off">Off — execute immediately</option>
          <option value="auto">Auto — plan, then execute</option>
          <option value="approve">Approve — plan, wait for approval</option>
        </select>

        {err && <div className="builder-err">⚠️ {err}</div>}

        <div className="builder-actions">
          <button className="clear-btn" onClick={onClose}>Cancel</button>
          <button className="send-btn" onClick={submit} disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create agent"}
          </button>
        </div>
      </div>
    </div>
  );
}
