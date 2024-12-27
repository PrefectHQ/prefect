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

type Props = {
	id: string | undefined;
	onDelete: () => void;
	onReset: () => void;
};

export const TaskRunConcurrencyLimitsActionsMenu = ({
	id,
	onDelete,
	onReset,
}: Props) => {
	const { toast } = useToast();

	const handleCopyId = (id: string | undefined) => {
		if (!id) {
			throw new Error("'id' field expected in GlobalConcurrencyLimit");
		}
		void navigator.clipboard.writeText(id);
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
				<DropdownMenuItem onClick={onDelete}>Delete</DropdownMenuItem>
				<DropdownMenuItem onClick={onReset}>Reset</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
