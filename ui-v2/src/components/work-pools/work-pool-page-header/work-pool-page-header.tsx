import type { WorkPool } from "@/api/work-pools";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { cn } from "@/utils";
import { WorkPoolMenu } from "../work-pool-menu";
import { WorkPoolToggle } from "../work-pool-toggle";

type WorkPoolPageHeaderProps = {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
};

export const WorkPoolPageHeader = ({
	workPool,
	onUpdate,
	className,
}: WorkPoolPageHeaderProps) => {
	return (
		<header
			className={cn("flex flex-row items-center justify-between", className)}
		>
			<Breadcrumb className={cn("min-w-0", className)}>
				<BreadcrumbList className="flex-nowrap">
					<BreadcrumbItem>
						<BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
							Work pools
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem className="text-xl font-semibold min-w-0">
						<BreadcrumbPage className="truncate block" title={workPool.name}>
							{workPool.name}
						</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<div className="flex items-center space-x-2">
				<WorkPoolToggle workPool={workPool} onUpdate={onUpdate} />
				<WorkPoolMenu workPool={workPool} onUpdate={onUpdate} />
			</div>
		</header>
	);
};
