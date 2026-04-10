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

type TaskRunConcurrencyLimitsActionsMenuProps = {
	id: string;
	onDelete: () => void;
	onReset: () => void;
	canUpdate?: boolean;
	canDelete?: boolean;
};

export const TaskRunConcurrencyLimitsActionsMenu = ({
	id,
	onDelete,
	onReset,
	canUpdate = true,
	canDelete = true,
}: TaskRunConcurrencyLimitsActionsMenuProps) => {
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
				<DropdownMenuItem onClick={() => handleCopyId(id)}>
					Copy ID
				</DropdownMenuItem>
				{canDelete && (
					<DropdownMenuItem variant="destructive" onClick={onDelete}>
						Delete
					</DropdownMenuItem>
				)}
				{canUpdate && (
					<DropdownMenuItem onClick={onReset}>Reset</DropdownMenuItem>
				)}
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
