import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import type { ArtifactCollection } from "@/api/artifacts";
import { createFakeArtifact, createFakeArtifactCollection } from "@/mocks";
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
	it("renders artifact card with description", async () => {
		const artifact: ArtifactCollection = createFakeArtifactCollection({
			description: "This is a description",
		});
		const { getByText } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		await waitFor(() => {
			expect(getByText("This is a description")).toBeTruthy();
		});
	});

	it("renders artifact card with updated date", async () => {
		const artifact = createFakeArtifactCollection({
			created: "2021-09-01T12:00:00Z",
		});
		const { getByText } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("Created")).toBeTruthy();
		expect(getByText("Sep 1st, 2021 at 12:00 PM")).toBeTruthy();
	});

	it("renders artifact card with key", async () => {
		const artifact = createFakeArtifactCollection({
			key: "test-key",
		});
		const { getByText } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("test-key")).toBeTruthy();
	});

	it("renders artifact card with type", async () => {
		const artifact = createFakeArtifactCollection({
			type: "test-type",
		});
		const { getByText } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("TEST-TYPE")).toBeTruthy();
	});

	it("renders artifact card with raw Artifact type", async () => {
		const artifact = createFakeArtifact({
			key: "raw-artifact-key",
			description: "A raw artifact",
		});
		const { getByText } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);
		expect(getByText("raw-artifact-key")).toBeTruthy();
	});

	it("links to artifact detail page when key is null", async () => {
		const artifact = createFakeArtifact({
			id: "null-key-artifact-id",
			key: null,
			type: "markdown",
		});
		const { container } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);
		const link = container.querySelector("a");
		expect(link).toBeTruthy();
		expect(link?.getAttribute("href")).toContain(
			"/artifacts/artifact/null-key-artifact-id",
		);
	});

	it("links to artifact detail page when key is undefined", async () => {
		const artifact = createFakeArtifact({
			id: "undef-key-artifact-id",
			key: undefined,
			type: "table",
		});
		const { container } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);
		const link = container.querySelector("a");
		expect(link).toBeTruthy();
		expect(link?.getAttribute("href")).toContain(
			"/artifacts/artifact/undef-key-artifact-id",
		);
	});

	it("links to key page when key is present", async () => {
		const artifact = createFakeArtifactCollection({
			key: "my-key",
		});
		const { container } = await waitFor(() =>
			render(<ArtifactsCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);
		const link = container.querySelector("a");
		expect(link).toBeTruthy();
		expect(link?.getAttribute("href")).toContain("/artifacts/key/my-key");
	});

	it("links to artifact detail page via latest_id for null-key collection", async () => {
		const artifact = createFakeArtifactCollection({
			latest_id: "collection-latest-id",
		});
		// Override key to empty string to test edge case
		const nullKeyArtifact = { ...artifact, key: "" };
		const { container } = await waitFor(() =>
			render(
				<ArtifactsCardRouter
					artifact={nullKeyArtifact as ArtifactCollection}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);
		const link = container.querySelector("a");
		expect(link).toBeTruthy();
		expect(link?.getAttribute("href")).toContain(
			"/artifacts/artifact/collection-latest-id",
		);
	});
});
