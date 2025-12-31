import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { WorkPoolMultiSelect } from "./work-pool-multi-select";

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

describe("WorkPoolMultiSelect", () => {
	const TestWorkPoolMultiSelect = ({
		initialSelectedWorkPoolIds = [],
		emptyMessage = "All work pools",
	}: {
		initialSelectedWorkPoolIds?: string[];
		emptyMessage?: string;
	}) => {
		const [selectedWorkPoolIds, setSelectedWorkPoolIds] = useState<string[]>(
			initialSelectedWorkPoolIds,
		);
		const handleToggleWorkPool = (workPoolId: string) => {
			setSelectedWorkPoolIds((prev) =>
				prev.includes(workPoolId)
					? prev.filter((id) => id !== workPoolId)
					: [...prev, workPoolId],
			);
		};
		return (
			<WorkPoolMultiSelect
				selectedWorkPoolIds={selectedWorkPoolIds}
				onToggleWorkPool={handleToggleWorkPool}
				emptyMessage={emptyMessage}
			/>
		);
	};

	it("renders with empty message when no work pools are selected", () => {
		renderWithQueryClient(<TestWorkPoolMultiSelect />);

		expect(screen.getByText("All work pools")).toBeVisible();
	});

	it("renders with custom empty message", () => {
		renderWithQueryClient(
			<TestWorkPoolMultiSelect emptyMessage="Select work pools" />,
		);

		expect(screen.getByText("Select work pools")).toBeVisible();
	});

	it("opens dropdown and shows search input", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestWorkPoolMultiSelect />);

		await user.click(screen.getByRole("button", { name: /all work pools/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search work pools...")).toBeVisible();
		});
	});

	it("shows work pool options in dropdown when opened", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestWorkPoolMultiSelect />);

		await user.click(screen.getByRole("button", { name: /all work pools/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("Search work pools...")).toBeVisible();
		});

		expect(screen.getByRole("listbox")).toBeVisible();
	});
});
