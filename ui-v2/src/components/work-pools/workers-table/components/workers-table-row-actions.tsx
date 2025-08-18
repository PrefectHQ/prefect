import type { WorkPoolWorker } from "@/api/work-pools";
import { WorkerMenu } from "@/components/workers/worker-menu";

export type WorkersTableRowActionsProps = {
	worker: WorkPoolWorker;
	workPoolName: string;
};

export const WorkersTableRowActions = ({
	worker,
	workPoolName,
}: WorkersTableRowActionsProps) => {
	return <WorkerMenu worker={worker} workPoolName={workPoolName} />;
};
