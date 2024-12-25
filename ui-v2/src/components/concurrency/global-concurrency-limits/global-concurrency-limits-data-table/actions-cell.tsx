import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import type { GlobalConcurrencyLimit } from "@/hooks/global-concurrency-limits";
import { useToast } from "@/hooks/use-toast";
import type { CellContext } from "@tanstack/react-table";

type Props = CellContext<GlobalConcurrencyLimit, unknown> & {
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
};

export const ActionsCell = ({ onEditRow, onDeleteRow, ...props }: Props) => {
	const { toast } = useToast();

	const handleCopyId = (id: string | undefined) => {
		if (!id) {
			throw new Error("'id' field expected in GlobalConcurrencyLimit");
		}
		void navigator.clipboard.writeText(id);
		toast({ title: "ID copied" });
	};

	const row = props.row.original;

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
