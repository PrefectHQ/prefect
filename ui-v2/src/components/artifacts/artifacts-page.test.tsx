import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { ArtifactsPage, type ArtifactsPageProps } from "./artifacts-page";

// Wraps component in test with a Tanstack router provider
const ArtifactsPageRouter = (props: ArtifactsPageProps) => {
	const rootRoute = createRootRoute({
		component: () => <ArtifactsPage {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("Artifacts Page", () => {
	const defaultCount = 2;
	const defaultArtifacts = Array.from(
		{ length: defaultCount },
		createFakeArtifact,
	);
	const defaultFilters = [
		{ id: "type", label: "Type", value: "all" },
		{ id: "name", label: "Name", value: "" },
	];
	const onFilterChange = vi.fn();

	it("renders filter", () => {
		const { findByTestId } = render(
			<ArtifactsPageRouter
				filters={defaultFilters}
				onFilterChange={onFilterChange}
				artifactsCount={defaultCount}
				artifactsList={defaultArtifacts}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(findByTestId("artifact-filter")).toBeTruthy();
		expect("Artifacts").toBeTruthy();
	});
});
