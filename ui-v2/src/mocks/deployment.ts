import {
	rand,
	randAlphaNumeric,
	randPastDate,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { Deployment } from "@/api/deployments";

export const createMockDeployment = (
	overrides?: Partial<Deployment>,
): Deployment => ({
	id: randUuid(),
	created: randPastDate().toISOString(),
	updated: randPastDate().toISOString(),
	name: `${randWord()}-${randAlphaNumeric({ length: 6 }).join("").toLowerCase()}`,
	version: "1.0.0",
	description: null,
	flow_id: randUuid(),
	schedules: [],
	paused: false,
	parameters: {},
	tags: [],
	work_queue_name: null,
	last_polled: null,
	parameter_openapi_schema: null,
	path: null,
	pull_steps: null,
	entrypoint: null,
	storage_document_id: null,
	infrastructure_document_id: null,
	created_by: null,
	work_pool_name: null,
	enforce_parameter_schema: false,
	job_variables: {},
	global_concurrency_limit: null,
	status: rand(["READY", "NOT_READY"]),
	...overrides,
});
