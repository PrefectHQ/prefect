import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeArtifact } from "@/mocks";
import {
	ArtifactDetailPage,
	type ArtifactDetailPageProps,
} from "./artifact-detail-page";

// Wraps component in test with a Tanstack router provider
const ArtifactDetailPageRouter = (props: ArtifactDetailPageProps) => {
	const rootRoute = createRootRoute({
		component: () => <ArtifactDetailPage {...props} />,
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

describe("ArtifactDetailPage", () => {
	beforeEach(() => {
		// Mocks away getRouteApi dependency in ArtifactDetailTabs
		// @ts-expect-error Ignoring error until @tanstack/react-router has better testing documentation. Ref: https://vitest.dev/api/vi.html#vi-mock
		vi.mock(import("@tanstack/react-router"), async (importOriginal) => {
			const mod = await importOriginal();
			return {
				...mod,
				getRouteApi: () => ({
					useSearch: () => ({ tab: "Artifact" }),
				}),
			};
		});
	});

	it("renders artifact detail for markdown", async () => {
		const artifact = createFakeArtifact({
			type: "markdown",
			data: "# Title\n\nThis is a test markdown",
		});

		await waitFor(() =>
			render(<ArtifactDetailPageRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByTestId("markdown-display")).toBeTruthy();
	});

	it("renders artifact detail for image", async () => {
		const url = "https://example.com/image.png";
		const artifact = createFakeArtifact({
			type: "image",
			data: url,
		});

		await waitFor(() =>
			render(<ArtifactDetailPageRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByTestId(url)).toBeTruthy();
	});

	it("renders artifact detail for progress", async () => {
		const artifact = createFakeArtifact({
			type: "progress",
			data: 50,
		});

		await waitFor(() =>
			render(<ArtifactDetailPageRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByTestId("progress-display")).toBeTruthy();
	});

	it("renders artifact detail for table with data", async () => {
		const artifact = createFakeArtifact({
			type: "table",
			data: JSON.stringify([
				{ key: "key1", value: "value1" },
				{ key: "key2", value: "value2" },
			]),
		});

		await waitFor(() =>
			render(<ArtifactDetailPageRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByTestId("table-display")).toBeTruthy();
	});

	it("renders artifact detail for link as markdown", async () => {
		const artifact = createFakeArtifact({
			type: "link",
			data: "[test](https://example.com)",
		});

		await waitFor(() =>
			render(<ArtifactDetailPageRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByTestId("markdown-display")).toBeTruthy();
	});

	it("renders artifact detail for rich artifacts", async () => {
		const artifact = createFakeArtifact({
			type: "rich",
			data: {
				html: "<h1>Rich Artifact Content</h1>",
				sandbox: ["allow-scripts"],
			},
		});

		await waitFor(() =>
			render(<ArtifactDetailPageRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByTestId("rich-artifact-iframe")).toBeTruthy();
	});
});
