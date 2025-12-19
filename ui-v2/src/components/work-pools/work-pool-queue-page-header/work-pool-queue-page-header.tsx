import type { WorkPoolQueue } from "@/api/work-pool-queues";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { cn } from "@/utils";
import { WorkPoolQueueMenu } from "../work-pool-queue-menu";
import { WorkPoolQueueToggle } from "../work-pool-queue-toggle";

export type WorkPoolQueuePageHeaderProps = {
	workPoolName: string;
	queue: WorkPoolQueue;
	onUpdate?: () => void;
	className?: string;
};

export const WorkPoolQueuePageHeader = ({
	workPoolName,
	queue,
	onUpdate,
	className,
}: WorkPoolQueuePageHeaderProps) => {
	return (
		<header
			className={cn(
				"flex mb-4 flex-row items-center justify-between",
				className,
			)}
		>
			<Breadcrumb className={className}>
				<BreadcrumbList>
					<BreadcrumbItem>
						<BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
							Work Pools
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem>
						<BreadcrumbLink
							to="/work-pools/work-pool/$workPoolName"
							params={{ workPoolName }}
							className="text-xl font-semibold"
						>
							{workPoolName}
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem className="text-xl font-semibold">
						<BreadcrumbPage>{queue.name}</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<div className="flex items-center space-x-2">
				<WorkPoolQueueToggle queue={queue} onUpdate={onUpdate} />
				<WorkPoolQueueMenu queue={queue} onUpdate={onUpdate} />
			</div>
		</header>
	);
};
