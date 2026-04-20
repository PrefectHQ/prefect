import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { components } from "@/api/prefect";
import { createFakeBlockDocument } from "@/mocks";
import { BlockDocumentCombobox } from "./block-document-combobox";

describe("BlockDocumentCombobox", () => {
	beforeAll(mockPointerEvents);

	const mockListBlockDocumentsAPI = (
		blockDocuments: Array<components["schemas"]["BlockDocument"]>,
	) => {
		server.use(
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blockDocuments);
			}),
		);
	};

	it("able to select a block document", async () => {
		const mockOnSelect = vi.fn();
		const blockDocuments = [
			createFakeBlockDocument({ id: "block-1", name: "my_block_0" }),
			createFakeBlockDocument({ id: "block-2", name: "my_block_1" }),
		];
		mockListBlockDocumentsAPI(blockDocuments);

		const user = userEvent.setup();

		render(
			<BlockDocumentCombobox
				blockTypeSlug="aws-credentials"
				selectedBlockDocumentId={undefined}
				onSelect={mockOnSelect}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a block/i)).toBeVisible(),
		);

		await user.click(screen.getByLabelText(/select a block/i));
		await user.click(screen.getByRole("option", { name: "my_block_0" }));

		expect(mockOnSelect).toHaveBeenLastCalledWith("block-1");
	});

	it("has the selected value displayed", async () => {
		const blockDocuments = [
			createFakeBlockDocument({ id: "block-1", name: "my_block_0" }),
			createFakeBlockDocument({ id: "block-2", name: "my_block_1" }),
		];
		mockListBlockDocumentsAPI(blockDocuments);

		render(
			<BlockDocumentCombobox
				blockTypeSlug="aws-credentials"
				selectedBlockDocumentId="block-1"
				onSelect={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => expect(screen.getByText("my_block_0")).toBeVisible());
	});

	it("shows placeholder when no block document is selected", async () => {
		mockListBlockDocumentsAPI([]);

		render(
			<BlockDocumentCombobox
				blockTypeSlug="aws-credentials"
				selectedBlockDocumentId={undefined}
				onSelect={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByText("Select a block...")).toBeVisible(),
		);
	});

	it("shows create new button when onCreateNew is provided", async () => {
		const mockOnCreateNew = vi.fn();
		mockListBlockDocumentsAPI([]);

		const user = userEvent.setup();

		render(
			<BlockDocumentCombobox
				blockTypeSlug="aws-credentials"
				selectedBlockDocumentId={undefined}
				onSelect={vi.fn()}
				onCreateNew={mockOnCreateNew}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a block/i)).toBeVisible(),
		);

		await user.click(screen.getByLabelText(/select a block/i));
		await user.click(screen.getByRole("option", { name: /create new block/i }));

		expect(mockOnCreateNew).toHaveBeenCalled();
	});
});
