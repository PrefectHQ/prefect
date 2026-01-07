import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RouteErrorState } from "./route-error-state";

const mockError = {
	type: "network-error" as const,
	message: "Unable to connect",
	details: "Check your connection",
};

describe("RouteErrorState", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("renders error message and details", () => {
		render(<RouteErrorState error={mockError} onRetry={() => {}} />);
		expect(screen.getByText("Unable to connect")).toBeInTheDocument();
		expect(screen.getByText("Check your connection")).toBeInTheDocument();
	});

	it("calls onRetry when retry button clicked", async () => {
		vi.useRealTimers();
		const onRetry = vi.fn();
		render(<RouteErrorState error={mockError} onRetry={onRetry} />);
		await userEvent.click(screen.getByRole("button", { name: /retry/i }));
		expect(onRetry).toHaveBeenCalledOnce();
	});

	it("shows countdown timer", () => {
		render(<RouteErrorState error={mockError} onRetry={() => {}} />);
		expect(screen.getByText(/retrying in \d+s/i)).toBeInTheDocument();
	});

	it("auto-retries after countdown", () => {
		const onRetry = vi.fn();
		render(<RouteErrorState error={mockError} onRetry={onRetry} />);

		// Fast-forward past the initial retry interval
		act(() => {
			vi.advanceTimersByTime(6000);
		});

		expect(onRetry).toHaveBeenCalled();
	});
});
