import type { WorkPool } from "@/api/work-pools";
import { WorkPoolMenu } from "@/components/work-pools/work-pool-menu";
import { WorkPoolToggle } from "@/components/work-pools/work-pool-toggle";

interface WorkPoolActionsProps {
	workPool: WorkPool;
	onUpdate?: () => void;
}

export const WorkPoolActions = ({
	workPool,
	onUpdate,
}: WorkPoolActionsProps) => {
	return (
		<>
			<WorkPoolToggle workPool={workPool} onUpdate={onUpdate} />
			<WorkPoolMenu workPool={workPool} onUpdate={onUpdate} />
		</>
	);
};
