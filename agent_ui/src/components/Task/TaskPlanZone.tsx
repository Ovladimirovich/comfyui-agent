/**
 * TaskPlanZone — зона "Task & Plan" (F3).
 *
 * Отображает:
 * - Текущую задачу (intent, dialog_state, результат/ошибка) через TaskCard
 * - План/цепочку шагов через PlanSteps
 * - D-1A: agent_message и dialog_state из терминальных событий
 *
 * Данные берутся из state App.tsx, который обновляется из SSE и snapshot.
 */
import { type ChainStep } from "./PlanSteps";
import TaskCard from "./TaskCard";
import PlanSteps from "./PlanSteps";

interface TaskPlanZoneProps {
  /** Последний пользовательский запрос (intent). */
  userIntent: string | null;
  /** Текущий dialog_state. */
  dialogState: string | null;
  /** Список шагов цепочки. */
  steps: ChainStep[];
  /** Индекс активного шага (-1 если нет активного). */
  activeStepIndex: number;
  /** Процент прогресса текущего шага (null если неизвестен). */
  progressPct: number | null;
  /** Ошибка из результата. */
  error: string | null;
  /** Job ID результата. */
  jobId: string | null;
  /** Capability последнего выполненного шага. */
  lastCapability: string | null;
  /** Сообщение агента (D-1A agent_message). */
  agentMessage: string | null;
}

export default function TaskPlanZone({
  userIntent,
  dialogState,
  steps,
  activeStepIndex,
  progressPct,
  error,
  jobId,
  lastCapability,
  agentMessage,
}: TaskPlanZoneProps) {
  const hasSteps = steps.length > 0;
  const hasActive = activeStepIndex >= 0 && activeStepIndex < steps.length;
  const isActive = dialogState === "planning" || dialogState === "executing" || dialogState === "chain" || hasActive;

  return (
    <div className="task-plan-zone">
      <section className="task-plan-zone__section">
        <h2 className="task-plan-zone__heading">Задача</h2>
        <TaskCard
          userIntent={userIntent}
          dialogState={dialogState}
          error={error}
          jobId={jobId}
          lastCapability={lastCapability}
        />
        {agentMessage ? (
          <div className="task-plan-zone__agent-message">
            <span className="task-plan-zone__agent-label">Agent message:</span>
            <span className="task-plan-zone__agent-text">{agentMessage}</span>
          </div>
        ) : null}
      </section>

      <section className="task-plan-zone__section">
        <h2 className="task-plan-zone__heading">
          План
          {hasSteps ? (
            <span className="task-plan-zone__step-count">
              {" "}
              ({steps.length} шаг{steps.length > 1 && steps.length < 5 ? "а" : steps.length >= 5 ? "ов" : ""})
            </span>
          ) : null}
        </h2>
        <PlanSteps
          steps={steps}
          activeStepIndex={hasActive ? activeStepIndex : null}
          progressPct={isActive ? progressPct : null}
        />
      </section>

      {!isActive && !hasSteps && (
        <div className="task-plan-zone__empty">
          Нет активной задачи. Отправьте запрос для начала выполнения.
        </div>
      )}
    </div>
  );
}
