import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import type { Automation } from "@/api/automations";
import type { BlockDocument } from "@/api/block-documents";
import type { BlockType } from "@/api/block-types";
import type { Deployment } from "@/api/deployments";
import type { Flow } from "@/api/flows";
import type { WorkPool } from "@/api/work-pools";
import type { WorkQueue } from "@/api/work-queues";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeBlockType,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { ActionsStep } from "./actions-step";

const ActionStepFormContainer = () => {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: { actions: [{ type: "cancel-flow-run" }] },
	});

	return (
		<Form {...form}>
			<form>
				<ActionsStep />
			</form>
		</Form>
	);
};

describe("ActionsStep", () => {
	beforeAll(mockPointerEvents);

	describe("multiple actions", () => {
		it("able to add multiple actions", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);
			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /add action/i }));
			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
			expect(screen.getByText(/action 1/i)).toBeVisible();
			expect(screen.getByText(/action 2/i)).toBeVisible();
		});

		it("able to remove an action actions", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);
			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /add action/i }));

			await user.click(
				screen.getByRole("button", { name: /remove action 2/i }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
			expect(screen.getByText(/action 1/i)).toBeVisible();
			expect(screen.queryByText(/action 2/i)).not.toBeInTheDocument();
		});
	});

	describe("multiple actions", () => {
		it("able to add multiple actions", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);
			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /add action/i }));
			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
			expect(screen.getByText(/action 1/i)).toBeVisible();
			expect(screen.getByText(/action 2/i)).toBeVisible();
		});

		it("able to remove an action actions", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);
			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /add action/i }));

			await user.click(
				screen.getByRole("button", { name: /remove action 2/i }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
			expect(screen.getByText(/action 1/i)).toBeVisible();
			expect(screen.queryByText(/action 2/i)).not.toBeInTheDocument();
		});
	});

	describe("action type -- basic action", () => {
		it("able to select a basic action", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
		});
	});

	describe("action type -- change flow run state ", () => {
		it("able to configure change flow run's state action", async () => {
			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Change flow run's state" }),
			);

			await user.click(screen.getByRole("combobox", { name: /select state/i }));
			await user.click(screen.getByRole("option", { name: "Failed" }));
			await user.type(screen.getByPlaceholderText("Failed"), "test name");
			await user.type(screen.getByLabelText("Message"), "test message");

			// ------------ Assert
			expect(screen.getAllByText("Change flow run's state")).toBeTruthy();
			expect(screen.getAllByText("Failed")).toBeTruthy();
			expect(screen.getByLabelText("Name")).toHaveValue("test name");
			expect(screen.getByLabelText("Message")).toHaveValue("test message");
		});
	});

	describe("action type -- automation", () => {
		const mockListAutomationsAPI = (automations: Array<Automation>) => {
			server.use(
				http.post(buildApiUrl("/automations/filter"), () => {
					return HttpResponse.json(automations);
				}),
			);
		};

		it("able to configure pause an automation action type", async () => {
			mockListAutomationsAPI([
				createFakeAutomation({ name: "my automation 0" }),
				createFakeAutomation({ name: "my automation 1" }),
			]);

			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Pause an automation" }),
			);

			expect(screen.getAllByText("Infer Automation")).toBeTruthy();
			await user.click(screen.getByLabelText(/select automation to pause/i));

			await user.click(screen.getByRole("option", { name: "my automation 0" }));
			// ------------ Assert
			expect(screen.getAllByText("Pause an automation")).toBeTruthy();
			expect(screen.getAllByText("my automation 0")).toBeTruthy();
		});

		it("able to configure resume an automation action type", async () => {
			mockListAutomationsAPI([
				createFakeAutomation({ name: "my automation 0" }),
				createFakeAutomation({ name: "my automation 1" }),
			]);
			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Resume an automation" }),
			);

			expect(screen.getAllByText("Infer Automation")).toBeTruthy();
			await user.click(screen.getByLabelText(/select automation to resume/i));

			await user.click(screen.getByRole("option", { name: "my automation 1" }));

			// ------------ Assert
			expect(screen.getAllByText("Pause an automation")).toBeTruthy();
			expect(screen.getAllByText("my automation 1")).toBeTruthy();
		});
	});

	describe("action type -- deployments", () => {
		const mockPaginateDeploymentsAPI = (deployments: Array<Deployment>) => {
			server.use(
				http.post(buildApiUrl("/deployments/paginate"), () => {
					return HttpResponse.json({
						results: deployments,
						count: deployments.length,
						page: 1,
						pages: 1,
						limit: 10,
					});
				}),
			);
		};
		const mockListFlowsAPI = (flows: Array<Flow>) => {
			server.use(
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(flows);
				}),
			);
		};

		it("able to configure pause a deployment action type", async () => {
			const DEPLOYMENTS_DATA = [
				createFakeDeployment({ name: "my deployment 0", flow_id: "a" }),
				createFakeDeployment({ name: "my deployment 1", flow_id: "a" }),
			];
			const FLOWS_DATA = [createFakeFlow({ id: "a" })];

			mockPaginateDeploymentsAPI(DEPLOYMENTS_DATA);
			mockListFlowsAPI(FLOWS_DATA);

			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Pause a deployment" }),
			);

			expect(screen.getAllByText("Infer Deployment")).toBeTruthy();
			await user.click(screen.getByLabelText(/select deployment to pause/i));

			await user.click(screen.getByRole("option", { name: "my deployment 0" }));
			// ------------ Assert
			expect(screen.getAllByText("Pause a deployment")).toBeTruthy();
			expect(screen.getAllByText("my deployment 0")).toBeTruthy();
		});

		it("able to configure resume a deployment action type", async () => {
			const DEPLOYMENTS_DATA = [
				createFakeDeployment({ name: "my deployment 0", flow_id: "a" }),
				createFakeDeployment({ name: "my deployment 1", flow_id: "a" }),
			];
			const FLOWS_DATA = [createFakeFlow({ id: "a" })];

			mockPaginateDeploymentsAPI(DEPLOYMENTS_DATA);
			mockListFlowsAPI(FLOWS_DATA);
			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Resume a deployment" }),
			);

			expect(screen.getAllByText("Infer Deployment")).toBeTruthy();
			await user.click(screen.getByLabelText(/select deployment to resume/i));

			await user.click(screen.getByRole("option", { name: "my deployment 1" }));

			// ------------ Assert
			expect(screen.getAllByText("Pause a deployment")).toBeTruthy();
			expect(screen.getAllByText("my deployment 1")).toBeTruthy();
		});

		it.todo("able to configure run a deployment action type", async () => {});
	});

	describe("action type -- work pools", () => {
		const mockListWorkPoolsAPI = (workPools: Array<WorkPool>) => {
			server.use(
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(workPools);
				}),
			);
		};

		it("able to configure pause a work pool action type", async () => {
			mockListWorkPoolsAPI([
				createFakeWorkPool({ name: "my work pool 0" }),
				createFakeWorkPool({ name: "my work pool 1" }),
			]);

			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Pause a work pool" }),
			);

			expect(screen.getAllByText("Infer Work Pool")).toBeTruthy();
			await user.click(screen.getByLabelText(/select work pool to pause/i));

			await user.click(screen.getByRole("option", { name: "my work pool 0" }));
			// ------------ Assert
			expect(screen.getAllByText("Pause a work pool")).toBeTruthy();
			expect(screen.getAllByText("my work pool 0")).toBeTruthy();
		});

		it("able to configure resume a work pool action type", async () => {
			mockListWorkPoolsAPI([
				createFakeWorkPool({ name: "my work pool 0" }),
				createFakeWorkPool({ name: "my work pool 1" }),
			]);
			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Resume a work pool" }),
			);

			expect(screen.getAllByText("Infer Work Pool")).toBeTruthy();
			await user.click(screen.getByLabelText(/select work pool to resume/i));

			await user.click(screen.getByRole("option", { name: "my work pool 1" }));

			// ------------ Assert
			expect(screen.getAllByText("Pause a work pool")).toBeTruthy();
			expect(screen.getAllByText("my work pool 1")).toBeTruthy();
		});
	});

	describe("action type -- work queues", () => {
		const mockListWorkQueuesAPI = (workQueues: Array<WorkQueue>) => {
			server.use(
				http.post(buildApiUrl("/work_queues/filter"), () => {
					return HttpResponse.json(workQueues);
				}),
			);
		};

		it("able to configure pause a work queue action type", async () => {
			mockListWorkQueuesAPI([
				createFakeWorkQueue({
					name: "my work queue 0",
					work_pool_name: "Work Pool A",
				}),
				createFakeWorkQueue({
					name: "my work queue 1",
					work_pool_name: "Work Pool A",
				}),
			]);

			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Pause a work queue" }),
			);

			expect(screen.getAllByText("Infer Work Queue")).toBeTruthy();
			await user.click(screen.getByLabelText(/select work queue to pause/i));

			expect(screen.getByText("Work Pool A")).toBeVisible();
			await user.click(screen.getByRole("option", { name: "my work queue 0" }));
			// ------------ Assert
			expect(screen.getAllByText("Pause a work queue")).toBeTruthy();
			expect(screen.getAllByText("my work queue 0")).toBeTruthy();
		});

		it("able to configure resume a work queue action type", async () => {
			mockListWorkQueuesAPI([
				createFakeWorkQueue({
					name: "my work queue 0",
					work_pool_name: "Work Pool A",
				}),
				createFakeWorkQueue({
					name: "my work queue 1",
					work_pool_name: "Work Pool A",
				}),
			]);
			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Resume a work queue" }),
			);

			expect(screen.getAllByText("Infer Work Queue")).toBeTruthy();
			await user.click(screen.getByLabelText(/select work queue to resume/i));

			expect(screen.getByText("Work Pool A")).toBeVisible();
			await user.click(screen.getByRole("option", { name: "my work queue 1" }));

			// ------------ Assert
			expect(screen.getAllByText("Pause a work queue")).toBeTruthy();
			expect(screen.getAllByText("my work queue 1")).toBeTruthy();
		});
	});

	describe("action type -- send notification", () => {
		const SLACK_BLOCK_TYPE_ID = "slack-block-type-id";
		const EMAIL_BLOCK_TYPE_ID = "email-block-type-id";

		const mockBlockTypesAPI = (blockTypes: Array<BlockType>) => {
			server.use(
				http.post(buildApiUrl("/block_types/filter"), () => {
					return HttpResponse.json(blockTypes);
				}),
			);
		};

		const mockBlockDocumentsAPI = (blockDocuments: Array<BlockDocument>) => {
			server.use(
				http.post(buildApiUrl("/block_documents/filter"), () => {
					return HttpResponse.json(blockDocuments);
				}),
			);
		};

		const mockTemplateValidationAPI = (valid: boolean, error?: string) => {
			server.use(
				http.post(buildApiUrl("/automations/templates/validate"), () => {
					if (valid) {
						return HttpResponse.json(null, { status: 204 });
					}
					return HttpResponse.json(
						{
							error: {
								line: 1,
								message: error ?? "Invalid template",
								source: "",
							},
						},
						{ status: 422 },
					);
				}),
			);
		};

		it("able to configure send notification action type", async () => {
			const blockTypes = [
				createFakeBlockType({
					id: SLACK_BLOCK_TYPE_ID,
					name: "Slack Webhook",
					slug: "slack-webhook",
				}),
				createFakeBlockType({
					id: EMAIL_BLOCK_TYPE_ID,
					name: "Email Server Credentials",
					slug: "email-server-credentials",
				}),
			];

			const blockDocuments = [
				createFakeBlockDocument({
					name: "my-slack-block",
					block_type_id: SLACK_BLOCK_TYPE_ID,
				}),
				createFakeBlockDocument({
					name: "my-email-block",
					block_type_id: EMAIL_BLOCK_TYPE_ID,
				}),
			];

			mockBlockTypesAPI(blockTypes);
			mockBlockDocumentsAPI(blockDocuments);
			mockTemplateValidationAPI(true);

			const user = userEvent.setup();

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Send a notification" }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Send a notification")).toBeTruthy();
			expect(screen.getByLabelText(/select notification block/i)).toBeVisible();
			expect(screen.getByLabelText("Subject")).toBeVisible();
			expect(screen.getByLabelText("Body")).toBeVisible();
			expect(
				screen.getByText(
					/the following objects can be used in notification templates/i,
				),
			).toBeVisible();
		});

		it.todo("able to select a notification block");

		it("able to enter subject and body", async () => {
			const blockTypes = [
				createFakeBlockType({
					id: SLACK_BLOCK_TYPE_ID,
					name: "Slack Webhook",
					slug: "slack-webhook",
				}),
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

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Send a notification" }),
			);

			await user.type(screen.getByLabelText("Subject"), "Test Subject");
			await user.type(screen.getByLabelText("Body"), "Test Body");

			// ------------ Assert
			expect(screen.getByLabelText("Subject")).toHaveValue("Test Subject");
			expect(screen.getByLabelText("Body")).toHaveValue("Test Body");
		});

		it("displays info message about template variables", async () => {
			const blockTypes = [
				createFakeBlockType({
					id: SLACK_BLOCK_TYPE_ID,
					name: "Slack Webhook",
					slug: "slack-webhook",
				}),
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

			// ------------ Setup
			render(<ActionStepFormContainer />, {
				wrapper: createWrapper(),
			});

			const user = userEvent.setup();

			// ------------ Act
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Send a notification" }),
			);

			// ------------ Assert
			expect(screen.getByText("flow", { selector: "code" })).toBeVisible();
			expect(
				screen.getByText("deployment", { selector: "code" }),
			).toBeVisible();
			expect(screen.getByText("flow_run", { selector: "code" })).toBeVisible();
			expect(screen.getByText("work_pool", { selector: "code" })).toBeVisible();
			expect(
				screen.getByText("work_queue", { selector: "code" }),
			).toBeVisible();
			expect(screen.getByText("metric", { selector: "code" })).toBeVisible();
		});
	});

	describe("action type -- flow run actions", () => {
		it("displays description for suspend flow run action", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Suspend a flow run" }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Suspend a flow run")).toBeTruthy();
			expect(
				screen.getByText("Suspend flow run inferred from the triggering event"),
			).toBeVisible();
		});

		it("displays description for cancel flow run action", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
			expect(
				screen.getByText("Cancel flow run inferred from the triggering event"),
			).toBeVisible();
		});

		it("displays description for resume flow run action", async () => {
			const user = userEvent.setup();
			// ------------ Setup
			render(<ActionStepFormContainer />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Resume a flow run" }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Resume a flow run")).toBeTruthy();
			expect(
				screen.getByText(
					"Resume a flow run inferred from the triggering event",
				),
			).toBeVisible();
		});
	});
});
