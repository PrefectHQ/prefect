import { createFileRoute } from "@tanstack/react-router";
import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import type { components } from "@/api/prefect";
import { VariablesDataTable } from "@/components/variables/data-table";
import { VariablesEmptyState } from "@/components/variables/empty-state";
import { VariablesLayout } from "@/components/variables/layout";
import {
	useVariableDialog,
	VariableDialog,
} from "@/components/variables/variable-dialog";
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
	offset: z.number().int().nonnegative().optional().default(0).catch(0),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z
		.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
		.optional()
		.default("CREATED_DESC")
		.catch("CREATED_DESC"),
	name: z.string().optional().catch(undefined),
	tags: z.array(z.string()).optional().catch(undefined),
});

export function VariablesPage() {
	const search = Route.useSearch();

	const { variables, filteredCount, totalCount } = useVariables(
		buildFilterBody(search),
	);
	const hasVariables = (totalCount ?? 0) > 0;
	const [pagination, onPaginationChange] = usePagination();
	const [columnFilters, onColumnFiltersChange] = useVariableColumnFilters();
	const [sorting, onSortingChange] = useVariableSorting();
	const [variableDialogState, onVariableAddOrEdit] = useVariableDialog();

	return (
		<VariablesLayout onAddVariableClick={onVariableAddOrEdit}>
			<VariableDialog {...variableDialogState} />
			{hasVariables ? (
				<VariablesDataTable
					variables={variables ?? []}
					currentVariableCount={filteredCount ?? 0}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					columnFilters={columnFilters}
					onColumnFiltersChange={onColumnFiltersChange}
					sorting={sorting}
					onSortingChange={onSortingChange}
					onVariableEdit={onVariableAddOrEdit}
				/>
			) : (
				<VariablesEmptyState onAddVariableClick={onVariableAddOrEdit} />
			)}
		</VariablesLayout>
	);
}

export const Route = createFileRoute("/variables")({
	validateSearch: zodValidator(searchParams),
	component: VariablesPage,
	loaderDeps: ({ search }) => buildFilterBody(search),
	loader: useVariables.loader,
	wrapInSuspense: true,
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

/**
 * Hook to manage pagination state and navigation for variables table
 *
 * Calculates current page index and size from URL search parameters and provides
 * a callback to update pagination state. Updates the URL when pagination changes.
 *
 * @returns A tuple containing:
 * - pagination: Current pagination state with pageIndex and pageSize
 * - onPaginationChange: Callback to update pagination and navigate with new search params
 */
const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pageIndex = search.offset ? Math.ceil(search.offset / search.limit) : 0;
	const pageSize = search.limit ?? 10;
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex,
			pageSize,
		}),
		[pageIndex, pageSize],
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

	return [pagination, onPaginationChange] as const;
};

/**
 * Hook to manage column filtering state and navigation for variables table
 *
 * Handles filtering by name and tags, updating the URL search parameters when filters change.
 * Resets pagination offset when filters are updated.
 *
 * @returns A tuple containing:
 * - columnFilters: Current column filter state for name and tags
 * - onColumnFiltersChange: Callback to update filters and navigate with new search params
 */
const useVariableColumnFilters = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	const columnFilters: ColumnFiltersState = useMemo(
		() => [
			{ id: "name", value: search.name },
			{ id: "tags", value: search.tags },
		],
		[search.name, search.tags],
	);

	const onColumnFiltersChange = useCallback(
		(newColumnFilters: ColumnFiltersState) => {
			void navigate({
				to: ".",
				search: (prev) => {
					const name = newColumnFilters.find((filter) => filter.id === "name")
						?.value as string | undefined;
					const tags = newColumnFilters.find((filter) => filter.id === "tags")
						?.value as string[] | undefined;
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

	return [columnFilters, onColumnFiltersChange] as const;
};

/**
 * Hook to manage sorting state and navigation for variables table
 *
 * Handles updating the URL search parameters when sort key changes.
 * Uses the current sort value from search params and provides a callback
 * to update sorting.
 *
 * @returns A tuple containing:
 * - sorting: Current sort key from search params
 * - onSortingChange: Callback to update sort and navigate with new search params
 */
const useVariableSorting = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSortingChange = useCallback(
		(sortKey: components["schemas"]["VariableSort"]) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, sort: sortKey }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search.sort, onSortingChange] as const;
};
