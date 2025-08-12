import type { WorkPool } from "@/api/work-pools";
import { PageHeading } from "@/components/ui/page-heading";
import { WorkPoolActions } from "./components/work-pool-actions";
import { WorkPoolBreadcrumbs } from "./components/work-pool-breadcrumbs";
import { WorkPoolTitle } from "./components/work-pool-title";

interface PageHeadingWorkPoolProps {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
}

export const PageHeadingWorkPool = ({
	workPool,
	onUpdate,
	className,
}: PageHeadingWorkPoolProps) => {
	return (
		<PageHeading
			breadcrumbs={<WorkPoolBreadcrumbs workPoolName={workPool.name} />}
			title={<WorkPoolTitle workPool={workPool} />}
			actions={<WorkPoolActions workPool={workPool} onUpdate={onUpdate} />}
			className={className}
		/>
	);
};
