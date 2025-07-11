import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockDocumentQuery } from "@/api/block-documents";
import { BlockDocumentDetailsPage } from "@/components/blocks/block-document-details-page/block-document-details-page";

export const Route = createFileRoute("/blocks/block/$id")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockDocumentQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	const { data } = useSuspenseQuery(buildGetBlockDocumentQuery(id));
	return <BlockDocumentDetailsPage blockDocument={data} />;
}
