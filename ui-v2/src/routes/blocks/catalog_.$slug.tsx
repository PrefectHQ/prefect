import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { BlockTypePage } from "@/components/blocks/block-type-page";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/blocks/catalog_/$slug")({
	component: function RouteComponent() {
		const { slug } = Route.useParams();
		const { data: blockType } = useSuspenseQuery(buildGetBlockTypeQuery(slug));
		return <BlockTypePage blockType={blockType} />;
	},
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockTypeQuery(params.slug)),
	wrapInSuspense: true,
	pendingComponent: function BlockTypePageSkeleton() {
		return (
			<div className="flex flex-col gap-6">
				<div className="flex items-center gap-2">
					<Skeleton className="h-6 w-16" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-16" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-32" />
				</div>
				<div className="rounded-lg border p-6 flex flex-col gap-4">
					<div className="flex items-center gap-4">
						<Skeleton className="h-12 w-12 rounded" />
						<Skeleton className="h-7 w-48" />
					</div>
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-3/4" />
					<Skeleton className="h-32 w-full" />
					<div className="flex justify-end">
						<Skeleton className="h-9 w-20" />
					</div>
				</div>
			</div>
		);
	},
});
