import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { categorizeError } from "@/api/error-utils";
import { BlocksCatalogPage } from "@/components/blocks/blocks-catalog-page/blocks-catalog-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

const searchParams = z.object({
	blockName: z.string().optional(),
});

export const Route = createFileRoute("/blocks/catalog")({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		const [search, onSearch] = useSearch();
		const { data: blockTypes } = useSuspenseQuery(
			buildListFilterBlockTypesQuery({
				block_types: { name: { like_: search } },
				offset: 0,
			}),
		);

		return (
			<BlocksCatalogPage
				blockTypes={blockTypes}
				search={search}
				onSearch={onSearch}
			/>
		);
	},
	loaderDeps: ({ search: { blockName } }) => ({
		blockName,
	}),
	loader: ({ deps, context: { queryClient } }) => {
		return queryClient.ensureQueryData(
			buildListFilterBlockTypesQuery({
				block_types: { name: { like_: deps.blockName } },
				offset: 0,
			}),
		);
	},
	errorComponent: function BlockCatalogErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load block catalog");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Block Catalog</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});

function useSearch() {
	const { blockName } = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSearch = useCallback(
		(value?: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					blockName: value,
				}),
				replace: true,
			});
		},
		[navigate],
	);
	const search = useMemo(() => blockName ?? "", [blockName]);
	return [search, onSearch] as const;
}
