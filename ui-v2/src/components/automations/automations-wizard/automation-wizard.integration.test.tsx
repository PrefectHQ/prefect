import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import {
	createFakeAutomation,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { AutomationWizard } from "./automation-wizard";

const AutomationWizardWithRouterAndToaster = () => {
	const rootRoute = createRootRoute();
	const indexRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/",
		component: () => <AutomationWizard />,
	});
	const automationsRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/automations",
		component: () => <div data-testid="automations-page">Automations Page</div>,
	});

	const routeTree = rootRoute.addChildren([indexRoute, automationsRoute]);

	const router = createRouter({
		routeTree,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});

	return (
		<>
			<Toaster />
			<RouterProvider router={router} />
		</>
	);
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

const navigateToDetailsStep = async (
	user: ReturnType<typeof userEvent.setup>,
) => {
	await user.click(screen.getByLabelText("Trigger Template"));
	await user.click(screen.getByRole("option", { name: "Flow run state" }));
	await user.click(screen.getByRole("button", { name: /next/i }));

	await waitFor(() => {
		expect(screen.getByLabelText(/select action/i)).toBeVisible();
	});

	await user.click(screen.getByLabelText(/select action/i));
	await user.click(screen.getByRole("option", { name: "Cancel a flow run" }));
	await user.click(screen.getByRole("button", { name: /next/i }));

	await waitFor(() => {
		expect(screen.getByLabelText(/automation name/i)).toBeVisible();
	});
};

describe("AutomationWizard Integration Tests", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	describe("Wizard navigation", () => {
		it("can navigate through all wizard steps", async () => {
			const user = userEvent.setup();
			setupMockAPIs();

			await waitFor(() =>
				render(<AutomationWizardWithRouterAndToaster />, {
					wrapper: createWrapper(),
				}),
			);

			// Step 1: Trigger - verify we're on the trigger step
			expect(screen.getByLabelText("Trigger Template")).toBeVisible();
			expect(screen.getByRole("button", { name: /next/i })).toBeVisible();

			// Select a trigger template and go to next step
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Step 2: Actions - verify we're on the actions step
			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			// Select an action and go to next step
			await user.click(screen.getByLabelText(/select action/i));
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);
			await user.click(screen.getByRole("button", { name: /next/i }));

			// Step 3: Details - verify we're on the details step
			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});

			// Verify Save button is visible on final step
			expect(screen.getByRole("button", { name: /save/i })).toBeVisible();
		});

		it("can navigate back using Previous button", async () => {
			const user = userEvent.setup();
			setupMockAPIs();

			await waitFor(() =>
				render(<AutomationWizardWithRouterAndToaster />, {
					wrapper: createWrapper(),
				}),
			);

			// Navigate to step 2
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));
			await user.click(screen.getByRole("button", { name: /next/i }));

			await waitFor(() => {
				expect(screen.getByLabelText(/select action/i)).toBeVisible();
			});

			// Click Previous to go back to step 1
			await user.click(screen.getByRole("button", { name: /previous/i }));

			await waitFor(() => {
				expect(screen.getByLabelText("Trigger Template")).toBeVisible();
			});
		});
	});

	describe("Save button", () => {
		it("Save button is visible and enabled on Details step", async () => {
			const user = userEvent.setup();
			setupMockAPIs();

			await waitFor(() =>
				render(<AutomationWizardWithRouterAndToaster />, {
					wrapper: createWrapper(),
				}),
			);

			await navigateToDetailsStep(user);

			const saveButton = screen.getByRole("button", { name: /save/i });
			expect(saveButton).toBeVisible();
			expect(saveButton).not.toBeDisabled();
		});
	});

	describe("Cancel navigation", () => {
		it("Cancel button links to automations list", async () => {
			setupMockAPIs();

			await waitFor(() =>
				render(<AutomationWizardWithRouterAndToaster />, {
					wrapper: createWrapper(),
				}),
			);

			const cancelButton = screen.getByRole("button", { name: /cancel/i });
			expect(cancelButton).toBeVisible();

			const cancelLink = within(cancelButton).getByRole("link");
			expect(cancelLink).toHaveAttribute("href", "/automations");
		});
	});

	describe("Validation errors", () => {
		it("does not submit without filling in automation name", async () => {
			const user = userEvent.setup();
			const createAutomationHandler = vi.fn();

			setupMockAPIs();

			// Override the automation creation handler to track calls
			server.use(
				http.post(buildApiUrl("/automations/"), async ({ request }) => {
					const body = await request.json();
					createAutomationHandler(body);
					return HttpResponse.json(createFakeAutomation(), { status: 201 });
				}),
			);

			await waitFor(() =>
				render(<AutomationWizardWithRouterAndToaster />, {
					wrapper: createWrapper(),
				}),
			);

			await navigateToDetailsStep(user);

			// Try to submit without filling in the name
			await user.click(screen.getByRole("button", { name: /save/i }));

			// Wait a bit to ensure the form validation runs
			await waitFor(() => {
				expect(screen.getByLabelText(/automation name/i)).toBeVisible();
			});

			// The API should not have been called because validation failed
			expect(createAutomationHandler).not.toHaveBeenCalled();
		});
	});

	describe("Form fields", () => {
		it("allows entering automation name and description", async () => {
			const user = userEvent.setup();
			setupMockAPIs();

			await waitFor(() =>
				render(<AutomationWizardWithRouterAndToaster />, {
					wrapper: createWrapper(),
				}),
			);

			await navigateToDetailsStep(user);

			const nameInput = screen.getByLabelText(/automation name/i);
			const descriptionInput = screen.getByLabelText(/description/i);

			await user.type(nameInput, "My Test Automation");
			await user.type(descriptionInput, "This is a test description");

			expect(nameInput).toHaveValue("My Test Automation");
			expect(descriptionInput).toHaveValue("This is a test description");
		});
	});
});
