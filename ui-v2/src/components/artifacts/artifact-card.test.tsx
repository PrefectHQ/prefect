import type { Artifact } from "@/api/artifacts";
import { createFakeArtifact } from "@/mocks";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { ArtifactCard, type ArtifactsCardProps } from "./artifact-card";

// Wraps component in test with a Tanstack router provider
const ArtifactsCardRouter = (props: ArtifactsCardProps) => {
	const rootRoute = createRootRoute({
		component: () => <ArtifactCard {...props} />,
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

describe("Artifacts Card", () => {
	it("renders artifact card with description", () => {
		const artifact: Artifact = createFakeArtifact({
			description: "This is a description",
		});
		const { getByText } = render(<ArtifactsCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("This is a description")).toBeTruthy();
	});

	it("renders artifact card with updated date", () => {
		const artifact = createFakeArtifact({
			created: "2021-09-01T12:00:00Z",
		});
		const { getByText } = render(<ArtifactsCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("Created")).toBeTruthy();
		expect(getByText("Sep 1st, 2021 at 12:00 PM")).toBeTruthy();
	});

	it("renders artifact card with key", () => {
		const artifact = createFakeArtifact({
			key: "test-key",
		});
		const { getByText } = render(<ArtifactsCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("test-key")).toBeTruthy();
	});

	it("renders artifact card with type", () => {
		const artifact = createFakeArtifact({
			type: "test-type",
		});
		const { getByText } = render(<ArtifactsCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("TEST-TYPE")).toBeTruthy();
	});
});
