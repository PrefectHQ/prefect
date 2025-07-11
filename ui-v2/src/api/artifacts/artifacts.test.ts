import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeArtifact } from "@/mocks";

import {
	type Artifact,
	buildCountArtifactsQuery,
	buildGetArtifactQuery,
	buildListArtifactsQuery,
} from "./index";

describe("artifacts queries and mutations", () => {
	const seedArtifactsData = () => [
		createFakeArtifact({ id: "0" }),
		createFakeArtifact({ id: "1" }),
	];

	const mockFetchListArtifactsAPI = (artifacts: Array<Artifact>) => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json(artifacts);
			}),
		);
	};

	const mockFetchGetArtifactAPI = (artifact: Artifact) => {
		server.use(
			http.get(buildApiUrl("/artifacts/:id"), () => {
				return HttpResponse.json(artifact);
			}),
		);
	};

	const mockFetchCountArtifactsAPI = (count: number) => {
		server.use(
			http.post(buildApiUrl("/artifacts/count"), () => {
				return HttpResponse.json(count);
			}),
		);
	};

	const filter = { sort: "ID_DESC", offset: 0 } as const;

	it("is stores artifact list data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedArtifactsData();
		mockFetchListArtifactsAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildListArtifactsQuery(filter)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	it("is retrieves single artifact data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockArtifact = createFakeArtifact();
		mockFetchGetArtifactAPI(mockArtifact);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildGetArtifactQuery(mockArtifact.id ?? "0")),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockArtifact);
	});

	it("is retrieves count of artifacts", async () => {
		// ------------ Mock API requests when cache is empty
		const count = 2;
		mockFetchCountArtifactsAPI(count);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildCountArtifactsQuery(filter)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(count);
	});
});
