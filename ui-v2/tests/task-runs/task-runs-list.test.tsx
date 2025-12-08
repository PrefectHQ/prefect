import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskRunsList } from "@/components/task-runs/task-runs-list";

const createWrapper = () => {
	const queryClient = new QueryClient();
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	return Wrapper;
};

describe("TaskRunsList", () => {
	it("should render loading skeleton when taskRuns is undefined", () => {
		render(<TaskRunsList taskRuns={undefined} />, {
			wrapper: createWrapper(),
		});
		expect(screen.getAllByRole("listitem")).toHaveLength(5);
	});

	it("should render empty state when taskRuns is empty", () => {
		render(<TaskRunsList taskRuns={[]} />, {
			wrapper: createWrapper(),
		});
		expect(screen.getByText("No task runs found")).toBeVisible();
	});

	it("should render clear filters button when onClearFilters is provided and taskRuns is empty", async () => {
		const onClearFilters = vi.fn();
		const user = userEvent.setup();
		render(<TaskRunsList taskRuns={[]} onClearFilters={onClearFilters} />, {
			wrapper: createWrapper(),
		});
		expect(screen.getByText("No task runs found")).toBeVisible();
		expect(screen.getByRole("button", { name: "Clear Filters" })).toBeVisible();
		await user.click(screen.getByRole("button", { name: "Clear Filters" }));
		expect(onClearFilters).toHaveBeenCalled();
	});
});
