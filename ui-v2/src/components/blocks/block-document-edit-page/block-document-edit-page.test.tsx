import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BlockDocument } from "@/api/block-documents";
import { createFakeBlockDocument } from "@/mocks";
import { BlockDocumentEditPage } from "./block-document-edit-page";

const validateForm = vi.fn();

vi.mock("@/components/schemas", () => ({
	useSchemaForm: () => ({
		values: {},
		setValues: vi.fn(),
		errors: [],
		validateForm,
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
	beforeEach(() => {
		validateForm.mockReset();
		validateForm.mockResolvedValue({ valid: true, errors: [] });
	});

	it("does not update the block document when validation fails", async () => {
		validateForm.mockResolvedValue({
			valid: false,
			errors: [{ property: "env", errors: ["Invalid JSON"] }],
		});
		const patchHandler = vi.fn();
		server.use(
			http.patch(buildApiUrl("/block_documents/:id"), () => {
				patchHandler();
				return new HttpResponse(null, { status: 204 });
			}),
		);
		const blockDocument = createFakeBlockDocument({ id: "block-doc-1" });

		render(<BlockDocumentEditPageRouter blockDocument={blockDocument} />, {
			wrapper: createWrapper(),
		});

		fireEvent.click(await screen.findByRole("button", { name: "Save" }));

		await waitFor(() => expect(validateForm).toHaveBeenCalled());
		expect(patchHandler).not.toHaveBeenCalled();
	});

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
