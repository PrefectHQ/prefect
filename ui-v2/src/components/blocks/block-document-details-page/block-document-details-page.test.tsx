import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeBlockDocument, createFakeBlockType } from "@/mocks";
import { BlockDocumentDetailsPage } from "./block-document-details-page";

vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		useNavigate: () => vi.fn(),
		useRouter: () => ({
			history: { back: vi.fn() },
		}),
	};
});

const queryClient = new QueryClient();

const renderWithProviders = (
	blockDocument: Parameters<
		typeof BlockDocumentDetailsPage
	>[0]["blockDocument"],
) =>
	render(
		<QueryClientProvider client={queryClient}>
			<BlockDocumentDetailsPage blockDocument={blockDocument} />
		</QueryClientProvider>,
	);

vi.mock("@/components/blocks/block-document-action-menu", () => ({
	BlockDocumentActionMenu: () => (
		<div data-testid="block-document-action-menu" />
	),
}));

vi.mock("@/components/blocks/block-type-details", () => ({
	BlockTypeDetails: () => <div data-testid="block-type-details" />,
}));

vi.mock("../python-example-snippet", () => ({
	PythonBlockSnippet: () => <div data-testid="python-block-snippet" />,
}));

vi.mock("./block-document-schema-properties", () => ({
	BlockDocumentSchemaProperties: () => (
		<div data-testid="block-document-schema-properties" />
	),
}));

vi.mock("./block-document-details-page-header", () => ({
	BlockDocumentDetailsPageHeader: ({ blockName }: { blockName: string }) => (
		<div data-testid="block-document-details-page-header">{blockName}</div>
	),
}));

describe("BlockDocumentDetailsPage", () => {
	it("renders the 'View Docs' link with the block type's specific documentation_url", () => {
		const blockType = createFakeBlockType({
			documentation_url:
				"https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.AwsCredentials",
			code_example: undefined,
		});
		const blockDocument = createFakeBlockDocument({
			block_type: blockType,
		});

		renderWithProviders(blockDocument);

		const docsLink = screen.getByRole("link", { name: "View Docs" });
		expect(docsLink).toHaveAttribute(
			"href",
			"https://prefecthq.github.io/prefect-aws/credentials/#prefect_aws.credentials.AwsCredentials",
		);
	});

	it("does not render the 'View Docs' link when documentation_url is null", () => {
		const blockType = createFakeBlockType({
			documentation_url: null,
			code_example: undefined,
		});
		const blockDocument = createFakeBlockDocument({
			block_type: blockType,
		});

		renderWithProviders(blockDocument);

		expect(
			screen.queryByRole("link", { name: "View Docs" }),
		).not.toBeInTheDocument();
	});

	it("renders both code example text and docs link when both are present", () => {
		const blockType = createFakeBlockType({
			documentation_url: "https://docs.prefect.io/some-block-type",
			code_example: "```python\nfrom prefect import Block\n```",
		});
		const blockDocument = createFakeBlockDocument({
			block_type: blockType,
		});

		renderWithProviders(blockDocument);

		expect(screen.getByText(/Paste this snippet/)).toBeInTheDocument();
		const docsLink = screen.getByRole("link", { name: "View Docs" });
		expect(docsLink).toHaveAttribute(
			"href",
			"https://docs.prefect.io/some-block-type",
		);
	});

	it("does not render help section when block type has neither docs url nor code example", () => {
		const blockType = createFakeBlockType({
			documentation_url: null,
			code_example: undefined,
		});
		const blockDocument = createFakeBlockDocument({
			block_type: blockType,
		});

		renderWithProviders(blockDocument);

		expect(screen.queryByText(/Need help/)).not.toBeInTheDocument();
		expect(screen.queryByText(/Paste this snippet/)).not.toBeInTheDocument();
	});
});
