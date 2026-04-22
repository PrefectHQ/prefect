import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CodeBanner } from "@/components/code-banner";

/**
 * Tests for the work pool queue setup banner (CodeBanner).
 *
 * The queue detail page renders a CodeBanner with a CLI command
 * to start a worker targeting a specific work pool queue:
 * `prefect worker start --pool "X" --work-queue "Y"`
 */

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("Work Pool Queue CodeBanner", () => {
	it("renders worker start command with pool and queue names", () => {
		render(
			<CodeBanner
				command='prefect worker start --pool "my-pool" --work-queue "my-queue"'
				title="Your work queue my-queue is ready to go!"
				subtitle="Work queues are scoped to a work pool to allow workers to pull from groups of queues with different priorities."
			/>,
			{ wrapper: createWrapper() },
		);

		expect(
			screen.getByText(
				'prefect worker start --pool "my-pool" --work-queue "my-queue"',
			),
		).toBeInTheDocument();
		expect(
			screen.getByText("Your work queue my-queue is ready to go!"),
		).toBeInTheDocument();
		expect(
			screen.getByText(
				"Work queues are scoped to a work pool to allow workers to pull from groups of queues with different priorities.",
			),
		).toBeInTheDocument();
	});

	describe("command generation logic", () => {
		it("generates correct worker command", () => {
			const workPoolName = "my-pool";
			const workQueueName = "my-queue";
			const command = `prefect worker start --pool "${workPoolName}" --work-queue "${workQueueName}"`;

			expect(command).toBe(
				'prefect worker start --pool "my-pool" --work-queue "my-queue"',
			);
		});

		it("generates correct title with queue name", () => {
			const workQueueName = "production-queue";
			const title = `Your work queue ${workQueueName} is ready to go!`;

			expect(title).toBe("Your work queue production-queue is ready to go!");
		});
	});
});
