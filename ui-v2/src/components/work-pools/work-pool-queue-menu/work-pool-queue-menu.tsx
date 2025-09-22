import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils";
import { DeleteWorkPoolQueueDialog } from "./components/delete-work-pool-queue-dialog";
import { useWorkPoolQueueMenu } from "./hooks/use-work-pool-queue-menu";

type WorkPoolQueueMenuProps = {
	queue: WorkPoolQueue;
	onUpdate?: () => void;
	className?: string;
};

export const WorkPoolQueueMenu = ({
	queue,
	onUpdate,
	className,
}: WorkPoolQueueMenuProps) => {
	const {
		menuItems,
		showDeleteDialog,
		setShowDeleteDialog,
		triggerIcon: TriggerIcon,
	} = useWorkPoolQueueMenu(queue);

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						variant="outline"
						size="icon"
						className={cn("size-8", className)}
					>
						<span className="sr-only">Open menu</span>
						<TriggerIcon className="size-4" />
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
			<DeleteWorkPoolQueueDialog
				queue={queue}
				open={showDeleteDialog}
				onOpenChange={setShowDeleteDialog}
				onDeleted={onUpdate}
			/>
		</>
	);
};
