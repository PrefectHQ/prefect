import { WorkerMenu } from "@/components/workers/worker-menu";
import type { WorkersTableRowActionsProps } from "../types";

export const WorkersTableRowActions = ({
	worker,
	workPoolName,
}: WorkersTableRowActionsProps) => {
	return <WorkerMenu worker={worker} workPoolName={workPoolName} />;
};
