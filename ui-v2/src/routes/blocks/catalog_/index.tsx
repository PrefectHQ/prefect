import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import { useBlockTypes, buildBlockTypesQuery } from "@/hooks/use-block-types";

const searchParams = z.object({});

function CatalogPage() {
	const { blockTypes } = useBlockTypes();

	return (
		<div>
			{blockTypes.map((blockType) => (
				<div key={blockType.slug}>
					<Link to="/blocks/catalog/$name" params={{ name: blockType.slug }}>
						{blockType.name}
					</Link>
				</div>
			))}
		</div>
	);
}

export const Route = createFileRoute("/blocks/catalog_/")({
	validateSearch: zodSearchValidator(searchParams),
	component: CatalogPage,
	loader: ({ context }) => {
		return context.queryClient.ensureQueryData(buildBlockTypesQuery());
	},
	wrapInSuspense: true,
});
