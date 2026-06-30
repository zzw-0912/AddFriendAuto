import TaskPanel from "./TaskPanel";
import type { TaskDefaults, UserStatus } from "./types";

interface Props {
  apiBase: string;
  token: string;
  status: UserStatus | null;
  slotId: number;
  taskDefaults: TaskDefaults;
  taskDefaultsVersion: number;
  onStatusChange: () => void;
}

function TaskCard({ apiBase, token, status, slotId, taskDefaults, taskDefaultsVersion, onStatusChange }: Props) {
  return (
    <section className="task-card">
      <TaskPanel
        apiBase={apiBase}
        token={token}
        status={status}
        slotId={slotId}
        taskDefaults={taskDefaults}
        taskDefaultsVersion={taskDefaultsVersion}
        onStatusChange={onStatusChange}
      />
    </section>
  );
}

export default TaskCard;
