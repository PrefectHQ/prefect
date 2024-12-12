import { DropdownMenuItem } from "@/components/ui/dropdown-menu";

import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import type { DeploymentWithFlow } from "@/hooks/deployments";
import { useToast } from "@/hooks/use-toast";
import type { CellContext } from "@tanstack/react-table";

type ActionsCellProps = CellContext<DeploymentWithFlow, unknown> & {
	onQuickRun: (deployment: DeploymentWithFlow) => void;
	onCustomRun: (deployment: DeploymentWithFlow) => void;
	onEdit: (deployment: DeploymentWithFlow) => void;
	onDelete: (deployment: DeploymentWithFlow) => void;
	onDuplicate: (deployment: DeploymentWithFlow) => void;
};

export const ActionsCell = ({
	row,
	onQuickRun,
	onCustomRun,
	onEdit,
	onDelete,
	onDuplicate,
}: ActionsCellProps) => {
	const id = row.original.id;
	const { toast } = useToast();
	if (!id) return null;

	return (
		<div className="flex flex-row justify-end">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<Icon id="MoreVertical" className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuLabel>Actions</DropdownMenuLabel>
					<DropdownMenuItem onClick={() => onQuickRun(row.original)}>
						Quick Run
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onCustomRun(row.original)}>
						Custom Run
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							void navigator.clipboard.writeText(id);
							toast({
								title: "ID copied",
							});
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onEdit(row.original)}>
						Edit
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onDelete(row.original)}>
						Delete
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onDuplicate(row.original)}>
						Duplicate
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
};
