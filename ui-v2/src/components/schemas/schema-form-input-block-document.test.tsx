import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { createFakeBlockDocument } from "@/mocks";
import { SchemaFormInputBlockDocument } from "./schema-form-input-block-document";

describe("SchemaFormInputBlockDocument", () => {
	beforeAll(mockPointerEvents);

	const mockBlockDocuments = [
		createFakeBlockDocument({ id: "block-1", name: "my_block_0" }),
		createFakeBlockDocument({ id: "block-2", name: "my_block_1" }),
	];

	const setupMocks = () => {
		server.use(
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(mockBlockDocuments);
			}),
		);
	};

	it("renders the combobox", async () => {
		setupMocks();

		render(
			<SchemaFormInputBlockDocument
				value={undefined}
				onValueChange={vi.fn()}
				blockTypeSlug="aws-credentials"
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a block/i)).toBeVisible(),
		);
	});

	it("calls onValueChange with $ref when a block is selected", async () => {
		setupMocks();
		const mockOnValueChange = vi.fn();
		const user = userEvent.setup();

		render(
			<SchemaFormInputBlockDocument
				value={undefined}
				onValueChange={mockOnValueChange}
				blockTypeSlug="aws-credentials"
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a block/i)).toBeVisible(),
		);

		await user.click(screen.getByLabelText(/select a block/i));
		await user.click(screen.getByRole("option", { name: "my_block_0" }));

		expect(mockOnValueChange).toHaveBeenCalledWith({ $ref: "block-1" });
	});

	it("displays the selected block document name", async () => {
		setupMocks();

		render(
			<SchemaFormInputBlockDocument
				value={{ $ref: "block-1" }}
				onValueChange={vi.fn()}
				blockTypeSlug="aws-credentials"
				id="test-id"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => expect(screen.getByText("my_block_0")).toBeVisible());
	});
});
