import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import {
	afterAll,
	afterEach,
	beforeAll,
	describe,
	expect,
	it,
	vi,
} from "vitest";
import { AutomationDeploymentCombobox } from "./index";

const mockDeployments = [
	{
		id: "deployment-1",
		name: "Test Deployment 1",
		flow_id: "flow-1",
		created: "2024-01-01T00:00:00Z",
		updated: "2024-01-01T00:00:00Z",
		status: "READY",
	},
	{
		id: "deployment-2",
		name: "Test Deployment 2",
		flow_id: "flow-2",
		created: "2024-01-01T00:00:00Z",
		updated: "2024-01-01T00:00:00Z",
		status: "READY",
	},
	{
		id: "deployment-3",
		name: "Another Deployment",
		flow_id: "flow-3",
		created: "2024-01-01T00:00:00Z",
		updated: "2024-01-01T00:00:00Z",
		status: "READY",
	},
];

const server = setupServer(
	http.post("*/deployments/filter", () => {
		return HttpResponse.json(mockDeployments);
	}),
);

describe("AutomationDeploymentCombobox", () => {
	beforeAll(() => {
		server.listen();
		mockPointerEvents();
	});

	afterAll(() => {
		server.close();
	});

	afterEach(() => {
		server.resetHandlers();
	});

	const renderComponent = (props: {
		selectedDeploymentIds?: string[];
		onSelectDeploymentIds?: (ids: string[]) => void;
	}) => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		return render(
			<QueryClientProvider client={queryClient}>
				<AutomationDeploymentCombobox
					selectedDeploymentIds={props.selectedDeploymentIds ?? []}
					onSelectDeploymentIds={props.onSelectDeploymentIds ?? vi.fn()}
				/>
			</QueryClientProvider>,
		);
	};

	it("renders with 'All deployments' when no deployments are selected", () => {
		renderComponent({});

		expect(screen.getByText("All deployments")).toBeInTheDocument();
	});

	it("opens the combobox when clicked", async () => {
		const user = userEvent.setup();
		renderComponent({});

		const trigger = screen.getByRole("button", { name: "Select deployments" });
		await user.click(trigger);

		expect(
			screen.getByPlaceholderText("Search deployments..."),
		).toBeInTheDocument();
	});

	it("shows search input when combobox is opened", async () => {
		const user = userEvent.setup();
		renderComponent({});

		const trigger = screen.getByRole("button", { name: "Select deployments" });
		await user.click(trigger);

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search deployments..."),
			).toBeInTheDocument();
		});
	});
});
