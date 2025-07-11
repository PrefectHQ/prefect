import type { CellContext } from "@tanstack/react-table";
import { toast } from "sonner";
import type { GlobalConcurrencyLimit } from "@/api/global-concurrency-limits";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

type ActionsCellProps = CellContext<GlobalConcurrencyLimit, unknown> & {
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
};

export const ActionsCell = ({
	onEditRow,
	onDeleteRow,
	...props
}: ActionsCellProps) => {
	const handleCopyId = (id: string) => {
		void navigator.clipboard.writeText(id);
		toast.success("ID copied");
	};

	const row = props.row.original;

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
				<DropdownMenuItem onClick={() => handleCopyId(row.id)}>
					Copy ID
				</DropdownMenuItem>
				<DropdownMenuItem onClick={() => onDeleteRow(row)}>
					Delete
				</DropdownMenuItem>
				<DropdownMenuItem onClick={() => onEditRow(row)}>Edit</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
