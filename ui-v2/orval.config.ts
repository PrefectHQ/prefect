import { defineConfig } from "orval";

export default defineConfig({
	api: {
		input: {
			target: "./oss_schema.json",
		},
		output: {
			mode: "tags-split",
			target: "./src/api/generated",
			schemas: "./src/api/models",
			client: "react-query",
			httpClient: "fetch",
			baseUrl: "http://prefect.grose.click/api",
			override: {
				query: {
					useQuery: true,
					useInfinite: false,
					useSuspenseQuery: true,
				},
			},
		},
	},
});
