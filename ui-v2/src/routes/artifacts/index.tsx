import { useSuspenseQueries } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	type ArtifactsFilter,
	buildCountArtifactsQuery,
	buildListArtifactsQuery,
} from "@/api/artifacts";
import { ArtifactsPage } from "@/components/artifacts/artifacts-page";
import type { filterType } from "@/components/artifacts/types";
import useDebounceCallback from "@/hooks/use-debounce-callback";

/**
 * Schema for validating URL search parameters for the artifacts page.
 * @property {number} page - The page number to display. Must be positive. Defaults to 1.
 * @property {number} limit - The maximum number of items to return. Must be positive. Defaults to 10.
 */
const searchParams = z.object({
	type: z.string().optional().catch(""),
	name: z.string().optional().catch(""),
});

/**
 * Builds filter parameters for artifacts query from search params
 *
 * @param search - Optional validated search parameters containing page and limit
 * @returns ArtifactsFilter with type and name
 *
 * @example
 * ```ts
 * const filter = buildFilterBody({ type: "markdown", name: "my-dataset" })
 * // Returns {
 * //		artifacts: {
 * //			operator: "and_",
 * //			type: { any_: ["markdown"] },
 * //			key: { like_: "my-dataset" }
 * //		},
 * //		sort: "CREATED_DESC",
 * //		offset: 0
 * //}
 * ```
 */
const buildFilterBody = (
	search?: z.infer<typeof searchParams>,
): ArtifactsFilter => ({
	artifacts: {
		operator: "and_", // Logical operator for combining filters
		type: {
			any_: search?.type && search?.type !== "all" ? [search.type] : undefined, // Filter by artifact type
		},
		key: {
			like_: search?.name ?? "", // Filter by artifact name
		},
	},
	sort: "CREATED_DESC",
	offset: 0,
});

export const Route = createFileRoute("/artifacts/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildFilterBody(search),
	loader: async ({ deps, context }) => {
		const [artifactsCount, artifactsList] = await Promise.all([
			context.queryClient.ensureQueryData(buildCountArtifactsQuery(deps)),
			context.queryClient.ensureQueryData(buildListArtifactsQuery(deps)),
		]);

		return { artifactsCount, artifactsList };
	},
	wrapInSuspense: true,
});

const useFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const filters = useMemo(
		() => [
			{ id: "type", label: "Type", value: search.type ?? "all" },
			{ id: "name", label: "Name", value: search.name },
		],
		[search.type, search.name],
	);

	const onFilterChange = useDebounceCallback(
		useCallback(
			(newFilters: filterType[]) => {
				if (!newFilters) return;
				void navigate({
					to: ".",
					search: () =>
						newFilters
							.filter((filter) => filter.value)
							.reduce(
								(prev, curr) => {
									if (!curr.value) return prev;
									prev[curr.id] = curr.value;
									return prev;
								},
								{} as Record<string, string>,
							),
					replace: true,
				});
			},
			[navigate],
		),
		400,
	);

	return { filters, onFilterChange };
};

function RouteComponent() {
	const search = Route.useSearch();
	const { filters, onFilterChange } = useFilter();

	const [{ data: artifactsCount }, { data: artifactsList }] =
		useSuspenseQueries({
			queries: [
				buildCountArtifactsQuery(buildFilterBody(search)),
				buildListArtifactsQuery(buildFilterBody(search)),
			],
		});

	return (
		<ArtifactsPage
			filters={filters}
			onFilterChange={onFilterChange}
			artifactsCount={artifactsCount}
			artifactsList={artifactsList}
		/>
	);
}
