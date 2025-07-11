import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

export type WorkPoolContextMenuProps = {
	workPool: WorkPool;
	onDelete: () => void;
};

export const WorkPoolContextMenu = ({
	workPool,
	onDelete,
}: WorkPoolContextMenuProps) => {
	const handleCopyId = (id: string) => {
		void navigator.clipboard.writeText(id);
		toast.success("ID copied");
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="size-8 p-0">
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				<DropdownMenuLabel>Actions</DropdownMenuLabel>
				<DropdownMenuItem onClick={() => handleCopyId(workPool.id)}>
					Copy ID
				</DropdownMenuItem>
				<Link
					to="/work-pools/work-pool/$workPoolName/edit"
					params={{ workPoolName: workPool.name }}
				>
					<DropdownMenuItem>Edit</DropdownMenuItem>
				</Link>
				<DropdownMenuItem onClick={onDelete}>Delete</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
