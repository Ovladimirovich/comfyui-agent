/**
 * ResultsZone — зона "Results & Assets" (F5).
 *
 * Отображает результаты выполнения:
 * - список ассетов (через существующий AssetCard)
 * - основной превью для активного ассета
 * - workflow информацию
 * - состояние (SUCCESS/FAILED/CANCELLED)
 * - ошибку если есть
 *
 * Данные берутся из state App.tsx (messages, dialogState, agentMessage).
 */
import AssetCard from "../Assets/AssetCard";

interface ResultsZoneProps {
  /** Ассеты последнего результата (из последнего сообщения). */
  assets: string[];
  /** Активный ассет для превью. */
  activeAsset: string | null;
  /** Workflow ID@version если есть. */
  activeWorkflow: string | null;
  /** Job ID результата. */
  jobId: string | null;
  /** Текущий dialog_state. */
  dialogState: string | null;
  /** Сообщение агента (D-1A agent_message). */
  agentMessage: string | null;
  /** Ошибка из результата. */
  error: string | null;
}

export default function ResultsZone({
  assets,
  activeAsset,
  activeWorkflow,
  jobId,
  dialogState,
  agentMessage,
  error,
}: ResultsZoneProps) {
  const isCompleted = dialogState === "SUCCESS";
  const isFailed = dialogState === "FAILED";
  const isCancelled = dialogState === "CANCELLED";
  const hasAssets = assets.length > 0;

  return (
    <div className="results-zone">
      <div className="results-zone__header">
        <h2>Results & Assets</h2>
        <div className="results-zone__status">
          {dialogState && (
            <span className={`results-zone__state results-zone__state--${dialogState.toLowerCase()}`}>
              {dialogState}
            </span>
          )}
        </div>
      </div>

      {agentMessage ? (
        <div className="results-zone__agent-message">
          <span className="results-zone__agent-label">Agent message:</span>
          <span className="results-zone__agent-text">{agentMessage}</span>
        </div>
      ) : null}

      {error ? (
        <div className="results-zone__error">
          <span className="results-zone__error-label">Ошибка:</span>
          <span className="results-zone__error-text">{error}</span>
        </div>
      ) : null}

      {jobId ? (
        <div className="results-zone__meta">
          <span className="results-zone__meta-label">Job:</span>
          <span className="results-zone__meta-value">{jobId}</span>
        </div>
      ) : null}

      {activeWorkflow ? (
        <div className="results-zone__meta">
          <span className="results-zone__meta-label">Workflow:</span>
          <span className="results-zone__meta-value">{activeWorkflow}</span>
        </div>
      ) : null}

      <section className="results-zone__section">
        <h3 className="results-zone__heading">
          Assets
          {hasAssets && (
            <span className="results-zone__count">
              {" "}
              ({assets.length} {assets.length === 1 ? "asset" : "assets"})
            </span>
          )}
        </h3>

        {hasAssets ? (
          <div className="results-zone__assets">
            {/* Primary preview for active/last asset */}
            {(activeAsset || assets[assets.length - 1]) && (
              <div className="results-zone__primary">
                <div className="results-zone__primary-label">
                  {activeAsset ? "Primary result" : "Latest result"}
                </div>
                <AssetCard
                  assetId={activeAsset || assets[assets.length - 1]}
                  initialText="result"
                />
              </div>
            )}

            {/* All assets list */}
            <div className="results-zone__list">
              {assets.map((assetId, index) => (
                <div key={assetId} className="results-zone__asset-item">
                  <AssetCard assetId={assetId} initialText={`asset ${index + 1}`} />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="results-zone__empty">
            Нет ассетов. Выполните задачу для получения результатов.
          </div>
        )}
      </section>

      {!hasAssets && !isCompleted && !isFailed && !isCancelled && (
        <div className="results-zone__empty">
          Нет результатов. Отправьте запрос для начала выполнения.
        </div>
      )}
    </div>
  );
}