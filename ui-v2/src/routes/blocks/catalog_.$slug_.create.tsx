import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildListFilterBlockSchemasQuery } from "@/api/block-schemas";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { BlockDocumentCreatePage } from "@/components/blocks/block-document-create-page";

export const Route = createFileRoute("/blocks/catalog_/$slug_/create")({
	component: RouteComponent,
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
	wrapInSuspense: true,
});

function RouteComponent() {
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
		<BlockDocumentCreatePage blockSchema={blockSchema} blockType={blockType} />
	);
}
