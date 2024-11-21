import { VariablesLayout } from "@/components/variables/layout";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { useCallback, useMemo, useState } from "react";
import type { components } from "@/api/prefect";
import { VariablesDataTable } from "@/components/variables/data-table";
import {
	VariableDialog,
	type VariableDialogProps,
} from "@/components/variables/variable-dialog";
import { VariablesEmptyState } from "@/components/variables/empty-state";
import { useVariables } from "@/hooks/variables";

/**
 * Schema for validating URL search parameters for the variables page.
 * @property {number} offset - The number of items to skip (for pagination). Must be non-negative. Defaults to 0.
 * @property {number} limit - The maximum number of items to return. Must be positive. Defaults to 10.
 * @property {string} sort - The sort order for variables. Can be "CREATED_DESC", "UPDATED_DESC", "NAME_ASC", or "NAME_DESC". Defaults to "CREATED_DESC".
 * @property {string} name - Optional filter to search variables by name.
 * @property {string[]} tags - Optional array of tags to filter variables by.
 */
const searchParams = z.object({
	offset: z.number().int().nonnegative().optional().default(0),
	limit: z.number().int().positive().optional().default(10),
	sort: z
		.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
		.optional()
		.default("CREATED_DESC"),
	name: z.string().optional(),
	tags: z.array(z.string()).optional(),
});

/**
 * Builds a filter body for the variables API based on search parameters.
 * @param search - Optional search parameters containing offset, limit, sort, name filter, and tags filter
 * @returns An object containing pagination parameters and variable filters that can be passed to the variables API
 */
const buildFilterBody = (search?: z.infer<typeof searchParams>) => ({
	offset: search?.offset ?? 0,
	limit: search?.limit ?? 10,
	sort: search?.sort ?? "CREATED_DESC",
	variables: {
		operator: "and_" as const,
		...(search?.name && { name: { like_: search.name } }),
		...(search?.tags?.length && {
			tags: { operator: "and_" as const, all_: search.tags },
		}),
	},
});

function VariablesPage() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const { variables, filteredCount, totalCount } = useVariables(
		buildFilterBody(search),
	);

	const pageIndex = search.offset ? search.offset / search.limit : 0;
	const pageSize = search.limit ?? 10;
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex,
			pageSize,
		}),
		[pageIndex, pageSize],
	);
	const columnFilters: ColumnFiltersState = useMemo(
		() => [
			{ id: "name", value: search.name },
			{ id: "tags", value: search.tags },
		],
		[search.name, search.tags],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					offset: newPagination.pageIndex * newPagination.pageSize,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onColumnFiltersChange = useCallback(
		(newColumnFilters: ColumnFiltersState) => {
			void navigate({
				to: ".",
				search: (prev) => {
					const name = newColumnFilters.find((filter) => filter.id === "name")
						?.value as string;
					const tags = newColumnFilters.find((filter) => filter.id === "tags")
						?.value as string[];
					return {
						...prev,
						offset: 0,
						name,
						tags,
					};
				},
				replace: true,
			});
		},
		[navigate],
	);

	const onSortingChange = useCallback(
		(sortKey: components["schemas"]["VariableSort"]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					sort: sortKey,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const [addVariableDialogOpen, setAddVariableDialogOpen] = useState(false);
	const [variableToEdit, setVariableToEdit] = useState<
		VariableDialogProps["existingVariable"] | undefined
	>(undefined);

	const onAddVariableClick = useCallback(() => {
		setVariableToEdit(undefined);
		setAddVariableDialogOpen(true);
	}, []);

	const handleVariableEdit = useCallback(
		(variable: components["schemas"]["Variable"]) => {
			setVariableToEdit(variable);
			setAddVariableDialogOpen(true);
		},
		[],
	);

	const handleVariableDialogOpenChange = useCallback((open: boolean) => {
		setAddVariableDialogOpen(open);
	}, []);

	return (
		<VariablesLayout onAddVariableClick={onAddVariableClick}>
			<VariableDialog
				existingVariable={variableToEdit}
				onOpenChange={handleVariableDialogOpenChange}
				open={addVariableDialogOpen}
			/>
			{(totalCount ?? 0) > 0 ? (
				<VariablesDataTable
					variables={variables ?? []}
					currentVariableCount={filteredCount ?? 0}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					columnFilters={columnFilters}
					onColumnFiltersChange={onColumnFiltersChange}
					sorting={search.sort}
					onSortingChange={onSortingChange}
					onVariableEdit={handleVariableEdit}
				/>
			) : (
				<VariablesEmptyState onAddVariableClick={onAddVariableClick} />
			)}
		</VariablesLayout>
	);
}

export const Route = createFileRoute("/variables")({
	validateSearch: zodSearchValidator(searchParams),
	component: VariablesPage,
	loaderDeps: ({ search }) => buildFilterBody(search),
	loader: useVariables.loader,
	wrapInSuspense: true,
});
