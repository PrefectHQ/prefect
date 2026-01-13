import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { createFakeBlockDocument, createFakeBlockType } from "@/mocks";
import { SchemaFormInputBlockDocument } from "./schema-form-input-block-document";

describe("SchemaFormInputBlockDocument", () => {
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

	it("renders the combobox with placeholder when no value is selected", async () => {
		mockBlockDocumentsAPI([]);

		render(
			<SchemaFormInputBlockDocument
				value={undefined}
				onValueChange={vi.fn()}
				blockTypeSlug="test-block-type"
				id="test-input"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(
				screen.getByText(`Select a ${mockBlockType.name}...`),
			).toBeVisible(),
		);
	});

	it("calls onValueChange with $ref when a block document is selected", async () => {
		const mockOnValueChange = vi.fn();
		const blockDocuments = [
			createFakeBlockDocument({ name: "my-block-0" }),
			createFakeBlockDocument({ name: "my-block-1" }),
		];
		mockBlockDocumentsAPI(blockDocuments);

		const user = userEvent.setup();

		render(
			<SchemaFormInputBlockDocument
				value={undefined}
				onValueChange={mockOnValueChange}
				blockTypeSlug="test-block-type"
				id="test-input"
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

		expect(mockOnValueChange).toHaveBeenLastCalledWith({
			$ref: blockDocuments[0].id,
		});
	});

	it("displays the selected block document name", async () => {
		const blockDocuments = [
			createFakeBlockDocument({ name: "my-block-0" }),
			createFakeBlockDocument({ name: "my-block-1" }),
		];
		mockBlockDocumentsAPI(blockDocuments);

		render(
			<SchemaFormInputBlockDocument
				value={{ $ref: blockDocuments[0].id }}
				onValueChange={vi.fn()}
				blockTypeSlug="test-block-type"
				id="test-input"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => expect(screen.getByText("my-block-0")).toBeVisible());
	});
});
