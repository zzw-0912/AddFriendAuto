import TaskPanel from "./TaskPanel";

interface Props {
  apiBase: string;
  token: string;
  status: { membership: { is_active: boolean; ends_at: string | null }; trial: { total: number; used: number; remaining: number } } | null;
  onStatusChange: () => void;
}

function TaskCard({ apiBase, token, status, onStatusChange }: Props) {
  return (
    <section className="task-card">
      <TaskPanel
        apiBase={apiBase}
        token={token}
        status={status}
        onStatusChange={onStatusChange}
      />
    </section>
  );
}

export default TaskCard;
