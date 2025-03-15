import { BlockTypesMultiSelect } from "@/components/blocks/block-types-multi-select";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks")({
	component: RouteComponent,
});

function RouteComponent() {
	return <BlockTypesMultiSelect />;

	return "🚧🚧 Pardon our dust! 🚧🚧";
}
