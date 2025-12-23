import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunDetails } from "./flow-run-details";

const FlowRunDetailsRouter = ({
	flowRun,
}: {
	flowRun: Parameters<typeof FlowRunDetails>[0]["flowRun"];
}) => {
	const rootRoute = createRootRoute({
		component: () => (
			<>
				<Toaster />
				<FlowRunDetails flowRun={flowRun} />
			</>
		),
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("FlowRunDetails", () => {
	it("should display empty state when no flowRun is provided", async () => {
		render(<FlowRunDetailsRouter flowRun={null} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(
				screen.getByText("No flow run details available"),
			).toBeInTheDocument();
		});
	});

	it("should display run count", async () => {
		const flowRun = createFakeFlowRun({ run_count: 5 });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.getByText("5")).toBeInTheDocument();
	});

	it("should display flow run ID", async () => {
		const flowRun = createFakeFlowRun({ id: "test-flow-run-id" });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Flow Run ID")).toBeInTheDocument();
		});
		expect(screen.getByText("test-flow-run-id")).toBeInTheDocument();
	});

	it("should display created date", async () => {
		const flowRun = createFakeFlowRun({
			created: "2024-01-15T10:30:00.000Z",
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Created")).toBeInTheDocument();
		});
	});

	it("should display last updated date", async () => {
		const flowRun = createFakeFlowRun({
			updated: "2024-01-15T12:00:00.000Z",
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Last Updated")).toBeInTheDocument();
		});
	});

	it("should display tags when present", async () => {
		const flowRun = createFakeFlowRun({
			tags: ["tag1", "tag2"],
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Tags")).toBeInTheDocument();
		});
		expect(screen.getByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
	});

	it("should not display tags when empty", async () => {
		const flowRun = createFakeFlowRun({ tags: [] });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.queryByText("Tags")).not.toBeInTheDocument();
	});

	it("should display created by when present", async () => {
		const flowRun = createFakeFlowRun({
			created_by: {
				id: "user-id",
				type: "USER",
				display_value: "John Doe",
			},
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Created By")).toBeInTheDocument();
		});
		expect(screen.getByText("John Doe")).toBeInTheDocument();
	});

	it("should not display created by when not present", async () => {
		const flowRun = createFakeFlowRun({ created_by: null });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.queryByText("Created By")).not.toBeInTheDocument();
	});

	it("should display idempotency key when present", async () => {
		const flowRun = createFakeFlowRun({
			idempotency_key: "my-idempotency-key",
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Idempotency Key")).toBeInTheDocument();
		});
		expect(screen.getByText("my-idempotency-key")).toBeInTheDocument();
	});

	it("should not display idempotency key when not present", async () => {
		const flowRun = createFakeFlowRun({ idempotency_key: null });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.queryByText("Idempotency Key")).not.toBeInTheDocument();
	});

	it("should display state message when present", async () => {
		const flowRun = createFakeFlowRun({
			state: {
				id: "state-id",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-15T12:00:00.000Z",
				message: "Flow completed successfully",
			},
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("State Message")).toBeInTheDocument();
		});
		expect(screen.getByText("Flow completed successfully")).toBeInTheDocument();
	});

	it("should not display state message when not present", async () => {
		const flowRun = createFakeFlowRun({
			state: {
				id: "state-id",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-15T12:00:00.000Z",
				message: null,
			},
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.queryByText("State Message")).not.toBeInTheDocument();
	});

	it("should display flow version when present", async () => {
		const flowRun = createFakeFlowRun({ flow_version: "v1.2.3" });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Flow Version")).toBeInTheDocument();
		});
		expect(screen.getByText("v1.2.3")).toBeInTheDocument();
	});

	it("should not display flow version when not present", async () => {
		const flowRun = createFakeFlowRun({ flow_version: null });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.queryByText("Flow Version")).not.toBeInTheDocument();
	});

	it("should display retry configuration when present", async () => {
		const flowRun = createFakeFlowRun({
			empirical_policy: {
				max_retries: 0,
				retry_delay_seconds: 0,
				retries: 3,
				retry_delay: 60,
				pause_keys: [],
				resuming: false,
				retry_type: null,
			},
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Retries")).toBeInTheDocument();
		});
		expect(screen.getByText("3")).toBeInTheDocument();
		expect(screen.getByText("Retry Delay")).toBeInTheDocument();
		expect(screen.getByText("60")).toBeInTheDocument();
	});

	it("should not display retry configuration when retries is null", async () => {
		const flowRun = createFakeFlowRun({
			empirical_policy: {
				max_retries: 0,
				retry_delay_seconds: 0,
				retries: null,
				retry_delay: null,
				pause_keys: [],
				resuming: false,
				retry_type: null,
			},
		});
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Run Count")).toBeInTheDocument();
		});
		expect(screen.queryByText("Retries")).not.toBeInTheDocument();
		expect(screen.queryByText("Retry Delay")).not.toBeInTheDocument();
	});

	it("should copy flow run ID when copy button is clicked", async () => {
		const user = userEvent.setup();
		const flowRun = createFakeFlowRun({ id: "copy-test-id" });
		render(<FlowRunDetailsRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Flow Run ID")).toBeInTheDocument();
		});

		const copyButton = screen.getByRole("button");
		await user.click(copyButton);

		expect(await navigator.clipboard.readText()).toBe("copy-test-id");

		await waitFor(() => {
			expect(screen.getByText("Flow Run ID copied")).toBeInTheDocument();
		});
	});
});
