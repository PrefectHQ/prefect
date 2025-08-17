import type { WorkPool } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { DeleteWorkPoolDialog } from "./components/delete-work-pool-dialog";
import { useWorkPoolMenu } from "./hooks/use-work-pool-menu";

interface WorkPoolMenuProps {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
}

export const WorkPoolMenu = ({
	workPool,
	onUpdate,
	className,
}: WorkPoolMenuProps) => {
	const {
		menuItems,
		showDeleteDialog,
		setShowDeleteDialog,
		triggerIcon: TriggerIcon,
	} = useWorkPoolMenu(workPool);

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
			<DeleteWorkPoolDialog
				workPool={workPool}
				open={showDeleteDialog}
				onOpenChange={setShowDeleteDialog}
				onDeleted={onUpdate}
			/>
		</>
	);
};
