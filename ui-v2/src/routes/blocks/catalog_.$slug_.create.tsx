import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildListFilterBlockSchemasQuery } from "@/api/block-schemas";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { categorizeError } from "@/api/error-utils";
import { BlockDocumentCreatePage } from "@/components/blocks/block-document-create-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

export const Route = createFileRoute("/blocks/catalog_/$slug_/create")({
	component: function RouteComponent() {
		const { slug } = Route.useParams();
		const { data: blockType } = useSuspenseQuery(buildGetBlockTypeQuery(slug));
		const { data: blockSchemas } = useSuspenseQuery(
			buildListFilterBlockSchemasQuery({
				block_schemas: {
					block_type_id: { any_: [blockType.id] },
					operator: "and_",
				},
				offset: 0,
			}),
		);
		const blockSchema = blockSchemas[0];
		if (!blockSchema) {
			throw new Error("Block schema not found");
		}

		return (
			<BlockDocumentCreatePage
				blockSchema={blockSchema}
				blockType={blockType}
			/>
		);
	},
	loader: async ({ params, context: { queryClient } }) => {
		// critical data
		const res = await queryClient.ensureQueryData(
			buildGetBlockTypeQuery(params.slug),
		);
		void queryClient.ensureQueryData(
			buildListFilterBlockSchemasQuery({
				block_schemas: {
					block_type_id: { any_: [res.id] },
					operator: "and_",
				},
				offset: 0,
			}),
		);
	},
	errorComponent: function BlockCreateErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(
			error,
			"Failed to load block creation form",
		);
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Create Block</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
