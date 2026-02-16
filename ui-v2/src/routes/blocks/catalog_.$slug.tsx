import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { BlockTypePage } from "@/components/blocks/block-type-page";
import { PrefectLoading } from "@/components/ui/loading";

export const Route = createFileRoute("/blocks/catalog_/$slug")({
	component: function RouteComponent() {
		const { slug } = Route.useParams();
		const { data: blockType } = useSuspenseQuery(buildGetBlockTypeQuery(slug));
		return <BlockTypePage blockType={blockType} />;
	},
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockTypeQuery(params.slug)),
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
