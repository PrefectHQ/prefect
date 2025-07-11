import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

export type DeploymentActionMenuProps = {
	id: string;
	onDelete: () => void;
};

export const DeploymentActionMenu = ({
	id,
	onDelete,
}: DeploymentActionMenuProps) => {
	const handleCopyId = (_id: string) => {
		void navigator.clipboard.writeText(_id);
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
				<DropdownMenuItem onClick={() => handleCopyId(id)}>
					Copy ID
				</DropdownMenuItem>
				<Link to="/deployments/deployment/$id/edit" params={{ id }}>
					<DropdownMenuItem>Edit</DropdownMenuItem>
				</Link>
				<DropdownMenuItem onClick={onDelete}>Delete</DropdownMenuItem>
				<Link to="/deployments/deployment/$id/duplicate" params={{ id }}>
					<DropdownMenuItem>Duplicate</DropdownMenuItem>
				</Link>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
