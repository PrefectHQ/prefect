import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { CodeBanner } from "@/components/code-banner";

/**
 * Tests for the work pool queue setup banner (CodeBanner) logic.
 *
 * The queue detail page renders a CodeBanner with an agent-aware CLI command
 * that varies based on the work pool type:
 * - Agent pools: `prefect agent start --pool "X" --work-queue "Y"`
 * - Worker pools: `prefect worker start --pool "X" --work-queue "Y"`
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
	describe("worker pool (non-agent)", () => {
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
	});

	describe("agent pool", () => {
		it("renders agent start command with pool and queue names", () => {
			render(
				<CodeBanner
					command='prefect agent start --pool "my-agent-pool" --work-queue "my-queue"'
					title="Your work queue my-queue is ready to go!"
					subtitle="Work queues are scoped to a work pool to allow agents to pull from groups of queues with different priorities."
				/>,
				{ wrapper: createWrapper() },
			);

			expect(
				screen.getByText(
					'prefect agent start --pool "my-agent-pool" --work-queue "my-queue"',
				),
			).toBeInTheDocument();
			expect(
				screen.getByText(
					"Work queues are scoped to a work pool to allow agents to pull from groups of queues with different priorities.",
				),
			).toBeInTheDocument();
		});
	});

	describe("command generation logic", () => {
		it("generates correct worker command for non-agent pool types", () => {
			const workPoolType = "process";
			const workPoolName = "my-pool";
			const workQueueName = "my-queue";
			const isAgentWorkPool = workPoolType === "prefect-agent";
			const command = `prefect ${isAgentWorkPool ? "agent" : "worker"} start --pool "${workPoolName}" --work-queue "${workQueueName}"`;

			expect(command).toBe(
				'prefect worker start --pool "my-pool" --work-queue "my-queue"',
			);
		});

		it("generates correct agent command for prefect-agent pool type", () => {
			const workPoolType = "prefect-agent";
			const workPoolName = "my-agent-pool";
			const workQueueName = "my-queue";
			const isAgentWorkPool = workPoolType === "prefect-agent";
			const command = `prefect ${isAgentWorkPool ? "agent" : "worker"} start --pool "${workPoolName}" --work-queue "${workQueueName}"`;

			expect(command).toBe(
				'prefect agent start --pool "my-agent-pool" --work-queue "my-queue"',
			);
		});

		it("generates correct title with queue name", () => {
			const workQueueName = "production-queue";
			const title = `Your work queue ${workQueueName} is ready to go!`;

			expect(title).toBe("Your work queue production-queue is ready to go!");
		});

		it("generates correct subtitle for worker pools", () => {
			const isAgentWorkPool = false;
			const subtitle = `Work queues are scoped to a work pool to allow ${isAgentWorkPool ? "agents" : "workers"} to pull from groups of queues with different priorities.`;

			expect(subtitle).toBe(
				"Work queues are scoped to a work pool to allow workers to pull from groups of queues with different priorities.",
			);
		});

		it("generates correct subtitle for agent pools", () => {
			const isAgentWorkPool = true;
			const subtitle = `Work queues are scoped to a work pool to allow ${isAgentWorkPool ? "agents" : "workers"} to pull from groups of queues with different priorities.`;

			expect(subtitle).toBe(
				"Work queues are scoped to a work pool to allow agents to pull from groups of queues with different priorities.",
			);
		});
	});

	describe("MSW handler for work pool details", () => {
		it("returns work pool with type field from GET /work_pools/:name", async () => {
			server.use(
				http.get(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json({
						id: "wp-1",
						created: new Date().toISOString(),
						updated: new Date().toISOString(),
						name: "test-pool",
						type: "prefect-agent",
						base_job_template: {},
						is_paused: false,
						concurrency_limit: null,
						default_queue_id: "q-1",
						status: "READY",
					});
				}),
			);

			const response: { name: string; type: string } = await fetch(
				buildApiUrl("/work_pools/test-pool"),
			).then((r) => r.json() as Promise<{ name: string; type: string }>);

			expect(response).toMatchObject({
				name: "test-pool",
				type: "prefect-agent",
			});
		});
	});
});
