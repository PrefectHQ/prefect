import * as React from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useBlockDocuments, buildBlockDocumentsQuery } from "@/hooks/use-block-documents";

function RouteComponent() {
	const { id } = Route.useParams();
	const { blockDocuments: [block] } = useBlockDocuments({
		blockDocuments: {
			operator: "and_", 
			is_anonymous: { eq_: false },
			id: { any_: [id] },
		},
	});

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
			buildBlockDocumentsQuery({
		blockDocuments: {
			operator: "and_", 
			is_anonymous: { eq_: false },
			id: { any_: [params.id] },
		},
			})
		);
	},
	wrapInSuspense: true,
});
