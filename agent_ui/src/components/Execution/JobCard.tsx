import { JobStatus } from "../../lib/types";

interface JobCardProps {
  job: JobStatus;
}

export default function JobCard({ job }: JobCardProps) {
  const stateColor = {
    QUEUED: "#8a8f98",
    RUNNING: "#2f6df0",
    SUCCESS: "#3cbf6f",
    FAILED: "#e5484d",
    CANCELLED: "#8a8f98",
  }[job.state] || "#8a8f98";

  return (
    <div className="job-card">
      <div className="job-card__header">
        <span className="job-card__title">Job</span>
        <span className="job-card__state" style={{ color: stateColor }}>
          {job.state}
        </span>
      </div>

      <div className="job-card__meta">
        <span className="job-card__label">ID:</span>
        <span className="job-card__value">{job.prompt_id}</span>
      </div>

      {job.progress_pct !== null && (
        <div className="job-card__progress">
          <span className="job-card__label">Progress:</span>
          <span className="job-card__value">{job.progress_pct}%</span>
          <div className="job-card__progress-bar">
            <div
              className="job-card__progress-fill"
              style={{ width: `${job.progress_pct}%` }}
            />
          </div>
        </div>
      )}

      {job.workflow_id && (
        <div className="job-card__meta">
          <span className="job-card__label">Workflow:</span>
          <span className="job-card__value">
            {job.workflow_id}@{job.workflow_version}
          </span>
        </div>
      )}

      {job.duration !== null && (
        <div className="job-card__meta">
          <span className="job-card__label">Duration:</span>
          <span className="job-card__value">{job.duration.toFixed(1)}s</span>
        </div>
      )}

      {job.error && (
        <div className="job-card__error">
          <span className="job-card__label">Error:</span>
          <span className="job-card__error-text">{job.error}</span>
        </div>
      )}
    </div>
  );
}