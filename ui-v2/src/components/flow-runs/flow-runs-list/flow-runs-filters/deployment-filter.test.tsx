import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { DeploymentFilter } from "./deployment-filter";

beforeAll(() => {
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		value: vi.fn(),
		configurable: true,
		writable: true,
	});
});

function renderWithQueryClient(ui: React.ReactElement) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
	);
}

describe("DeploymentFilter", () => {
	const TestDeploymentFilter = ({
		initialSelectedDeployments = new Set<string>(),
	}: {
		initialSelectedDeployments?: Set<string>;
	}) => {
		const [selectedDeployments, setSelectedDeployments] = useState<Set<string>>(
			initialSelectedDeployments,
		);
		return (
			<DeploymentFilter
				selectedDeployments={selectedDeployments}
				onSelectDeployments={setSelectedDeployments}
			/>
		);
	};

	it("renders with 'All deployments' when no deployments are selected", () => {
		renderWithQueryClient(<TestDeploymentFilter />);

		expect(
			screen.getByRole("button", { name: /filter by deployment/i }),
		).toBeVisible();
		expect(screen.getByText("All deployments")).toBeVisible();
	});

	it("opens dropdown and shows 'All deployments' option", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestDeploymentFilter />);

		await user.click(
			screen.getByRole("button", { name: /filter by deployment/i }),
		);

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search deployments..."),
			).toBeVisible();
		});

		expect(
			screen.getByRole("option", { name: /all deployments/i }),
		).toBeVisible();
	});

	it("shows search input in dropdown", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestDeploymentFilter />);

		await user.click(
			screen.getByRole("button", { name: /filter by deployment/i }),
		);

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search deployments..."),
			).toBeVisible();
		});
	});

	it("has 'All deployments' checkbox checked by default", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestDeploymentFilter />);

		await user.click(
			screen.getByRole("button", { name: /filter by deployment/i }),
		);

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /all deployments/i }),
			).toBeVisible();
		});

		const allDeploymentsOption = screen.getByRole("option", {
			name: /all deployments/i,
		});
		const allDeploymentsCheckbox =
			allDeploymentsOption.querySelector('[role="checkbox"]');
		expect(allDeploymentsCheckbox).toHaveAttribute("data-state", "checked");
	});
});
