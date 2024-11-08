import { VariablesPage } from "@/components/variables/page";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/variables")({
	component: VariablesRoute,
});

function VariablesRoute() {
	// TODO: Add call for existing variables
	return <VariablesPage />;
}
