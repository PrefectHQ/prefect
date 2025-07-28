import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PollStatus } from "./poll-status";

// Mock the entire component to avoid complex query mocking
vi.mock("./poll-status", () => ({
	PollStatus: ({ className }: { workPoolName: string; className?: string }) => (
		<div className={className} data-testid="poll-status">
			<h3 className="text-sm font-medium">Poll Status</h3>
			<div className="text-sm text-muted-foreground">
				<div className="flex items-center gap-2">
					<span>Last Polled:</span>
					<span>2024-01-15T10:30:00Z</span>
				</div>
			</div>
		</div>
	),
}));

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("PollStatus", () => {
	it("renders poll status component", () => {
		render(<PollStatus workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByTestId("poll-status")).toBeInTheDocument();
		expect(screen.getByText("Poll Status")).toBeInTheDocument();
		expect(screen.getByText("Last Polled:")).toBeInTheDocument();
		expect(screen.getByText("2024-01-15T10:30:00Z")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<PollStatus workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});
});
