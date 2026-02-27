import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockDocumentQuery } from "@/api/block-documents";
import { BlockDocumentDetailsPage } from "@/components/blocks/block-document-details-page/block-document-details-page";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/blocks/block/$id")({
	component: function RouteComponent() {
		const { id } = Route.useParams();
		const { data } = useSuspenseQuery(buildGetBlockDocumentQuery(id));
		return <BlockDocumentDetailsPage blockDocument={data} />;
	},
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockDocumentQuery(params.id)),
	wrapInSuspense: true,
	pendingComponent: function BlockDocumentDetailSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<Skeleton className="h-6 w-16" />
						<Skeleton className="h-4 w-4" />
						<Skeleton className="h-6 w-48" />
					</div>
					<Skeleton className="h-8 w-8" />
				</div>
				<div className="rounded-lg border p-4">
					<div className="grid grid-cols-[1fr_250px] gap-4">
						<div className="flex flex-col gap-4">
							<Skeleton className="h-4 w-full" />
							<Skeleton className="h-32 w-full" />
							<Skeleton className="h-4 w-3/4" />
						</div>
						<div className="flex flex-col gap-3">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-32" />
							<Skeleton className="h-4 w-20" />
						</div>
					</div>
				</div>
			</div>
		);
	},
});
