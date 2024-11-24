import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "../../ui/dropdown-menu";
import { Button } from "../../ui/button";
import { MoreVerticalIcon } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getQueryService } from "@/api/service";
import type { CellContext } from "@tanstack/react-table";
import type { components } from "@/api/prefect";
import { useToast } from "@/hooks/use-toast";

type ActionsCellProps = CellContext<
	components["schemas"]["Variable"],
	unknown
> & {
	onVariableEdit: (variable: components["schemas"]["Variable"]) => void;
};

export const ActionsCell = ({ row, onVariableEdit }: ActionsCellProps) => {
	const id = row.original.id;
	const queryClient = useQueryClient();
	const { mutate: deleteVariable } = useMutation({
		mutationKey: ["delete-variable"],
		mutationFn: async (id: string) =>
			await getQueryService().DELETE("/variables/{id}", {
				params: { path: { id } },
			}),
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "variables",
				}),
				queryClient.invalidateQueries({
					queryKey: ["total-variable-count"],
				}),
			]);
		},
	});
	const { toast } = useToast();
	if (!id) return null;

	const onVariableDelete = () => {
		deleteVariable(id);
		toast({
			title: "Variable deleted",
		});
	};

	return (
		<div className="flex flex-row justify-end">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<MoreVerticalIcon className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuLabel>Actions</DropdownMenuLabel>
					<DropdownMenuItem
						onClick={() => void navigator.clipboard.writeText(id)}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() =>
							void navigator.clipboard.writeText(row.original.name)
						}
					>
						Copy Name
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							const copyValue =
								typeof row.original.value !== "string"
									? JSON.stringify(row.original.value)
									: row.original.value;
							if (copyValue) {
								void navigator.clipboard.writeText(copyValue);
							}
						}}
					>
						Copy Value
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => onVariableEdit(row.original)}>
						Edit
					</DropdownMenuItem>
					<DropdownMenuItem onClick={onVariableDelete}>Delete</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
};
