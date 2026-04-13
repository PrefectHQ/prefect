import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BLOCK_SCHEMAS, createFakeBlockType } from "@/mocks";
import { BlockDocumentCreatePage } from "./block-document-create-page";

const mockNavigate = vi.fn();
const mockHistoryBack = vi.fn();

vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		useNavigate: () => mockNavigate,
		useRouter: () => ({
			history: {
				back: mockHistoryBack,
			},
		}),
	};
});

type CreateBlockDocumentOptions = {
	onSuccess?: (res: { id: string }) => void;
	onError?: (error: Error) => void;
};

const mockCreateBlockDocument =
	vi.fn<(data: unknown, options: CreateBlockDocumentOptions) => void>();

vi.mock("@/api/block-documents", () => ({
	useCreateBlockDocument: () => ({
		createBlockDocument: mockCreateBlockDocument,
		isPending: false,
	}),
	useBlockDocumentNameCheck: () => ({
		isNameTaken: false,
		isChecking: false,
	}),
}));

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
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

vi.mock("./block-document-create-page-header", () => ({
	BlockDocumentCreatePageHeader: () => (
		<div data-testid="block-document-create-page-header" />
	),
}));

const mockUpdateDraft = vi.fn();
const mockClearDraft = vi.fn();

vi.mock("./use-block-create-draft", () => ({
	useBlockCreateDraft: () => ({
		draft: { blockName: "", values: {} },
		updateDraft: mockUpdateDraft,
		clearDraft: mockClearDraft,
	}),
}));

describe("BlockDocumentCreatePage", () => {
	let queryClient: QueryClient;

	const mockBlockType = createFakeBlockType({
		id: "block-type-1",
		slug: "aws-credentials",
		name: "AWS Credentials",
	});

	const awsCredentialsSchema = BLOCK_SCHEMAS.find(
		(schema) => schema.fields?.block_type_slug === "aws-credentials",
	);
	if (!awsCredentialsSchema) {
		throw new Error("AWS credentials schema not found in BLOCK_SCHEMAS");
	}

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});

		vi.clearAllMocks();
		localStorage.clear();
	});

	const renderPage = (redirect?: string) => {
		return render(
			<QueryClientProvider client={queryClient}>
				<BlockDocumentCreatePage
					blockSchema={awsCredentialsSchema}
					blockType={mockBlockType}
					redirect={redirect}
				/>
			</QueryClientProvider>,
		);
	};

	it("calls router.history.back on cancel", async () => {
		const user = userEvent.setup();
		renderPage();

		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		await user.click(cancelButton);

		expect(mockHistoryBack).toHaveBeenCalled();
	});

	it("navigates to the created block on success when no redirect is provided", async () => {
		const user = userEvent.setup();

		mockCreateBlockDocument.mockImplementation((_data, options) => {
			options.onSuccess?.({ id: "new-block-id" });
		});

		renderPage();

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "my-block");

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalledWith({
				to: "/blocks/block/$id",
				params: { id: "new-block-id" },
			});
		});
	});

	it("clears draft on successful block creation", async () => {
		const user = userEvent.setup();

		mockCreateBlockDocument.mockImplementation((_data, options) => {
			options.onSuccess?.({ id: "new-block-id" });
		});

		renderPage();

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "my-block");

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(mockClearDraft).toHaveBeenCalled();
		});
	});

	it("navigates to redirect URL on success when redirect is provided", async () => {
		const user = userEvent.setup();

		mockCreateBlockDocument.mockImplementation((_data, options) => {
			options.onSuccess?.({ id: "new-block-id" });
		});

		renderPage("/deployments");

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "my-block");

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalledWith({
				to: "/deployments",
			});
		});
	});
});
