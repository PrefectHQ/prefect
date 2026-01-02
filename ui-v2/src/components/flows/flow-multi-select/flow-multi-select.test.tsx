import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FlowMultiSelect } from "./flow-multi-select";

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

describe("FlowMultiSelect", () => {
	const TestFlowMultiSelect = ({
		initialSelectedFlowIds = [],
		emptyMessage = "Any flow",
	}: {
		initialSelectedFlowIds?: string[];
		emptyMessage?: string;
	}) => {
		const [selectedFlowIds, setSelectedFlowIds] = useState<string[]>(
			initialSelectedFlowIds,
		);
		const handleToggleFlow = (flowId: string) => {
			setSelectedFlowIds((prev) =>
				prev.includes(flowId)
					? prev.filter((id) => id !== flowId)
					: [...prev, flowId],
			);
		};
		return (
			<FlowMultiSelect
				selectedFlowIds={selectedFlowIds}
				onToggleFlow={handleToggleFlow}
				emptyMessage={emptyMessage}
			/>
		);
	};

	it("renders with empty message when no flows are selected", () => {
		renderWithQueryClient(<TestFlowMultiSelect />);

		expect(screen.getByText("Any flow")).toBeVisible();
	});

	it("renders with custom empty message", () => {
		renderWithQueryClient(<TestFlowMultiSelect emptyMessage="Select a flow" />);

		expect(screen.getByText("Select a flow")).toBeVisible();
	});

	it("opens dropdown and shows search input", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestFlowMultiSelect />);

		await user.click(screen.getByRole("button", { name: /any flow/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search flows...")).toBeVisible();
		});
	});

	it("shows flow options in dropdown when opened", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestFlowMultiSelect />);

		await user.click(screen.getByRole("button", { name: /any flow/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search flows...")).toBeVisible();
		});

		expect(screen.getByRole("listbox")).toBeVisible();
	});
});
