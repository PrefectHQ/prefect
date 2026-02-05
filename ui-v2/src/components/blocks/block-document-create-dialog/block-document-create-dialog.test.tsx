import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { BLOCK_SCHEMAS, createFakeBlockType } from "@/mocks";
import { BlockDocumentCreateDialog } from "./block-document-create-dialog";

describe("BlockDocumentCreateDialog", () => {
	const mockBlockType = createFakeBlockType({
		id: "block-type-1",
		slug: "aws-credentials",
		name: "AWS Credentials",
	});

	// Use a specific AWS credentials schema instead of a random one to avoid
	// flaky tests caused by schema/block-type mismatches
	const awsCredentialsSchema = BLOCK_SCHEMAS.find(
		(schema) => schema.fields?.block_type_slug === "aws-credentials",
	);
	if (!awsCredentialsSchema) {
		throw new Error("AWS credentials schema not found in BLOCK_SCHEMAS");
	}
	const mockBlockSchema = awsCredentialsSchema;

	const setupMocks = () => {
		server.use(
			http.get(buildApiUrl("/block_types/slug/:slug"), () => {
				return HttpResponse.json(mockBlockType);
			}),
			http.post(buildApiUrl("/block_schemas/filter"), () => {
				return HttpResponse.json([
					{ ...mockBlockSchema, block_type_id: mockBlockType.id },
				]);
			}),
			http.post(buildApiUrl("/block_documents/"), () => {
				return HttpResponse.json({
					id: "new-block-document-id",
					name: "test-block",
				});
			}),
		);
	};

	it("renders the dialog when open", async () => {
		setupMocks();

		render(
			<BlockDocumentCreateDialog
				open={true}
				onOpenChange={vi.fn()}
				blockTypeSlug="aws-credentials"
				onCreated={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByText("Create New Block")).toBeVisible(),
		);
	});

	it("does not render when closed", () => {
		setupMocks();

		render(
			<BlockDocumentCreateDialog
				open={false}
				onOpenChange={vi.fn()}
				blockTypeSlug="aws-credentials"
				onCreated={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.queryByText("Create New Block")).not.toBeInTheDocument();
	});

	it("calls onOpenChange when cancel is clicked", async () => {
		setupMocks();
		const mockOnOpenChange = vi.fn();
		const user = userEvent.setup();

		render(
			<BlockDocumentCreateDialog
				open={true}
				onOpenChange={mockOnOpenChange}
				blockTypeSlug="aws-credentials"
				onCreated={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByRole("button", { name: /cancel/i })).toBeVisible(),
		);

		await user.click(screen.getByRole("button", { name: /cancel/i }));

		expect(mockOnOpenChange).toHaveBeenCalledWith(false);
	});

	it("shows name input field", async () => {
		setupMocks();

		render(
			<BlockDocumentCreateDialog
				open={true}
				onOpenChange={vi.fn()}
				blockTypeSlug="aws-credentials"
				onCreated={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => expect(screen.getByLabelText("Name")).toBeVisible());
	});
});
