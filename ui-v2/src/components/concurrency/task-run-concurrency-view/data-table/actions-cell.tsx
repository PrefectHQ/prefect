import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { type TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { useToast } from "@/hooks/use-toast";
import { CellContext } from "@tanstack/react-table";

type Props = CellContext<TaskRunConcurrencyLimit, unknown> & {
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
};

export const ActionsCell = ({ onDeleteRow, onResetRow, ...props }: Props) => {
	const { toast } = useToast();

	const handleCopyId = (id: string | undefined) => {
		if (!id) {
			throw new Error("'id' field expected in GlobalConcurrencyLimit");
		}
		void navigator.clipboard.writeText(id);
		toast({ title: "Name copied" });
	};

	const row = props.row.original;

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
					<DropdownMenuItem onClick={() => handleCopyId(row.id)}>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onDeleteRow(row)}>
						Delete
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onResetRow(row)}>
						Reset
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
};
