import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks/catalog_/$name_/create")({
	component: RouteComponent,
});

function RouteComponent() {
	return "Hello /blocks/catalog_/$name_/create!";
}
