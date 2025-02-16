import { buildFilterBlockDocumentsQuery } from "@/api/block-documents";
import { BlocksDataTable } from "@/components/blocks/data-table";
import { BlocksEmptyState } from "@/components/blocks/empty-state";
import { BlocksLayout } from "@/components/blocks/layout";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";

/**
 * Schema for validating URL search parameters for the blocks page.
 * @property {string} search used to filter data table
 */
const searchParams = z.object({
	search: z.string().optional(),
});

export const Route = createFileRoute("/blocks/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	wrapInSuspense: true,
	loader: ({ context }) =>
		context.queryClient.ensureQueryData(
			buildFilterBlockDocumentsQuery(),
		),
});

function RouteComponent() {
	const { data } = useQuery(buildFilterBlockDocumentsQuery());
	
	return (
		<BlocksLayout>
			{true ? (
				<BlocksDataTable blocks={data ?? []} />
			) : (
				<BlocksEmptyState />
			)}
		</BlocksLayout>
	);
}
