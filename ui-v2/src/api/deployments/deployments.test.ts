import { createFakeDeployment } from "@/mocks/create-fake-deployment";
import { QueryClient, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { Deployment } from "./index";
import {
	buildCountDeploymentsQuery,
	buildPaginateDeploymentsQuery,
	queryKeyFactory,
	useDeleteDeployment,
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
			http.post("/deployments/count", () => {
				return HttpResponse.json(total);
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
});
