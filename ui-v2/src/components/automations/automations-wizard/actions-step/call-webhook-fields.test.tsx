import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { Form } from "@/components/ui/form";
import { createFakeBlockDocument } from "@/mocks";

import { CallWebhookFields } from "./call-webhook-fields";

// Simple schema for testing
const testSchema = z.object({
	actions: z.array(
		z.object({
			type: z.literal("call-webhook"),
			block_document_id: z.string().optional(),
			payload: z.string().optional(),
		}),
	),
});

type TestSchema = z.infer<typeof testSchema>;

const TestFormContainer = () => {
	const form = useForm<TestSchema>({
		resolver: zodResolver(testSchema),
		defaultValues: {
			actions: [
				{
					type: "call-webhook",
					block_document_id: undefined,
					payload: "",
				},
			],
		},
	});

	return (
		<Form {...form}>
			<form>
				<CallWebhookFields index={0} />
			</form>
		</Form>
	);
};

describe("CallWebhookFields", () => {
	const WEBHOOK_BLOCK_TYPE_ID = "webhook-block-type-id";

	const mockBlockTypesAPI = (
		blockTypes: Array<{ id: string; name: string; slug: string }>,
	) => {
		server.use(
			http.post(buildApiUrl("/block_types/filter"), () => {
				return HttpResponse.json(blockTypes);
			}),
		);
	};

	const mockBlockDocumentsAPI = (
		blockDocuments: ReturnType<typeof createFakeBlockDocument>[],
	) => {
		server.use(
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blockDocuments);
			}),
		);
	};

	const mockTemplateValidationAPI = (isValid: boolean) => {
		server.use(
			http.post(buildApiUrl("/automations/templates/validate"), () => {
				if (isValid) {
					return new HttpResponse(null, { status: 204 });
				}
				return HttpResponse.json(
					{
						error: {
							line: 1,
							message: "Invalid template syntax",
							source: "test",
						},
					},
					{ status: 422 },
				);
			}),
		);
	};

	it("renders block selector and payload fields", () => {
		const blockTypes = [
			{ id: WEBHOOK_BLOCK_TYPE_ID, name: "Webhook", slug: "webhook" },
		];
		const blockDocuments = [
			createFakeBlockDocument({
				name: "my-webhook-block",
				block_type_id: WEBHOOK_BLOCK_TYPE_ID,
			}),
		];

		mockBlockTypesAPI(blockTypes);
		mockBlockDocumentsAPI(blockDocuments);
		mockTemplateValidationAPI(true);

		render(<TestFormContainer />, { wrapper: createWrapper() });

		// Check that the block selector is rendered
		expect(screen.getByLabelText(/select webhook block/i)).toBeInTheDocument();

		// Check that payload field is rendered
		expect(screen.getByLabelText(/payload/i)).toBeInTheDocument();
	});

	it("displays info message about template variables", () => {
		mockBlockTypesAPI([]);
		mockBlockDocumentsAPI([]);
		mockTemplateValidationAPI(true);

		render(<TestFormContainer />, { wrapper: createWrapper() });

		expect(
			screen.getByText(
				/the following objects can be used in webhook payload templates/i,
			),
		).toBeInTheDocument();

		// Check that template variable names are displayed
		expect(screen.getByText("flow")).toBeInTheDocument();
		expect(screen.getByText("deployment")).toBeInTheDocument();
		expect(screen.getByText("flow_run")).toBeInTheDocument();
		expect(screen.getByText("work_pool")).toBeInTheDocument();
		expect(screen.getByText("work_queue")).toBeInTheDocument();
	});

	it("allows entering payload text", async () => {
		mockBlockTypesAPI([]);
		mockBlockDocumentsAPI([]);
		mockTemplateValidationAPI(true);

		const user = userEvent.setup();

		render(<TestFormContainer />, { wrapper: createWrapper() });

		const payloadInput = screen.getByLabelText(/payload/i);

		await user.type(payloadInput, "Test Payload Content");

		expect(payloadInput).toHaveValue("Test Payload Content");
	});

	it("opens block selector dropdown when clicked", async () => {
		mockPointerEvents();

		const blockTypes = [
			{ id: WEBHOOK_BLOCK_TYPE_ID, name: "Webhook", slug: "webhook" },
		];
		const blockDocuments = [
			createFakeBlockDocument({
				name: "my-webhook-block",
				block_type_id: WEBHOOK_BLOCK_TYPE_ID,
			}),
		];

		mockBlockTypesAPI(blockTypes);
		mockBlockDocumentsAPI(blockDocuments);
		mockTemplateValidationAPI(true);

		const user = userEvent.setup();

		render(<TestFormContainer />, { wrapper: createWrapper() });

		const blockSelector = screen.getByLabelText(/select webhook block/i);
		await user.click(blockSelector);

		// Check that the search input appears
		expect(
			screen.getByPlaceholderText(/search for a block/i),
		).toBeInTheDocument();
	});

	it("validates template and shows error for invalid Jinja syntax", async () => {
		mockBlockTypesAPI([]);
		mockBlockDocumentsAPI([]);
		mockTemplateValidationAPI(false);

		const user = userEvent.setup();

		render(<TestFormContainer />, { wrapper: createWrapper() });

		const payloadInput = screen.getByLabelText(/payload/i);
		await user.type(payloadInput, "{{ invalid }");

		// Wait for debounced validation to trigger and error to appear
		// The debounce delay is 1000ms, so we wait for the error message
		expect(
			await screen.findByText(/error on line 1/i, {}, { timeout: 3000 }),
		).toBeInTheDocument();
	});
});
