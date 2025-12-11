import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FlowFilter } from "./flow-filter";

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

describe("FlowFilter", () => {
	const TestFlowFilter = ({
		initialSelectedFlows = new Set<string>(),
	}: {
		initialSelectedFlows?: Set<string>;
	}) => {
		const [selectedFlows, setSelectedFlows] =
			useState<Set<string>>(initialSelectedFlows);
		return (
			<FlowFilter
				selectedFlows={selectedFlows}
				onSelectFlows={setSelectedFlows}
			/>
		);
	};

	it("renders with 'All flows' when no flows are selected", () => {
		renderWithQueryClient(<TestFlowFilter />);

		expect(
			screen.getByRole("button", { name: /filter by flow/i }),
		).toBeVisible();
		expect(screen.getByText("All flows")).toBeVisible();
	});

	it("opens dropdown and shows 'All flows' option", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestFlowFilter />);

		await user.click(screen.getByRole("button", { name: /filter by flow/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search flows...")).toBeVisible();
		});

		expect(screen.getByRole("option", { name: /all flows/i })).toBeVisible();
	});

	it("shows search input in dropdown", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestFlowFilter />);

		await user.click(screen.getByRole("button", { name: /filter by flow/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search flows...")).toBeVisible();
		});
	});

	it("has 'All flows' checkbox checked by default", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestFlowFilter />);

		await user.click(screen.getByRole("button", { name: /filter by flow/i }));

		await waitFor(() => {
			expect(screen.getByRole("option", { name: /all flows/i })).toBeVisible();
		});

		const allFlowsOption = screen.getByRole("option", { name: /all flows/i });
		const allFlowsCheckbox = allFlowsOption.querySelector('[role="checkbox"]');
		expect(allFlowsCheckbox).toHaveAttribute("data-state", "checked");
	});
});
