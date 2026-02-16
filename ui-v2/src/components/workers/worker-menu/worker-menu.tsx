import type { WorkPoolWorker } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils";
import { DeleteWorkerDialog } from "./components/delete-worker-dialog";
import { useWorkerMenu } from "./hooks/use-worker-menu";

type WorkerMenuProps = {
	worker: WorkPoolWorker;
	workPoolName: string;
	onWorkerDeleted?: () => void;
	className?: string;
};

export const WorkerMenu = ({
	worker,
	workPoolName,
	onWorkerDeleted,
	className,
}: WorkerMenuProps) => {
	const {
		menuItems,
		showDeleteDialog,
		setShowDeleteDialog,
		triggerIcon: TriggerIcon,
	} = useWorkerMenu(worker);

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						className={cn("h-8 w-8", className)}
					>
						<span className="sr-only">Open menu</span>
						<TriggerIcon className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					{menuItems.map((item) => {
						const Icon = item.icon;
						return (
							<DropdownMenuItem
								key={item.label}
								onClick={item.action}
								className={cn(
									item.variant === "destructive" && "text-destructive",
								)}
							>
								<Icon className="mr-2 h-4 w-4" />
								{item.label}
							</DropdownMenuItem>
						);
					})}
				</DropdownMenuContent>
			</DropdownMenu>
			<DeleteWorkerDialog
				worker={worker}
				workPoolName={workPoolName}
				open={showDeleteDialog}
				onOpenChange={setShowDeleteDialog}
				onDeleted={onWorkerDeleted}
			/>
		</>
	);
};
