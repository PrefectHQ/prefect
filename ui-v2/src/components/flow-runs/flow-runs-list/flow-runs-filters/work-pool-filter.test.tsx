import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { WorkPoolFilter } from "./work-pool-filter";

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

describe("WorkPoolFilter", () => {
	const TestWorkPoolFilter = ({
		initialSelectedWorkPools = new Set<string>(),
	}: {
		initialSelectedWorkPools?: Set<string>;
	}) => {
		const [selectedWorkPools, setSelectedWorkPools] = useState<Set<string>>(
			initialSelectedWorkPools,
		);
		return (
			<WorkPoolFilter
				selectedWorkPools={selectedWorkPools}
				onSelectWorkPools={setSelectedWorkPools}
			/>
		);
	};

	it("renders with 'All work pools' when no work pools are selected", () => {
		renderWithQueryClient(<TestWorkPoolFilter />);

		expect(
			screen.getByRole("button", { name: /filter by work pool/i }),
		).toBeVisible();
		expect(screen.getByText("All work pools")).toBeVisible();
	});

	it("opens dropdown and shows 'All work pools' option", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestWorkPoolFilter />);

		await user.click(
			screen.getByRole("button", { name: /filter by work pool/i }),
		);

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search work pools...")).toBeVisible();
		});

		expect(
			screen.getByRole("option", { name: /all work pools/i }),
		).toBeVisible();
	});

	it("shows search input in dropdown", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestWorkPoolFilter />);

		await user.click(
			screen.getByRole("button", { name: /filter by work pool/i }),
		);

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search work pools...")).toBeVisible();
		});
	});

	it("has 'All work pools' checkbox checked by default", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestWorkPoolFilter />);

		await user.click(
			screen.getByRole("button", { name: /filter by work pool/i }),
		);

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /all work pools/i }),
			).toBeVisible();
		});

		const allWorkPoolsOption = screen.getByRole("option", {
			name: /all work pools/i,
		});
		const allWorkPoolsCheckbox =
			allWorkPoolsOption.querySelector('[role="checkbox"]');
		expect(allWorkPoolsCheckbox).toHaveAttribute("data-state", "checked");
	});
});
