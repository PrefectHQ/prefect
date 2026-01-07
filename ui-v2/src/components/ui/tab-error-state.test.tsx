import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TabErrorState } from "./tab-error-state";

const mockError = {
	type: "network-error" as const,
	message: "Unable to connect",
	details: "Check your connection",
};

describe("TabErrorState", () => {
	it("renders error message and details", () => {
		render(<TabErrorState error={mockError} />);
		expect(screen.getByText("Unable to connect")).toBeInTheDocument();
		expect(screen.getByText("Check your connection")).toBeInTheDocument();
	});

	it("calls onRetry when retry button clicked", async () => {
		const onRetry = vi.fn();
		render(<TabErrorState error={mockError} onRetry={onRetry} />);
		await userEvent.click(screen.getByRole("button", { name: /retry/i }));
		expect(onRetry).toHaveBeenCalledOnce();
	});

	it("shows retrying state", () => {
		render(<TabErrorState error={mockError} onRetry={() => {}} isRetrying />);
		expect(screen.getByRole("button", { name: /retrying/i })).toBeDisabled();
	});

	it("hides retry button when onRetry not provided", () => {
		render(<TabErrorState error={mockError} />);
		expect(screen.queryByRole("button")).not.toBeInTheDocument();
	});
});
