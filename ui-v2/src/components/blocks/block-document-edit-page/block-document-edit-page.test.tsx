import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeBlockDocument } from "@/mocks";
import { BlockDocumentEditPage } from "./block-document-edit-page";

vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		useNavigate: () => vi.fn(),
		Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
	};
});

vi.mock("@/api/block-documents", () => ({
	useUpdateBlockDocument: () => ({
		updateBlockDocument: vi.fn(),
		isPending: false,
	}),
}));

vi.mock("@/components/schemas", () => ({
	useSchemaForm: () => ({
		values: {},
		setValues: vi.fn(),
		errors: [],
		validateForm: vi.fn().mockResolvedValue(undefined),
	}),
	LazySchemaForm: () => <div data-testid="schema-form" />,
}));

vi.mock("./block-document-edit-page-header", () => ({
	BlockDocumentEditPageHeader: () => (
		<div data-testid="block-document-edit-page-header" />
	),
}));

describe("BlockDocumentEditPage", () => {
	const renderPage = (name: string | null = "my-block") => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});
		const blockDocument = createFakeBlockDocument({
			id: "block-doc-1",
			name,
		});
		return render(
			<QueryClientProvider client={queryClient}>
				<BlockDocumentEditPage blockDocument={blockDocument} />
			</QueryClientProvider>,
		);
	};

	it("renders the block name as a disabled field with an explanatory description", () => {
		renderPage("my-block");

		const nameInput = screen.getByLabelText("Block Name");
		expect(nameInput).toBeDisabled();
		expect(nameInput).toHaveValue("my-block");
		expect(
			screen.getByText("Block names are not editable"),
		).toBeInTheDocument();
	});
});
