import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
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
});
