import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetBlockDocumentQuery } from "@/api/block-documents";
import { BlockDocumentEditPage } from "@/components/blocks/block-document-edit-page";

export const Route = createFileRoute("/blocks/block_/$id/edit")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildGetBlockDocumentQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	const { data } = useSuspenseQuery(buildGetBlockDocumentQuery(id));
	return <BlockDocumentEditPage blockDocument={data} />;
}
