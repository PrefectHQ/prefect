import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { buildListWorkPoolTypesQuery } from "./collections";

describe("workers api", () => {
	const mockWorkersResponse = {
		prefect: {
			process: {
				type: "process",
				display_name: "Process",
				description: "Execute flow runs as subprocesses",
				logo_url: "https://example.com/process.png",
				is_beta: false,
				default_base_job_configuration: {
					job_configuration: {
						command: "{{ command }}",
						env: "{{ env }}",
					},
					variables: {
						properties: {
							command: { type: "string" },
							env: { type: "object" },
						},
					},
				},
			},
		},
		"prefect-aws": {
			ecs: {
				type: "ecs",
				display_name: "AWS ECS",
				description: "Execute flow runs on AWS ECS",
				logo_url: "https://example.com/ecs.png",
				is_beta: false,
				default_base_job_configuration: {
					job_configuration: {
						image: "{{ image }}",
					},
					variables: {
						properties: {
							image: { type: "string" },
						},
					},
				},
			},
		},
	};

	describe("buildListWorkPoolTypesQuery", () => {
		it("fetches work pool types metadata", async () => {
			server.use(
				http.get(
					buildApiUrl("/collections/views/aggregate-worker-metadata"),
					() => {
						return HttpResponse.json(mockWorkersResponse);
					},
				),
			);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListWorkPoolTypesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockWorkersResponse);
		});

		it("handles empty response", async () => {
			server.use(
				http.get(
					buildApiUrl("/collections/views/aggregate-worker-metadata"),
					() => {
						return HttpResponse.json({});
					},
				),
			);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildListWorkPoolTypesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual({});
		});
	});
});
