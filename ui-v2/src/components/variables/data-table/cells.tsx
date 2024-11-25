import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { MoreVerticalIcon } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getQueryService } from "@/api/service";
import type { CellContext } from "@tanstack/react-table";
import type { components } from "@/api/prefect";
import { useToast } from "@/hooks/use-toast";
import { JsonInput } from "@/components/ui/json-input";
import {
	HoverCard,
	HoverCardContent,
	HoverCardTrigger,
} from "@/components/ui/hover-card";
import { useRef } from "react";
import { useIsOverflowing } from "@/hooks/use-is-overflowing";

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
						onClick={() => {
							void navigator.clipboard.writeText(id);
							toast({
								title: "ID copied",
							});
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							void navigator.clipboard.writeText(row.original.name);
							toast({
								title: "Name copied",
							});
						}}
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
								toast({
									title: "Value copied",
								});
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

export const ValueCell = (
	props: CellContext<components["schemas"]["Variable"], unknown>,
) => {
	const value = props.getValue();
	const codeRef = useRef<HTMLDivElement>(null);
	const isOverflowing = useIsOverflowing(codeRef);

	if (!value) return null;
	return (
		// Disable the hover card if the value is overflowing
		<HoverCard open={isOverflowing ? undefined : false}>
			<HoverCardTrigger asChild>
				<code
					ref={codeRef}
					className="px-2 py-1 font-mono text-sm text-ellipsis overflow-hidden whitespace-nowrap block"
				>
					{JSON.stringify(value, null, 2)}
				</code>
			</HoverCardTrigger>
			<HoverCardContent className="p-0">
				<JsonInput value={JSON.stringify(value, null, 2)} disabled />
			</HoverCardContent>
		</HoverCard>
	);
};
