import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import {
	createFakeAutomation,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { AutomationWizard } from "./automation-wizard";

// Wraps component in test with a TanStack router provider
const AutomationWizardWithRouter = () => {
	const rootRoute = createRootRoute({
		component: () => <AutomationWizard onSubmit={() => {}} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

const setupMockAPIs = () => {
	const MOCK_AUTOMATIONS_DATA = Array.from({ length: 5 }, createFakeAutomation);
	const MOCK_DEPLOYMENTS_DATA = [
		createFakeDeployment({ flow_id: "a" }),
		createFakeDeployment({ flow_id: "b" }),
	];
	const MOCK_FLOWS_DATA = [
		createFakeFlow({ id: "a" }),
		createFakeFlow({ id: "b" }),
	];
	const MOCK_WORK_POOLS_DATA = Array.from({ length: 5 }, createFakeWorkPool);
	const MOCK_WORK_QUEUES_DATA = [
		createFakeWorkQueue({ work_pool_name: "My workpool A" }),
		createFakeWorkQueue({ work_pool_name: "My workpool B" }),
	];

	server.use(
		http.post(buildApiUrl("/automations/filter"), () => {
			return HttpResponse.json(MOCK_AUTOMATIONS_DATA);
		}),
		http.post(buildApiUrl("/deployments/paginate"), () => {
			return HttpResponse.json({
				count: MOCK_DEPLOYMENTS_DATA.length,
				limit: 100,
				page: 1,
				pages: 1,
				results: MOCK_DEPLOYMENTS_DATA,
			});
		}),
		http.post(buildApiUrl("/flows/filter"), () => {
			return HttpResponse.json(MOCK_FLOWS_DATA);
		}),
		http.post(buildApiUrl("/work_pools/filter"), () => {
			return HttpResponse.json(MOCK_WORK_POOLS_DATA);
		}),
		http.post(buildApiUrl("/work_queues/filter"), () => {
			return HttpResponse.json(MOCK_WORK_QUEUES_DATA);
		}),
	);
};

describe("AutomationWizard", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	beforeEach(() => {
		setupMockAPIs();
	});

	describe("stepper rendering", () => {
		it("renders 3 steps in the stepper (Trigger, Actions, Details)", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			expect(screen.getByRole("button", { name: /trigger/i })).toBeVisible();
			expect(screen.getByRole("button", { name: /actions/i })).toBeVisible();
			expect(screen.getByRole("button", { name: /details/i })).toBeVisible();
		});

		it("displays step numbers correctly (01, 02, 03)", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			expect(screen.getByText("01")).toBeVisible();
			expect(screen.getByText("02")).toBeVisible();
			expect(screen.getByText("03")).toBeVisible();
		});

		it("starts on the Trigger step (first step)", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Trigger step should be active (visible and styled as active)
			const triggerButton = screen.getByRole("button", { name: /trigger/i });
			expect(triggerButton).toBeVisible();

			// The TriggerStep content should be visible
			expect(screen.getByLabelText("Trigger Template")).toBeVisible();
		});

		it("shows the correct active step styling", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Trigger step should be enabled (first step is always visited)
			const triggerButton = screen.getByRole("button", { name: /trigger/i });
			expect(triggerButton).not.toBeDisabled();

			// Actions and Details steps should be disabled initially
			const actionsButton = screen.getByRole("button", { name: /actions/i });
			const detailsButton = screen.getByRole("button", { name: /details/i });
			expect(actionsButton).toBeDisabled();
			expect(detailsButton).toBeDisabled();
		});
	});

	describe("navigation buttons", () => {
		it("shows Previous button disabled on first step", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			const previousButton = screen.getByRole("button", { name: /previous/i });
			expect(previousButton).toBeDisabled();
		});

		it("shows Next button on non-final steps", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			const nextButton = screen.getByRole("button", { name: /next/i });
			expect(nextButton).toBeVisible();
		});

		it("shows Cancel button that links to automations page", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			const cancelButton = screen.getByRole("button", { name: /cancel/i });
			expect(cancelButton).toBeVisible();
			expect(within(cancelButton).getByRole("link")).toHaveAttribute(
				"href",
				"/automations",
			);
		});
	});

	describe("forward navigation (Trigger -> Actions -> Details)", () => {
		it("navigates from Trigger to Actions step when clicking Next after selecting a trigger template", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Select a trigger template first
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			// Click Next
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Should now be on Actions step
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});
		});

		it("navigates from Actions to Details step when clicking Next after selecting an action", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Actions step first
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Wait for Actions step
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			// Select an action
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);

			// Click Next
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Should now be on Details step
			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});
		});

		it("shows Save button on the final (Details) step", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Details step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Should show Save button instead of Next
			await waitFor(() => {
				expect(screen.getByRole("button", { name: /save/i })).toBeVisible();
			});
			expect(
				screen.queryByRole("button", { name: /^next$/i }),
			).not.toBeInTheDocument();
		});
	});

	describe("backward navigation", () => {
		it("navigates from Actions back to Trigger step when clicking Previous", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Actions step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Verify we're on Actions step
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			// Click Previous
			await user.click(screen.getByRole("button", { name: /previous/i }));

			// Should be back on Trigger step
			await waitFor(() => {
				expect(screen.getByLabelText("Trigger Template")).toBeVisible();
			});
		});

		it("navigates from Details back to Actions step when clicking Previous", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Details step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Verify we're on Details step
			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});

			// Click Previous
			await user.click(screen.getByRole("button", { name: /previous/i }));

			// Should be back on Actions step
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});
		});

		it("enables Previous button after navigating to second step", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Previous should be disabled on first step
			expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled();

			// Navigate to Actions step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Previous should now be enabled
			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /previous/i }),
				).not.toBeDisabled();
			});
		});
	});

	describe("stepper step clicking", () => {
		it("allows clicking on visited steps to navigate", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Actions step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			// Trigger step should now be clickable (visited)
			const triggerStepButton = screen.getByRole("button", {
				name: /trigger/i,
			});
			expect(triggerStepButton).not.toBeDisabled();

			// Click on Trigger step
			await user.click(triggerStepButton);

			// Should navigate back to Trigger step
			await waitFor(() => {
				expect(screen.getByLabelText("Trigger Template")).toBeVisible();
			});
		});

		it("disables clicking on unvisited steps", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Actions and Details steps should be disabled (not visited)
			const actionsStepButton = screen.getByRole("button", {
				name: /actions/i,
			});
			const detailsStepButton = screen.getByRole("button", {
				name: /details/i,
			});

			expect(actionsStepButton).toBeDisabled();
			expect(detailsStepButton).toBeDisabled();
		});
	});

	describe("trigger step content", () => {
		it("renders trigger template select on Trigger step", async () => {
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			expect(screen.getByLabelText("Trigger Template")).toBeVisible();
		});

		it("shows trigger fields after selecting a template", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			// Should show trigger fields
			// Note: Flow run state trigger does not have a Threshold field (removed to match Vue)
			await waitFor(() => {
				expect(screen.getByLabelText("select posture")).toBeVisible();
			});
			expect(screen.getByText("Flows")).toBeVisible();
		});

		it("can select different trigger templates", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Test deployment-status template
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(
				screen.getByRole("option", { name: "Deployment status" }),
			);

			await waitFor(() => {
				expect(screen.getByLabelText("select posture")).toBeVisible();
			});
		});
	});

	describe("actions step content", () => {
		it("renders action select on Actions step", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Actions step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});
		});

		it("shows Add Action button on Actions step", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Actions step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: /add action/i }),
				).toBeVisible();
			});
		});
	});

	describe("details step content", () => {
		it("renders name and description fields on Details step", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Details step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});
			expect(screen.getByLabelText(/description/i)).toBeVisible();
		});

		it("can fill in automation name and description", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Details step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});

			// Fill in details
			await user.type(
				screen.getByLabelText(/automation name/i),
				"My Test Automation",
			);
			await user.type(
				screen.getByLabelText(/description/i),
				"Test description",
			);

			expect(screen.getByLabelText(/automation name/i)).toHaveValue(
				"My Test Automation",
			);
			expect(screen.getByLabelText(/description/i)).toHaveValue(
				"Test description",
			);
		});
	});

	describe("form validation", () => {
		it("validates trigger step before allowing navigation", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Select a trigger template (required for valid trigger)
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			// Click Next - should navigate since trigger has valid defaults
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Should be on Actions step
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});
		});

		it("validates actions step before allowing navigation", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate to Actions step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			// Select an action
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);

			// Click Next - should navigate since action is selected
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Should be on Details step
			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});
		});
	});

	describe("complete wizard flow", () => {
		it("completes full wizard flow from Trigger to Save", async () => {
			const user = userEvent.setup();
			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Step 1: Trigger
			expect(screen.getByLabelText("Trigger Template")).toBeVisible();
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Step 2: Actions
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Step 3: Details
			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});
			await user.type(
				screen.getByLabelText(/automation name/i),
				"My Automation",
			);

			// Save button should be visible
			expect(screen.getByRole("button", { name: /save/i })).toBeVisible();
		});
	});

	describe("form submission", () => {
		it("renders Save button on final step that can be clicked", async () => {
			const user = userEvent.setup();

			await waitFor(() =>
				render(<AutomationWizardWithRouter />, { wrapper: createWrapper() }),
			);

			// Navigate through wizard to Details step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});

			// Fill in automation name
			await user.type(
				screen.getByLabelText(/automation name/i),
				"Test Automation",
			);

			// Save button should be visible and clickable
			const saveButton = screen.getByRole("button", { name: /save/i });
			expect(saveButton).toBeVisible();
			expect(saveButton).not.toBeDisabled();
		});
	});
});
