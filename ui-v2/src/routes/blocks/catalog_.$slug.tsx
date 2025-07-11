import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { BlockTypePage } from "@/components/blocks/block-type-page";

export const Route = createFileRoute("/blocks/catalog_/$slug")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockTypeQuery(params.slug)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { slug } = Route.useParams();
	const { data: blockType } = useSuspenseQuery(buildGetBlockTypeQuery(slug));
	return <BlockTypePage blockType={blockType} />;
}
