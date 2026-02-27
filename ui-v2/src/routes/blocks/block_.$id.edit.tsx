import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockDocumentQuery } from "@/api/block-documents";
import { categorizeError } from "@/api/error-utils";
import { BlockDocumentEditPage } from "@/components/blocks/block-document-edit-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

export const Route = createFileRoute("/blocks/block_/$id/edit")({
	component: function RouteComponent() {
		const { id } = Route.useParams();
		const { data } = useSuspenseQuery(buildGetBlockDocumentQuery(id));
		return <BlockDocumentEditPage blockDocument={data} />;
	},
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockDocumentQuery(params.id)),
	errorComponent: function BlockEditErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load block");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Edit Block</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
