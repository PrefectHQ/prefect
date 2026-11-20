import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
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
	const mockListFlows = () => {
		server.use(
			http.post(buildApiUrl("/flows/filter"), () =>
				HttpResponse.json([
					{ id: "flow-1", name: "Flow one", tags: [] },
					{ id: "flow-2", name: "Flow two", tags: [] },
				]),
			),
		);
	};

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
		return (
			<FlowMultiSelect
				selectedFlowIds={selectedFlowIds}
				onSelectFlowIds={setSelectedFlowIds}
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

	it("selects, deselects, and clears flows", async () => {
		const user = userEvent.setup();
		mockListFlows();
		renderWithQueryClient(<TestFlowMultiSelect />);

		await user.click(screen.getByRole("button", { name: /any flow/i }));

		const anyFlow = await screen.findByRole("option", { name: "Any flow" });
		const flowOne = screen.getByRole("option", { name: "Flow one" });
		const flowTwo = screen.getByRole("option", { name: "Flow two" });
		const anyFlowCheckbox = within(anyFlow).getByRole("checkbox");
		const flowOneCheckbox = within(flowOne).getByRole("checkbox");
		const flowTwoCheckbox = within(flowTwo).getByRole("checkbox");

		expect(anyFlowCheckbox).toBeChecked();
		expect(flowOneCheckbox).not.toBeChecked();

		await user.click(flowOne);
		expect(anyFlowCheckbox).not.toBeChecked();
		expect(flowOneCheckbox).toBeChecked();

		await user.click(flowTwo);
		expect(flowOneCheckbox).toBeChecked();
		expect(flowTwoCheckbox).toBeChecked();

		await user.click(flowOne);
		expect(flowOneCheckbox).not.toBeChecked();
		expect(flowTwoCheckbox).toBeChecked();

		await user.click(anyFlow);
		expect(anyFlowCheckbox).toBeChecked();
		expect(flowTwoCheckbox).not.toBeChecked();
	});
});
