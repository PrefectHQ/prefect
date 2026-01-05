import createClient from "openapi-fetch";
import type { paths } from "@/api/prefect";

export type PrefectApiClient = ReturnType<typeof createClient<paths>>;

export function createPrefectApiClient(): PrefectApiClient {
	const baseUrl = process.env.PREFECT_API_URL ?? "http://localhost:4200/api";
	return createClient<paths>({ baseUrl });
}
