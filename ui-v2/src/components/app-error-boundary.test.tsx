import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppErrorBoundary } from "./app-error-boundary";

// Suppress React error boundary console errors in tests
beforeEach(() => {
	vi.spyOn(console, "error").mockImplementation(() => {});
});

function ThrowingComponent({ error }: { error: Error }): never {
	throw error;
}

describe("AppErrorBoundary", () => {
	it("renders children when no error", () => {
		render(
			<AppErrorBoundary>
				<div>App content</div>
			</AppErrorBoundary>,
		);

		expect(screen.getByText("App content")).toBeInTheDocument();
	});

	it("renders error display when child throws network error", () => {
		const networkError = new TypeError("Failed to fetch");

		render(
			<AppErrorBoundary>
				<ThrowingComponent error={networkError} />
			</AppErrorBoundary>,
		);

		expect(
			screen.getByText("Unable to connect to Prefect server"),
		).toBeInTheDocument();
	});

	it("renders error display when child throws server error", () => {
		const serverError = new Error("Failed to fetch UI settings: status 500");

		render(
			<AppErrorBoundary>
				<ThrowingComponent error={serverError} />
			</AppErrorBoundary>,
		);

		expect(screen.getByText("Prefect server error")).toBeInTheDocument();
		expect(screen.getByText("Status code: 500")).toBeInTheDocument();
	});

	it("logs error to console", () => {
		const error = new Error("Test error");

		render(
			<AppErrorBoundary>
				<ThrowingComponent error={error} />
			</AppErrorBoundary>,
		);

		expect(console.error).toHaveBeenCalled();
	});
});
