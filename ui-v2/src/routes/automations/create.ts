import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";

// nb: Revisit search params to determine if we're decoding the parameters correctly. Or if there are stricter typings
// We'll know stricter types as we write more of the webapp

/**
 * Schema for validating URL search parameters for the create automation page.
 * @property actions used designate how to pre-populate the fields
 */
const searchParams = z
	.object({ actions: z.record(z.unknown()).optional() })
	.optional();

export const Route = createFileRoute("/automations/create")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
