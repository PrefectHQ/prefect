import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { BlocksCatalogPage } from "@/components/blocks/blocks-catalog-page/blocks-catalog-page";
import { Skeleton } from "@/components/ui/skeleton";

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
	wrapInSuspense: true,
	pendingComponent: function BlocksCatalogPageSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center gap-2">
					<Skeleton className="h-6 w-16" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-20" />
				</div>
				<div className="flex items-center justify-between">
					<Skeleton className="h-4 w-24" />
					<Skeleton className="h-9 w-40" />
				</div>
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
					{Array.from({ length: 6 }).map((_, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: okay for static skeleton list
						<div key={i} className="rounded-lg border p-6 flex flex-col gap-3">
							<div className="flex items-center gap-4">
								<Skeleton className="h-10 w-10 rounded" />
								<Skeleton className="h-5 w-32" />
							</div>
							<Skeleton className="h-20 w-full" />
							<div className="flex justify-end gap-2">
								<Skeleton className="h-8 w-16" />
								<Skeleton className="h-8 w-16" />
							</div>
						</div>
					))}
				</div>
			</div>
		);
	},
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
