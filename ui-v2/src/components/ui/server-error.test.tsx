import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ServerError } from "@/api/error-utils";
import { ServerErrorDisplay } from "./server-error";

describe("ServerErrorDisplay", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	const networkError: ServerError = {
		type: "network-error",
		message: "Unable to connect to Prefect server",
		details: "Server may be down",
	};

	const serverError: ServerError = {
		type: "server-error",
		message: "Prefect server error",
		details: "The server returned an error",
		statusCode: 500,
	};

	it("displays error message and details", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		expect(
			screen.getByText("Unable to connect to Prefect server"),
		).toBeInTheDocument();
		expect(screen.getByText("Server may be down")).toBeInTheDocument();
	});

	it("displays status code when present", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={serverError} onRetry={onRetry} />);

		expect(screen.getByText("Status code: 500")).toBeInTheDocument();
	});

	it("calls onRetry when retry button is clicked", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		fireEvent.click(screen.getByRole("button", { name: /retry now/i }));

		expect(onRetry).toHaveBeenCalledTimes(1);
	});

	it("shows countdown timer", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		expect(
			screen.getByText("Automatically retrying in 5s"),
		).toBeInTheDocument();
	});

	it("decrements countdown and auto-retries", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		// Advance 1 second
		act(() => {
			vi.advanceTimersByTime(1000);
		});
		expect(
			screen.getByText("Automatically retrying in 4s"),
		).toBeInTheDocument();

		// Advance to trigger retry (4 more seconds)
		act(() => {
			vi.advanceTimersByTime(4000);
		});
		expect(onRetry).toHaveBeenCalledTimes(1);
	});

	it("uses exponential backoff for auto-retries", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		// First retry after 5 seconds
		act(() => {
			vi.advanceTimersByTime(5000);
		});
		expect(onRetry).toHaveBeenCalledTimes(1);

		// After first auto-retry, next interval should be 10 seconds
		expect(
			screen.getByText("Automatically retrying in 10s"),
		).toBeInTheDocument();

		// Second retry after 10 more seconds
		act(() => {
			vi.advanceTimersByTime(10000);
		});
		expect(onRetry).toHaveBeenCalledTimes(2);

		// After second auto-retry, next interval should be 20 seconds
		expect(
			screen.getByText("Automatically retrying in 20s"),
		).toBeInTheDocument();
	});

	it("resets backoff on manual retry", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		// First auto-retry after 5 seconds
		act(() => {
			vi.advanceTimersByTime(5000);
		});
		expect(onRetry).toHaveBeenCalledTimes(1);

		// Next interval should be 10 seconds
		expect(
			screen.getByText("Automatically retrying in 10s"),
		).toBeInTheDocument();

		// Wait for the isRetrying state to reset (500ms timeout in handleAutoRetry)
		act(() => {
			vi.advanceTimersByTime(500);
		});

		// Manual retry should reset the backoff
		fireEvent.click(screen.getByRole("button", { name: /retry now/i }));
		expect(onRetry).toHaveBeenCalledTimes(2);

		// After manual retry, interval should reset to 5 seconds (check immediately)
		// The countdown is set synchronously in handleManualRetry
		expect(
			screen.getByText("Automatically retrying in 5s"),
		).toBeInTheDocument();
	});

	it("displays help text for starting server", () => {
		const onRetry = vi.fn();
		render(<ServerErrorDisplay error={networkError} onRetry={onRetry} />);

		expect(screen.getByText("prefect server start")).toBeInTheDocument();
	});
});
