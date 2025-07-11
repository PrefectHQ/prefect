import { QueryClient, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeDeployment } from "@/mocks/create-fake-deployment";
import type { Deployment } from "./index";
import {
	buildCountDeploymentsQuery,
	buildDeploymentDetailsQuery,
	buildFilterDeploymentsQuery,
	buildPaginateDeploymentsQuery,
	queryKeyFactory,
	useCreateDeployment,
	useCreateDeploymentSchedule,
	useDeleteDeployment,
	useDeleteDeploymentSchedule,
	useUpdateDeployment,
	useUpdateDeploymentSchedule,
} from "./index";

describe("deployments api", () => {
	const mockFetchDeploymentsAPI = (
		deployments: Array<Deployment>,
		total: number = deployments.length,
	) => {
		server.use(
			http.post(buildApiUrl("/deployments/paginate"), () => {
				return HttpResponse.json({
					results: deployments,
					count: total,
					page: 1,
					pages: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/deployments/count"), () => {
				return HttpResponse.json(total);
			}),
		);
	};

	const mockFilterDeploymentsAPI = (deployments: Array<Deployment>) => {
		server.use(
			http.post(buildApiUrl("/deployments/filter"), () => {
				return HttpResponse.json(deployments);
			}),
		);
	};

	const mockGetDeploymentAPI = (deployment: Deployment) => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(deployment);
			}),
		);
	};

	describe("buildPaginateDeploymentsQuery", () => {
		it("fetches paginated deployments with default parameters", async () => {
			const deployment = createFakeDeployment();
			mockFetchDeploymentsAPI([deployment]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			// Execute the query function
			await waitFor(() => {
				expect(result.current.data).toEqual({
					results: [deployment],
					page: 1,
					pages: 1,
					limit: 10,
					count: 1,
				});
			});
		});

		it("fetches paginated deployments with custom filter parameters", async () => {
			const deployment = createFakeDeployment();
			mockFetchDeploymentsAPI([deployment]);

			const filter = {
				page: 2,
				limit: 25,
				sort: "CREATED_DESC" as const,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildPaginateDeploymentsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual({
				results: [deployment],
				page: 1,
				pages: 1,
				limit: 10,
				count: 1,
			});
		});
	});

	describe("buildFilterDeploymentsQuery", () => {
		it("fetches filtered deployments", async () => {
			const queryClient = new QueryClient();

			const mockResponse = [createFakeDeployment()];
			mockFilterDeploymentsAPI(mockResponse);

			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockResponse);
		});
	});

	describe("buildCountDeploymentsQuery", () => {
		it("fetches deployment count with default parameters", async () => {
			mockFetchDeploymentsAPI([createFakeDeployment()]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildCountDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toBe(1);
			});
		});

		it("fetches deployment count with custom filter", async () => {
			mockFetchDeploymentsAPI([createFakeDeployment()]);

			const filter = {
				offset: 10,
				sort: "CREATED_DESC" as const,
				deployments: {
					operator: "and_" as const,
					name: { like_: "test" },
				},
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildCountDeploymentsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toBe(1);
			});
		});
	});

	describe("buildDeploymentDetailsQuery", () => {
		it("fetches deployment details", async () => {
			const queryClient = new QueryClient();

			const mockResponse = createFakeDeployment({ id: "my-id" });
			mockGetDeploymentAPI(mockResponse);

			const { result } = renderHook(
				() => useSuspenseQuery(buildDeploymentDetailsQuery("my-id")),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockResponse);
		});
	});

	describe("useCreateDeployment", () => {
		const mockCreateDeploymentAPI = (deployment: Deployment) => {
			server.use(
				http.post(buildApiUrl("/deployments"), () => {
					return HttpResponse.json(deployment);
				}),
			);
		};

		it("invalidates cache and fetches updated value", async () => {
			const mockDeployment = createFakeDeployment();
			mockFetchDeploymentsAPI([mockDeployment]);
			mockCreateDeploymentAPI(mockDeployment);
			const queryClient = new QueryClient();

			queryClient.setQueryData(queryKeyFactory["lists-filter"](), [
				mockDeployment,
			]);

			const { result: useListDeploymentsResult } = renderHook(
				() => useQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useCreateDeploymentResult } = renderHook(
				useCreateDeployment,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useCreateDeploymentResult.current.createDeployment({
					enforce_parameter_schema: mockDeployment.enforce_parameter_schema,
					flow_id: mockDeployment.flow_id,
					name: mockDeployment.name,
					paused: mockDeployment.paused,
				}),
			);

			await waitFor(() =>
				expect(useCreateDeploymentResult.current.isSuccess).toBe(true),
			);
			expect(useListDeploymentsResult.current.data?.count).toEqual(1);
			const newDeployment = useListDeploymentsResult.current.data?.results.find(
				(deployment) => deployment.id === mockDeployment.id,
			);
			expect(newDeployment).toEqual(mockDeployment);
		});
	});

	describe("useUpdateDeployment", () => {
		it("invalidates cache and fetches updated value", async () => {
			const MOCK_ID = "0";
			const mockDeployment = createFakeDeployment({
				id: MOCK_ID,
				paused: false,
			});
			const updatedMockDeployment = { ...mockDeployment, paused: true };
			mockFetchDeploymentsAPI([updatedMockDeployment]);

			const queryClient = new QueryClient();

			queryClient.setQueryData(queryKeyFactory.all(), [mockDeployment]);

			const { result: useListDeploymentsResult } = renderHook(
				() => useQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useUpdateDeploymentResult } = renderHook(
				useUpdateDeployment,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useUpdateDeploymentResult.current.updateDeployment({
					id: MOCK_ID,
					paused: true,
				}),
			);

			await waitFor(() =>
				expect(useUpdateDeploymentResult.current.isSuccess).toBe(true),
			);
			const result = useListDeploymentsResult.current.data?.results.find(
				(deployment) => deployment.id === MOCK_ID,
			);
			expect(result).toEqual(updatedMockDeployment);
		});
	});

	describe("useDeleteDeployment", () => {
		it("invalidates cache and fetches updated value", async () => {
			const mockDeployment = createFakeDeployment();
			mockFetchDeploymentsAPI([]);

			const queryClient = new QueryClient();

			queryClient.setQueryData(queryKeyFactory.all(), [mockDeployment]);

			const { result: useListDeploymentsResult } = renderHook(
				() => useQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useDeleteDeploymentResult } = renderHook(
				useDeleteDeployment,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useDeleteDeploymentResult.current.deleteDeployment(mockDeployment.id),
			);

			await waitFor(() =>
				expect(useDeleteDeploymentResult.current.isSuccess).toBe(true),
			);
			expect(useListDeploymentsResult.current.data?.results).toHaveLength(0);
		});
	});

	describe("useCreateDeploymentSchedule", () => {
		const MOCK_DEPLOYMENT_ID = "deployment-id";
		const MOCK_SCHEDULE_ID = "schedule-id";
		const MOCK_SCHEDULE = {
			id: MOCK_SCHEDULE_ID,
			created: "2024-01-01T00:00:00.000Z",
			updated: "2024-01-01T00:00:00.000Z",
			deployment_id: "deployment-id",
			schedule: {
				interval: 3600.0,
				anchor_date: "2024-01-01T00:00:00.000Z",
				timezone: "UTC",
			},
			active: false,
			max_scheduled_runs: null,
		};
		const MOCK_DEPLYOMENT = createFakeDeployment({
			id: MOCK_DEPLOYMENT_ID,
			schedules: [],
		});
		const MOCK_UPDATED_DEPLOYMENT = {
			...MOCK_DEPLYOMENT,
			schedules: [MOCK_SCHEDULE],
		};

		it("invalidates cache and fetches updated value", async () => {
			const queryClient = new QueryClient();
			// Original cached value
			queryClient.setQueryData(queryKeyFactory.all(), [MOCK_DEPLYOMENT]);

			// Updated fetch and cached value
			mockFetchDeploymentsAPI([MOCK_UPDATED_DEPLOYMENT]);

			const { result: useListDeploymentsResult } = renderHook(
				() => useQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useCreateDeploymentScheduleResult } = renderHook(
				useCreateDeploymentSchedule,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useCreateDeploymentScheduleResult.current.createDeploymentSchedule({
					deployment_id: MOCK_DEPLOYMENT_ID,
					schedule: {
						interval: 3600.0,
						anchor_date: "2024-01-01T00:00:00.000Z",
						timezone: "UTC",
					},
					active: false,
					max_scheduled_runs: null,
				}),
			);

			await waitFor(() =>
				expect(useCreateDeploymentScheduleResult.current.isSuccess).toBe(true),
			);
			expect(
				useListDeploymentsResult.current.data?.results[0].schedules,
			).toEqual([MOCK_SCHEDULE]);
		});
	});

	describe("useUpdateDeploymentSchedule", () => {
		const MOCK_DEPLOYMENT_ID = "deployment-id";
		const MOCK_SCHEDULE_ID = "schedule-id";
		const MOCK_SCHEDULE = {
			id: MOCK_SCHEDULE_ID,
			created: "2024-01-01T00:00:00.000Z",
			updated: "2024-01-01T00:00:00.000Z",
			deployment_id: "deployment-id",
			schedule: {
				interval: 3600.0,
				anchor_date: "2024-01-01T00:00:00.000Z",
				timezone: "UTC",
			},
			active: false,
			max_scheduled_runs: null,
		};
		const MOCK_UPDATED_SCHEDULE = { ...MOCK_SCHEDULE, active: true };
		const MOCK_DEPLYOMENT = createFakeDeployment({
			id: MOCK_DEPLOYMENT_ID,
			schedules: [MOCK_SCHEDULE],
		});
		const MOCK_UPDATED_DEPLOYMENT = {
			...MOCK_DEPLYOMENT,
			schedules: [MOCK_UPDATED_SCHEDULE],
		};

		it("invalidates cache and fetches updated value", async () => {
			const queryClient = new QueryClient();
			// Original cached value
			queryClient.setQueryData(queryKeyFactory.all(), [MOCK_DEPLYOMENT]);

			// Updated fetch and cached value
			mockFetchDeploymentsAPI([MOCK_UPDATED_DEPLOYMENT]);

			const { result: useListDeploymentsResult } = renderHook(
				() => useQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useUpdateDeploymentScheduleResult } = renderHook(
				useUpdateDeploymentSchedule,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useUpdateDeploymentScheduleResult.current.updateDeploymentSchedule({
					deployment_id: MOCK_DEPLOYMENT_ID,
					schedule_id: MOCK_SCHEDULE_ID,
					active: true,
				}),
			);

			await waitFor(() =>
				expect(useUpdateDeploymentScheduleResult.current.isSuccess).toBe(true),
			);
			expect(
				useListDeploymentsResult.current.data?.results[0].schedules,
			).toEqual([MOCK_UPDATED_SCHEDULE]);
		});
	});

	describe("useDeleteDeploymentSchedule", () => {
		const MOCK_DEPLOYMENT_ID = "deployment-id";
		const MOCK_SCHEDULE_ID = "schedule-id";
		const MOCK_SCHEDULE = {
			id: MOCK_SCHEDULE_ID,
			created: "2024-01-01T00:00:00.000Z",
			updated: "2024-01-01T00:00:00.000Z",
			deployment_id: "deployment-id",
			schedule: {
				interval: 3600.0,
				anchor_date: "2024-01-01T00:00:00.000Z",
				timezone: "UTC",
			},
			active: false,
			max_scheduled_runs: null,
		};
		const MOCK_DEPLYOMENT = createFakeDeployment({
			id: MOCK_DEPLOYMENT_ID,
			schedules: [MOCK_SCHEDULE],
		});
		const MOCK_UPDATED_DEPLOYMENT = {
			...MOCK_DEPLYOMENT,
			schedules: [],
		};

		it("invalidates cache and fetches updated value", async () => {
			const queryClient = new QueryClient();
			// Original cached value
			queryClient.setQueryData(queryKeyFactory.all(), [MOCK_DEPLYOMENT]);

			// Updated fetch and cached value
			mockFetchDeploymentsAPI([MOCK_UPDATED_DEPLOYMENT]);

			const { result: useListDeploymentsResult } = renderHook(
				() => useQuery(buildPaginateDeploymentsQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useDeleteDeploymentScheduleResult } = renderHook(
				useDeleteDeploymentSchedule,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useDeleteDeploymentScheduleResult.current.deleteDeploymentSchedule({
					deployment_id: MOCK_DEPLOYMENT_ID,
					schedule_id: MOCK_SCHEDULE_ID,
				}),
			);

			await waitFor(() =>
				expect(useDeleteDeploymentScheduleResult.current.isSuccess).toBe(true),
			);
			expect(
				useListDeploymentsResult.current.data?.results[0].schedules,
			).toHaveLength(0);
		});
	});
});
