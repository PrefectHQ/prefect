import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { createFakeBlockDocument, createFakeBlockType } from "@/mocks";
import { BlockDocumentCombobox } from "./block-document-combobox";

describe("BlockDocumentCombobox", () => {
	beforeAll(mockPointerEvents);

	const mockBlockType = createFakeBlockType({ slug: "test-block-type" });

	const mockBlockDocumentsAPI = (
		blockDocuments: ReturnType<typeof createFakeBlockDocument>[],
	) => {
		server.use(
			http.get(buildApiUrl("/block_types/slug/:slug"), () => {
				return HttpResponse.json(mockBlockType);
			}),
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blockDocuments);
			}),
		);
	};

	it("able to select a block document", async () => {
		const mockOnSelect = vi.fn();
		const blockDocuments = [
			createFakeBlockDocument({ name: "my-block-0" }),
			createFakeBlockDocument({ name: "my-block-1" }),
		];
		mockBlockDocumentsAPI(blockDocuments);

		const user = userEvent.setup();

		render(
			<BlockDocumentCombobox
				blockTypeSlug="test-block-type"
				selectedBlockDocumentId={undefined}
				onSelect={mockOnSelect}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(
				screen.getByLabelText(`Select a ${mockBlockType.name}`),
			).toBeVisible(),
		);

		await user.click(screen.getByLabelText(`Select a ${mockBlockType.name}`));
		await user.click(screen.getByRole("option", { name: "my-block-0" }));

		expect(mockOnSelect).toHaveBeenLastCalledWith(blockDocuments[0].id);
	});

	it("has the selected value displayed", async () => {
		const blockDocuments = [
			createFakeBlockDocument({ name: "my-block-0" }),
			createFakeBlockDocument({ name: "my-block-1" }),
		];
		mockBlockDocumentsAPI(blockDocuments);

		render(
			<BlockDocumentCombobox
				blockTypeSlug="test-block-type"
				selectedBlockDocumentId={blockDocuments[0].id}
				onSelect={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => expect(screen.getByText("my-block-0")).toBeVisible());
	});

	it("shows placeholder when no block document is selected", async () => {
		mockBlockDocumentsAPI([]);

		render(
			<BlockDocumentCombobox
				blockTypeSlug="test-block-type"
				selectedBlockDocumentId={undefined}
				onSelect={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(
				screen.getByText(`Select a ${mockBlockType.name}...`),
			).toBeVisible(),
		);
	});

	it("shows create new button when onCreateNew is provided", async () => {
		const mockOnCreateNew = vi.fn();
		mockBlockDocumentsAPI([]);

		const user = userEvent.setup();

		render(
			<BlockDocumentCombobox
				blockTypeSlug="test-block-type"
				selectedBlockDocumentId={undefined}
				onSelect={vi.fn()}
				onCreateNew={mockOnCreateNew}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(
				screen.getByLabelText(`Select a ${mockBlockType.name}`),
			).toBeVisible(),
		);

		await user.click(screen.getByLabelText(`Select a ${mockBlockType.name}`));
		await user.click(
			screen.getByRole("button", { name: `Create new ${mockBlockType.name}` }),
		);

		expect(mockOnCreateNew).toHaveBeenCalled();
	});
});
