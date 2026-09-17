/**
 * PlanSteps — отображение цепочки выполнения (M18 + M19).
 *
 * Использует реальные chain_step события из SSE:
 * - step: индекс шага (0-based)
 * - total_steps: общее количество шагов в цепочке
 * - state: "completed" | "failed" | "cancelled"
 * - capability: capability шага
 * - outputs: список output asset IDs
 */

export interface ChainStep {
  /** Индекс шага (0-based). */
  step: number;
  /** Общее количество шагов в цепочке. */
  total_steps: number;
  /** Состояние шага. */
  state: "pending" | "running" | "completed" | "failed" | "cancelled";
  /** Capability шага (из subtask.capability). */
  capability: string;
  /** Output assets шага. */
  outputs: string[];
}

interface PlanStepsProps {
  steps: ChainStep[];
  activeStepIndex: number | null;
  progressPct: number | null;
}

export default function PlanSteps({ steps, activeStepIndex, progressPct }: PlanStepsProps) {
  if (steps.length === 0) {
    return (
      <div className="plan-steps">
        <div className="plan-steps__empty">Шаги цепочки пока отсутствуют</div>
        {activeStepIndex !== null && (
          <div className="plan-steps__current">
            Активный шаг: <strong>{activeStepIndex + 1}</strong> из <strong>{steps.length || "?"}</strong>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="plan-steps">
      <div className="plan-steps__header">
        <span>Шаг {activeStepIndex !== null ? activeStepIndex + 1 : "?"} из {steps.length}</span>
        {progressPct !== null && (
          <span className="plan-steps__progress">
            прогресс: {progressPct}%
          </span>
        )}
      </div>

      <ol className="plan-steps__list">
        {steps.map((s, idx) => (
          <li
            key={idx}
            className={`plan-steps__item plan-steps__item--${s.state}${idx === activeStepIndex ? " plan-steps__item--active" : ""}`}
          >
            <span className="plan-steps__marker">{stepMarker(s.state)}</span>
            <span className="plan-steps__label">
              <span className="plan-steps__index">#{idx + 1}</span>
              <span className="plan-steps__capability">{s.capability}</span>
            </span>
            {s.outputs.length > 0 && (
              <span className="plan-steps__outputs">{s.outputs.length} output{s.outputs.length > 1 ? "s" : ""}</span>
            )}
          </li>
        ))}
      </ol>

      {activeStepIndex !== null && activeStepIndex >= steps.length && (
        <div className="plan-steps__pending">Ожидают: {steps.length - activeStepIndex}</div>
      )}
    </div>
  );
}

function stepMarker(state: ChainStep["state"]): string {
  switch (state) {
    case "completed":
      return "✓";
    case "failed":
      return "✗";
    case "cancelled":
      return "⊘";
    case "running":
      return "→";
    default:
      return "○";
  }
}
