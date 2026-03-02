import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { categorizeError } from "@/api/error-utils";
import { BlockTypePage } from "@/components/blocks/block-type-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

export const Route = createFileRoute("/blocks/catalog_/$slug")({
	component: function RouteComponent() {
		const { slug } = Route.useParams();
		const { data: blockType } = useSuspenseQuery(buildGetBlockTypeQuery(slug));
		return <BlockTypePage blockType={blockType} />;
	},
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockTypeQuery(params.slug)),
	errorComponent: function BlockTypeErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load block type");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Block Type</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
