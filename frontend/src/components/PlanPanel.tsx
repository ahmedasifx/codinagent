import { useState } from "react";

interface Props {
  plan: string;
  awaitingApproval?: boolean;
  onApprove: (editedPlan: string) => void;
  onReject: () => void;
}

export function PlanPanel({ plan, awaitingApproval, onApprove, onReject }: Props) {
  const [draft, setDraft] = useState(plan);

  return (
    <div className="plan-panel">
      <div className="plan-head">📋 Plan{awaitingApproval ? " — review & approve" : ""}</div>
      {awaitingApproval ? (
        <>
          <textarea
            className="plan-edit"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(14, draft.split("\n").length + 1)}
          />
          <div className="plan-actions">
            <button className="clear-btn" onClick={onReject}>Reject</button>
            <button className="send-btn" onClick={() => onApprove(draft)}>Approve &amp; run ▶</button>
          </div>
        </>
      ) : (
        <pre className="plan-text">{plan}</pre>
      )}
    </div>
  );
}
