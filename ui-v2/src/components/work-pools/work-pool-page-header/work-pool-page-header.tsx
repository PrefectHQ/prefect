import type { WorkPool } from "@/api/work-pools";
import { cn } from "@/lib/utils";
import { WorkPoolActions } from "./components/work-pool-actions";
import { WorkPoolBreadcrumbs } from "./components/work-pool-breadcrumbs";
import { WorkPoolTitle } from "./components/work-pool-title";

interface WorkPoolPageHeaderProps {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
}

export const WorkPoolPageHeader = ({
	workPool,
	onUpdate,
	className,
}: WorkPoolPageHeaderProps) => {
	const breadcrumbs = <WorkPoolBreadcrumbs workPoolName={workPool.name} />;
	const title = <WorkPoolTitle workPool={workPool} />;
	const actions = <WorkPoolActions workPool={workPool} onUpdate={onUpdate} />;

	return (
		<header
			className={cn(
				"flex flex-col space-y-4 md:flex-row md:items-center md:justify-between md:space-y-0",
				className,
			)}
		>
			<div className="flex flex-col space-y-2">
				{breadcrumbs && <nav>{breadcrumbs}</nav>}
				<div className="flex flex-col space-y-1">
					<h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
				</div>
			</div>
			{actions && <div className="flex items-center space-x-2">{actions}</div>}
		</header>
	);
};
