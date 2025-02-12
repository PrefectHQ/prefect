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
import {
	ArtifactDetailPage,
	ArtifactDetailPageProps,
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
	// @ts-expect-error - Type error from using a test router
	return <RouterProvider router={router} />;
};

describe("ArtifactDetailPage", () => {
	it("renders artifact detail for markdown", () => {
		const artifact = createFakeArtifact({
			type: "markdown",
			data: "# Title\n\nThis is a test markdown",
		});

		const { getByTestId } = render(
			<ArtifactDetailPageRouter artifact={artifact} />,
			{
				wrapper: createWrapper(),
			},
		);

		expect(getByTestId("markdown-display")).toBeTruthy();
	});

	it("renders artifact detail for image", () => {
		const url = "https://example.com/image.png";
		const artifact = createFakeArtifact({
			type: "image",
			data: url,
		});

		const { getByTestId } = render(
			<ArtifactDetailPageRouter artifact={artifact} />,
			{
				wrapper: createWrapper(),
			},
		);

		expect(getByTestId(url)).toBeTruthy();
	});

	it("renders artifact detail for progress", () => {
		const artifact = createFakeArtifact({
			type: "progress",
			data: 50,
		});

		const { getByTestId } = render(
			<ArtifactDetailPageRouter artifact={artifact} />,
			{
				wrapper: createWrapper(),
			},
		);

		expect(getByTestId("progress-display")).toBeTruthy();
	});

	it("renders artifact detail for table with data", () => {
		const artifact = createFakeArtifact({
			type: "table",
			data: JSON.stringify([
				{ key: "key1", value: "value1" },
				{ key: "key2", value: "value2" },
			]),
		});

		const { getByTestId } = render(
			<ArtifactDetailPageRouter artifact={artifact} />,
			{
				wrapper: createWrapper(),
			},
		);

		expect(getByTestId("table-display")).toBeTruthy();
	});

	it("renders artifact detail for link as markdown", () => {
		const artifact = createFakeArtifact({
			type: "link",
			data: "[test](https://example.com)",
		});

		const { getByTestId } = render(
			<ArtifactDetailPageRouter artifact={artifact} />,
			{
				wrapper: createWrapper(),
			},
		);

		expect(getByTestId("markdown-display")).toBeTruthy();
	});
});
