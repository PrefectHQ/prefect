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

import { SendNotificationFields } from "./send-notification-fields";

// Simple schema for testing
const testSchema = z.object({
	actions: z.array(
		z.object({
			type: z.literal("send-notification"),
			block_document_id: z.string().optional(),
			subject: z.string().optional(),
			body: z.string().optional(),
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
					type: "send-notification",
					block_document_id: undefined,
					subject: "",
					body: "",
				},
			],
		},
	});

	return (
		<Form {...form}>
			<form>
				<SendNotificationFields index={0} />
			</form>
		</Form>
	);
};

describe("SendNotificationFields", () => {
	const SLACK_BLOCK_TYPE_ID = "slack-block-type-id";

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

	it("renders block selector, subject, and body fields", () => {
		const blockTypes = [
			{ id: SLACK_BLOCK_TYPE_ID, name: "Slack Webhook", slug: "slack-webhook" },
		];
		const blockDocuments = [
			createFakeBlockDocument({
				name: "my-slack-block",
				block_type_id: SLACK_BLOCK_TYPE_ID,
			}),
		];

		mockBlockTypesAPI(blockTypes);
		mockBlockDocumentsAPI(blockDocuments);
		mockTemplateValidationAPI(true);

		render(<TestFormContainer />, { wrapper: createWrapper() });

		// Check that the block selector is rendered
		expect(
			screen.getByLabelText(/select notification block/i),
		).toBeInTheDocument();

		// Check that subject and body fields are rendered
		expect(screen.getByLabelText(/subject/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/body/i)).toBeInTheDocument();
	});

	it("displays info message about template variables", () => {
		mockBlockTypesAPI([]);
		mockBlockDocumentsAPI([]);
		mockTemplateValidationAPI(true);

		render(<TestFormContainer />, { wrapper: createWrapper() });

		expect(
			screen.getByText(
				/the following objects can be used in notification templates/i,
			),
		).toBeInTheDocument();

		// Check that template variable names are displayed
		expect(screen.getByText("flow")).toBeInTheDocument();
		expect(screen.getByText("deployment")).toBeInTheDocument();
		expect(screen.getByText("flow_run")).toBeInTheDocument();
		expect(screen.getByText("work_pool")).toBeInTheDocument();
		expect(screen.getByText("work_queue")).toBeInTheDocument();
		expect(screen.getByText("metric")).toBeInTheDocument();
	});

	it("allows entering subject and body text", async () => {
		mockBlockTypesAPI([]);
		mockBlockDocumentsAPI([]);
		mockTemplateValidationAPI(true);

		const user = userEvent.setup();

		render(<TestFormContainer />, { wrapper: createWrapper() });

		const subjectInput = screen.getByLabelText(/subject/i);
		const bodyInput = screen.getByLabelText(/body/i);

		await user.type(subjectInput, "Test Subject");
		await user.type(bodyInput, "Test Body");

		expect(subjectInput).toHaveValue("Test Subject");
		expect(bodyInput).toHaveValue("Test Body");
	});

	it("opens block selector dropdown when clicked", async () => {
		mockPointerEvents();

		const blockTypes = [
			{ id: SLACK_BLOCK_TYPE_ID, name: "Slack Webhook", slug: "slack-webhook" },
		];
		const blockDocuments = [
			createFakeBlockDocument({
				name: "my-slack-block",
				block_type_id: SLACK_BLOCK_TYPE_ID,
			}),
		];

		mockBlockTypesAPI(blockTypes);
		mockBlockDocumentsAPI(blockDocuments);
		mockTemplateValidationAPI(true);

		const user = userEvent.setup();

		render(<TestFormContainer />, { wrapper: createWrapper() });

		const blockSelector = screen.getByLabelText(/select notification block/i);
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

		const subjectInput = screen.getByLabelText(/subject/i);
		await user.type(subjectInput, "{{ invalid }");

		// Wait for debounced validation to trigger and error to appear
		// The debounce delay is 1000ms, so we wait for the error message
		expect(
			await screen.findByText(/error on line 1/i, {}, { timeout: 3000 }),
		).toBeInTheDocument();
	});
});
