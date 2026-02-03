import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { fetchFlowRunGraph } from "./api";

describe("fetchFlowRunGraph", () => {
	const createMockGraphResponse = (overrides = {}) => ({
		start_time: "2023-09-27T15:50:39.425118+00:00",
		end_time: "2023-09-27T15:51:08.999871+00:00",
		root_node_ids: ["node-1"],
		nodes: [
			[
				"node-1",
				{
					kind: "task-run",
					id: "node-1",
					label: "test-task",
					state_type: "COMPLETED",
					start_time: "2023-09-27T15:50:39.995728+00:00",
					end_time: "2023-09-27T15:50:40.532868+00:00",
					parents: [],
					children: [],
					artifacts: [],
				},
			],
		],
		artifacts: [],
		...overrides,
	});

	describe("state mapping", () => {
		it("should map states from the API response", async () => {
			const mockStates = [
				{
					id: "state-1",
					timestamp: "2023-09-27T15:50:38.000000+00:00",
					type: "PENDING",
					name: "Pending",
				},
				{
					id: "state-2",
					timestamp: "2023-09-27T15:50:39.425118+00:00",
					type: "RUNNING",
					name: "Running",
				},
				{
					id: "state-3",
					timestamp: "2023-09-27T15:51:08.999871+00:00",
					type: "COMPLETED",
					name: "Completed",
				},
			];

			server.use(
				http.get(buildApiUrl("/flow_runs/:id/graph-v2"), () => {
					return HttpResponse.json(
						createMockGraphResponse({ states: mockStates }),
					);
				}),
			);

			const result = await fetchFlowRunGraph("test-flow-run-id");

			expect(result.states).toBeDefined();
			expect(result.states).toHaveLength(3);
			expect(result.states?.[0]).toEqual({
				id: "state-1",
				timestamp: new Date("2023-09-27T15:50:38.000000+00:00"),
				type: "PENDING",
				name: "Pending",
			});
			expect(result.states?.[1]).toEqual({
				id: "state-2",
				timestamp: new Date("2023-09-27T15:50:39.425118+00:00"),
				type: "RUNNING",
				name: "Running",
			});
			expect(result.states?.[2]).toEqual({
				id: "state-3",
				timestamp: new Date("2023-09-27T15:51:08.999871+00:00"),
				type: "COMPLETED",
				name: "Completed",
			});
		});

		it("should handle empty states array", async () => {
			server.use(
				http.get(buildApiUrl("/flow_runs/:id/graph-v2"), () => {
					return HttpResponse.json(createMockGraphResponse({ states: [] }));
				}),
			);

			const result = await fetchFlowRunGraph("test-flow-run-id");

			expect(result.states).toEqual([]);
		});

		it("should handle undefined states property", async () => {
			server.use(
				http.get(buildApiUrl("/flow_runs/:id/graph-v2"), () => {
					return HttpResponse.json(
						createMockGraphResponse({ states: undefined }),
					);
				}),
			);

			const result = await fetchFlowRunGraph("test-flow-run-id");

			expect(result.states).toEqual([]);
		});
	});
});
