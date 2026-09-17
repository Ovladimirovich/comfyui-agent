import Spinner from "../common/Spinner";

interface CancelButtonProps {
  onClick: () => void;
  loading: boolean;
  error: string | null;
  disabled: boolean;
}

export default function CancelButton({ onClick, loading, error, disabled }: CancelButtonProps) {
  return (
    <div className="cancel-button-container">
      <button
        className={`cancel-button ${disabled ? "cancel-button--disabled" : ""}`}
        onClick={onClick}
        disabled={disabled || loading}
      >
        {loading ? <Spinner /> : "Cancel"}
      </button>
      {error && <div className="cancel-button__error">{error}</div>}
    </div>
  );
}