/**
 * TaskCard — карточка текущей задачи (intent + dialog_state + result/error).
 *
 * Данные берутся из:
 * - userIntent: последний пользовательский запрос
 * - dialogState: текущее состояние диалога
 * - resultError: ошибка из terminal result/error события
 * - resultJobId: job ID из результата
 */
import DialogStateBadge from "../Conversation/DialogStateBadge";

interface TaskCardProps {
  /** Пользовательский запрос (intent). */
  userIntent: string | null;
  /** Текущий dialog_state. */
  dialogState: string | null;
  /** Ошибка из результата. */
  error: string | null;
  /** Job ID результата. */
  jobId: string | null;
  /** Capability последнего шага. */
  lastCapability: string | null;
}

export default function TaskCard({ userIntent, dialogState, error, jobId, lastCapability }: TaskCardProps) {
  return (
    <div className="task-card">
      <div className="task-card__header">
        <span className="task-card__title">Текущая задача</span>
        <DialogStateBadge dialogState={dialogState} />
      </div>

      {userIntent ? (
        <div className="task-card__intent">
          <span className="task-card__label">Intent:</span>
          <span className="task-card__value">{userIntent}</span>
        </div>
      ) : (
        <div className="task-card__intent task-card__intent--empty">
          Запрос не задан
        </div>
      )}

      {lastCapability && (
        <div className="task-card__meta">
          <span className="task-card__label">Capability:</span>
          <span className="task-card__capability">{lastCapability}</span>
        </div>
      )}

      {jobId && (
        <div className="task-card__meta">
          <span className="task-card__label">Job:</span>
          <span className="task-card__job-id">{jobId}</span>
        </div>
      )}

      {error ? (
        <div className="task-card__error">
          <span className="task-card__label">Ошибка:</span>
          <span className="task-card__error-text">{error}</span>
        </div>
      ) : null}
    </div>
  );
}
