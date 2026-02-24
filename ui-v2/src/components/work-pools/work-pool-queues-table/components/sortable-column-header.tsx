import type { Column } from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/utils";

type SortableColumnHeaderProps<TData> = {
	column: Column<TData, unknown>;
	label: string;
};

export function SortableColumnHeader<TData>({
	column,
	label,
}: SortableColumnHeaderProps<TData>) {
	const sorted = column.getIsSorted();
	return (
		<button
			type="button"
			onClick={() => column.toggleSorting(sorted === "asc")}
			className="flex items-center gap-1 group h-auto p-0 font-medium text-muted-foreground hover:text-foreground"
		>
			{label}
			<span
				className={cn(
					"opacity-0 group-hover:opacity-100 transition-opacity size-3",
					sorted && "opacity-100 text-foreground",
				)}
			>
				{sorted === "desc" ? (
					<ArrowDown className="size-3" />
				) : (
					<ArrowUp className="size-3" />
				)}
			</span>
		</button>
	);
}
