import { createFileRoute } from "@tanstack/react-router";
import {
	useBlockDocument,
	buildBlockDocumentQuery,
} from "@/hooks/use-block-documents";

function RouteComponent() {
	const { id } = Route.useParams();
	const { data: block } = useBlockDocument(id);

	return (
		<div>
			<h2>Block ID: {id}</h2>
			<pre>{JSON.stringify(block, null, 2)}</pre>
		</div>
	);
}

export const Route = createFileRoute("/blocks/$id")({
	component: RouteComponent,
	loader: ({ context, params }) => {
		return context.queryClient.ensureQueryData(
			buildBlockDocumentQuery(params.id),
		);
	},
	wrapInSuspense: true,
});
