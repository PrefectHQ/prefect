import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import type { BlockDocument } from "@/api/block-documents";
import { createFakeBlockDocument } from "@/mocks";
import { BlockDocumentEditPage } from "./block-document-edit-page";

vi.mock("@/components/schemas", () => ({
	useSchemaForm: () => ({
		values: {},
		setValues: vi.fn(),
		errors: [],
		validateForm: vi.fn().mockResolvedValue(undefined),
	}),
	LazySchemaForm: () => <div data-testid="schema-form" />,
}));

const BlockDocumentEditPageRouter = ({
	blockDocument,
}: {
	blockDocument: BlockDocument;
}) => {
	const rootRoute = createRootRoute({
		component: () => <BlockDocumentEditPage blockDocument={blockDocument} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("BlockDocumentEditPage", () => {
	it("renders the block name as a disabled field with an explanatory description", async () => {
		const blockDocument = createFakeBlockDocument({
			id: "block-doc-1",
			name: "my-block",
		});

		render(<BlockDocumentEditPageRouter blockDocument={blockDocument} />, {
			wrapper: createWrapper(),
		});

		const nameInput = await screen.findByLabelText("Block Name");
		expect(nameInput).toBeDisabled();
		expect(nameInput).toHaveValue("my-block");
		await waitFor(() => {
			expect(
				screen.getByText("Block names are not editable"),
			).toBeInTheDocument();
		});
	});
});
