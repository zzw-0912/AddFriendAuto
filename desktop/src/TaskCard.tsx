import TaskPanel from "./TaskPanel";
import type { TaskDefaults, UserStatus } from "./types";

interface Props {
  apiBase: string;
  token: string;
  status: UserStatus | null;
  slotId: number;
  taskDefaults: TaskDefaults;
  taskDefaultsVersion: number;
  onStatusChange: (options?: { force?: boolean }) => void | Promise<unknown>;
  onOpenTutorial: () => void;
  onOpenPayment: () => void;
  onOpenProfile: () => void;
}

function TaskCard({
  apiBase,
  token,
  status,
  slotId,
  taskDefaults,
  taskDefaultsVersion,
  onStatusChange,
  onOpenTutorial,
  onOpenPayment,
  onOpenProfile,
}: Props) {
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
        onOpenTutorial={onOpenTutorial}
        onOpenPayment={onOpenPayment}
        onOpenProfile={onOpenProfile}
      />
    </section>
  );
}

export default TaskCard;
