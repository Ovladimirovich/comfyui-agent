import { useCallback, useEffect, useState } from "react";
import { cancelJob, jobStatus } from "../../lib/api";
import { JobStatus } from "../../lib/types";
import JobCard from "./JobCard";
import CancelButton from "./CancelButton";

interface ExecutionZoneProps {
  sessionId: string;
}

export default function ExecutionZone({ sessionId }: ExecutionZoneProps) {
  const [jobStatusData, setJobStatusData] = useState<JobStatus | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const refreshJobStatus = useCallback(async () => {
    const status = await jobStatus(sessionId);
    if (status) {
      setJobStatusData(status);
    }
  }, [sessionId]);

  const handleCancel = useCallback(async () => {
    setCancelLoading(true);
    setCancelError(null);
    try {
      await cancelJob(sessionId);
      // После отмены обновляем статус
      await refreshJobStatus();
    } catch (err) {
      setCancelError(String(err));
    } finally {
      setCancelLoading(false);
    }
  }, [sessionId, refreshJobStatus]);

  // Обновляем статус каждые 2 секунды когда есть активный job
  useEffect(() => {
    if (!jobStatusData) return;
    
    const interval = setInterval(refreshJobStatus, 2000);
    return () => clearInterval(interval);
  }, [jobStatusData, refreshJobStatus]);

  // Первичная загрузка при монтировании
  useEffect(() => {
    refreshJobStatus();
  }, [refreshJobStatus]);

  if (!jobStatusData) {
    return (
      <div className="execution-zone">
        <div className="execution-zone__header">
          <h2>Execution</h2>
        </div>
        <div className="execution-zone__empty">
          Нет активного выполнения
        </div>
      </div>
    );
  }

  return (
    <div className="execution-zone">
      <div className="execution-zone__header">
        <h2>Execution</h2>
      </div>
      
      <JobCard job={jobStatusData} />
      
      <div className="execution-zone__actions">
        <CancelButton 
          onClick={handleCancel}
          loading={cancelLoading}
          error={cancelError}
          disabled={!jobStatusData || jobStatusData.state === "SUCCESS" || jobStatusData.state === "FAILED" || jobStatusData.state === "CANCELLED"}
        />
      </div>
    </div>
  );
}