import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeWorkPool } from "@/mocks";
import {
	TriggerDetailsWorkPoolStatus,
	type TriggerDetailsWorkPoolStatusProps,
} from "./trigger-details-work-pool-status";

const TriggerDetailsWorkPoolStatusRouter = (
	props: TriggerDetailsWorkPoolStatusProps,
) => {
	const rootRoute = createRootRoute({
		component: () => <TriggerDetailsWorkPoolStatus {...props} />,
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

describe("TriggerDetailsWorkPoolStatus", () => {
	describe("when workPoolIds is empty", () => {
		it("renders 'any work pool' text", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any work pool")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders 'not ready' status correctly", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Reactive"
					status="NOT_READY"
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("not ready")).toBeInTheDocument();
		});

		it("renders 'paused' status correctly", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Reactive"
					status="PAUSED"
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("paused")).toBeInTheDocument();
		});
	});

	describe("posture labels", () => {
		it("renders 'enters' for Reactive posture", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("enters")).toBeInTheDocument();
		});

		it("renders 'stays in' for Proactive posture", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Proactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("stays in")).toBeInTheDocument();
		});
	});

	describe("time display", () => {
		it("does not show time for Reactive posture", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Reactive"
					status="READY"
					time={30}
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.queryByText(/for/)).not.toBeInTheDocument();
		});

		it("shows time for Proactive posture when time is provided", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Proactive"
					status="PAUSED"
					time={30}
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("for 30 seconds")).toBeInTheDocument();
		});

		it("does not show time for Proactive posture when time is not provided", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Proactive"
					status="PAUSED"
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.queryByText(/for/)).not.toBeInTheDocument();
		});

		it("formats longer time durations correctly", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Proactive"
					status="PAUSED"
					time={3661}
				/>,
				{ wrapper: createWrapper() },
			);

			expect(
				screen.getByText("for 1 hour 1 minute 1 second"),
			).toBeInTheDocument();
		});
	});

	describe("when workPoolIds has items", () => {
		it("renders singular 'work pool' for single work pool", async () => {
			const mockWorkPool = createFakeWorkPool({
				id: "pool-1",
				name: "my-pool",
			});

			server.use(
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([mockWorkPool]);
				}),
			);

			await waitFor(() =>
				render(
					<TriggerDetailsWorkPoolStatusRouter
						workPoolIds={["pool-1"]}
						posture="Reactive"
						status="READY"
					/>,
					{ wrapper: createWrapper() },
				),
			);

			expect(screen.getByText("work pool")).toBeInTheDocument();

			await waitFor(() => {
				expect(screen.getByText("my-pool")).toBeInTheDocument();
			});
		});

		it("renders plural 'work pools' for multiple work pools", async () => {
			const mockWorkPool1 = createFakeWorkPool({
				id: "pool-1",
				name: "pool-one",
			});
			const mockWorkPool2 = createFakeWorkPool({
				id: "pool-2",
				name: "pool-two",
			});

			server.use(
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([mockWorkPool1, mockWorkPool2]);
				}),
			);

			await waitFor(() =>
				render(
					<TriggerDetailsWorkPoolStatusRouter
						workPoolIds={["pool-1", "pool-2"]}
						posture="Reactive"
						status="NOT_READY"
					/>,
					{ wrapper: createWrapper() },
				),
			);

			expect(screen.getByText("work pools")).toBeInTheDocument();

			await waitFor(() => {
				expect(screen.getByText("pool-one")).toBeInTheDocument();
				expect(screen.getByText("pool-two")).toBeInTheDocument();
			});
		});

		it("renders work pool links with 'or' between last two items", async () => {
			const mockWorkPool1 = createFakeWorkPool({
				id: "pool-1",
				name: "pool-one",
			});
			const mockWorkPool2 = createFakeWorkPool({
				id: "pool-2",
				name: "pool-two",
			});
			const mockWorkPool3 = createFakeWorkPool({
				id: "pool-3",
				name: "pool-three",
			});

			server.use(
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([
						mockWorkPool1,
						mockWorkPool2,
						mockWorkPool3,
					]);
				}),
			);

			await waitFor(() =>
				render(
					<TriggerDetailsWorkPoolStatusRouter
						workPoolIds={["pool-1", "pool-2", "pool-3"]}
						posture="Reactive"
						status="READY"
					/>,
					{ wrapper: createWrapper() },
				),
			);

			await waitFor(() => {
				expect(screen.getByText("pool-one")).toBeInTheDocument();
				expect(screen.getByText("pool-two")).toBeInTheDocument();
				expect(screen.getByText("pool-three")).toBeInTheDocument();
			});

			const container = screen.getByText("When").parentElement;
			expect(container?.textContent).toContain("or");
		});

		it("renders work pool links as clickable links", async () => {
			const mockWorkPool = createFakeWorkPool({
				id: "pool-1",
				name: "my-pool",
			});

			server.use(
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([mockWorkPool]);
				}),
			);

			await waitFor(() =>
				render(
					<TriggerDetailsWorkPoolStatusRouter
						workPoolIds={["pool-1"]}
						posture="Reactive"
						status="READY"
					/>,
					{ wrapper: createWrapper() },
				),
			);

			await waitFor(() => {
				const link = screen.getByRole("link", { name: /my-pool/i });
				expect(link).toBeInTheDocument();
				expect(link).toHaveAttribute("href", "/work-pools/work-pool/my-pool");
			});
		});
	});

	describe("complete sentence rendering", () => {
		it("renders complete sentence for any work pool reactive", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			const container = screen.getByText("When").parentElement;
			expect(container?.textContent).toContain("When");
			expect(container?.textContent).toContain("any work pool");
			expect(container?.textContent).toContain("enters");
			expect(container?.textContent).toContain("ready");
		});

		it("renders complete sentence for any work pool proactive with time", () => {
			render(
				<TriggerDetailsWorkPoolStatus
					workPoolIds={[]}
					posture="Proactive"
					status="PAUSED"
					time={30}
				/>,
				{ wrapper: createWrapper() },
			);

			const container = screen.getByText("When").parentElement;
			expect(container?.textContent).toContain("When");
			expect(container?.textContent).toContain("any work pool");
			expect(container?.textContent).toContain("stays in");
			expect(container?.textContent).toContain("paused");
			expect(container?.textContent).toContain("for 30 seconds");
		});
	});
});
