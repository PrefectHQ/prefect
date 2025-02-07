import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { useToast } from "@/hooks/use-toast";
import { Link } from "@tanstack/react-router";

export type DeploymentActionMenuProps = {
	id: string;
	onDelete: () => void;
};

export const DeploymentActionMenu = ({
	id,
	onDelete,
}: DeploymentActionMenuProps) => {
	const { toast } = useToast();

	const handleCopyId = (_id: string) => {
		void navigator.clipboard.writeText(_id);
		toast({ title: "ID copied" });
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="h-8 w-8 p-0">
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="h-4 w-4" />
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
