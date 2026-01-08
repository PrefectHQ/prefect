import { HttpResponse, http } from "msw";

export const buildApiUrl = (path: string) => {
	return `${import.meta.env.VITE_API_URL}${path}`;
};

const artifactsHandlers = [
	http.post(buildApiUrl("/artifacts/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(buildApiUrl("/artifacts/count"), () => {
		return HttpResponse.json(0);
	}),
];

const automationsHandlers = [
	http.get(buildApiUrl("/automations/related-to/:resource_id"), () => {
		return HttpResponse.json([]);
	}),

	http.post(buildApiUrl("/automations/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(buildApiUrl("/automations/"), () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),

	http.patch(buildApiUrl("/automations/:id"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
	http.delete(buildApiUrl("/automations/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const blockDocumentsHandlers = [
	http.post(buildApiUrl("/block_documents/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(buildApiUrl("/block_documents/count"), () => {
		return HttpResponse.json(0);
	}),

	http.delete(buildApiUrl("/block_documents/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),

	http.patch(buildApiUrl("/block_documents/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const blockSchemasHandlers = [
	http.post(buildApiUrl("/block_schemas/filter"), () => {
		return HttpResponse.json([]);
	}),
];

const blockTypesHandlers = [
	http.post(buildApiUrl("/block_types/filter"), () => {
		return HttpResponse.json([]);
	}),
];

const eventsHandlers = [
	http.post(buildApiUrl("/events/filter"), () => {
		return HttpResponse.json({
			events: [],
			total: 0,
			next_page: null,
		});
	}),

	http.get(buildApiUrl("/events/filter/next"), () => {
		return HttpResponse.json({
			events: [],
			total: 0,
			next_page: null,
		});
	}),

	http.post(buildApiUrl("/events/count-by/:countable"), () => {
		return HttpResponse.json([]);
	}),
];

const deploymentsHandlers = [
	http.get(buildApiUrl("/deployments/:id"), ({ params }) => {
		const id = params.id as string;
		return HttpResponse.json({
			id,
			name: `Deployment ${id}`,
			tags: [],
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			flow_id: "flow-1",
		});
	}),

	http.post(buildApiUrl("/deployments/filter"), () => {
		return HttpResponse.json([
			{ id: "deployment-1", name: "Deployment 1", tags: [] },
			{ id: "deployment-2", name: "Deployment 2", tags: [] },
		]);
	}),

	http.patch(buildApiUrl("/deployments/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),

	http.delete(buildApiUrl("/deployments/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),

	http.post(buildApiUrl("/deployments/:id/schedules"), () => {
		return HttpResponse.json({ status: 201 });
	}),

	http.patch(buildApiUrl("/deployments/:id/schedules/:schedule_id"), () => {
		return HttpResponse.json({ status: 204 });
	}),

	http.delete(buildApiUrl("/deployments/:id/schedules/:schedule_id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const flowHandlers = [
	http.get(buildApiUrl("/flows/:id"), () => {
		return HttpResponse.json({
			id: "1",
			name: "Flow 1",
			tags: [],
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			labels: {},
		});
	}),

	http.post(buildApiUrl("/flows/paginate"), () => {
		return HttpResponse.json({
			results: [
				{ id: "1", name: "Flow 1", tags: [] },
				{ id: "2", name: "Flow 2", tags: [] },
			],
		});
	}),

	http.post(buildApiUrl("/flows/filter"), () => {
		return HttpResponse.json([
			{ id: "1", name: "Flow 1", tags: [] },
			{ id: "2", name: "Flow 2", tags: [] },
		]);
	}),

	http.post(buildApiUrl("/deployments/count"), () => {
		return HttpResponse.json(1);
	}),

	http.post(buildApiUrl("/ui/flows/count-deployments"), () => {
		return HttpResponse.json({});
	}),

	http.post(buildApiUrl("/ui/flows/next-runs"), () => {
		return HttpResponse.json({});
	}),

	http.delete(buildApiUrl("/flows/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const flowRunHandlers = [
	http.get(buildApiUrl("/flow_runs/:id"), () => {
		return HttpResponse.json({
			id: "1",
			name: "test-flow-run",
			flow_id: "flow-1",
			state_type: "COMPLETED",
			state_name: "Completed",
			tags: [],
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			state: {
				id: "state-1",
				type: "COMPLETED",
				name: "Completed",
				timestamp: new Date().toISOString(),
			},
		});
	}),

	http.post(buildApiUrl("/flow_runs/filter"), () => {
		return HttpResponse.json([
			{ id: "1", name: "Flow 1", tags: [] },
			{ id: "2", name: "Flow 2", tags: [] },
		]);
	}),

	http.post(buildApiUrl("/flow_runs/paginate"), () => {
		return HttpResponse.json({
			results: [],
			count: 0,
			pages: 0,
			page: 1,
			limit: 10,
		});
	}),

	http.post(buildApiUrl("/flow_runs/count"), () => {
		return HttpResponse.json(0);
	}),

	http.delete(buildApiUrl("/flow_runs/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const globalConcurrencyLimitsHandlers = [
	http.post(buildApiUrl("/v2/concurrency_limits/filter"), () => {
		return HttpResponse.json([]);
	}),
	http.post(buildApiUrl("/v2/concurrency_limits/"), () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),
	http.patch(buildApiUrl("/v2/concurrency_limits/:id_or_name"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
	http.delete(buildApiUrl("/v2/concurrency_limits/:id_or_name"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const settingsHandlers = [
	http.post(buildApiUrl("/admin/settings"), () => {
		return HttpResponse.json({});
	}),
];

// UI Settings handler - note: /ui-settings is at the base URL, not under /api
// In tests, VITE_API_URL is set to http://localhost:4200/api, so we need to
// handle the request at the base URL (stripping /api)
const uiSettingsHandlers = [
	http.get("http://localhost:4200/ui-settings", () => {
		return HttpResponse.json({
			api_url: "http://localhost:4200/api",
			csrf_enabled: false,
			auth: null,
			flags: [],
		});
	}),
	// Also handle the case where the base URL might be different
	http.get(/\/ui-settings$/, () => {
		return HttpResponse.json({
			api_url: "http://localhost:4200/api",
			csrf_enabled: false,
			auth: null,
			flags: [],
		});
	}),
];

const taskRunHandlers = [
	http.post(buildApiUrl("/task_runs/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(buildApiUrl("/task_runs/paginate"), () => {
		return HttpResponse.json({
			results: [],
			count: 0,
			pages: 0,
			page: 1,
			limit: 10,
		});
	}),

	http.post(buildApiUrl("/task_runs/count"), () => {
		return HttpResponse.json(0);
	}),

	http.post(buildApiUrl("/task_runs/history"), () => {
		return HttpResponse.json([]);
	}),

	http.delete(buildApiUrl("/task_runs/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const taskRunConcurrencyLimitsHandlers = [
	http.post(buildApiUrl("/concurrency_limits/filter"), () => {
		return HttpResponse.json([]);
	}),
	http.post(buildApiUrl("/concurrency_limits/tag/:tag/reset"), () => {
		return HttpResponse.json({ status: 200 });
	}),
	http.delete(buildApiUrl("/concurrency_limits/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const variablesHandlers = [
	http.post(buildApiUrl("/variables/"), () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),

	http.post(buildApiUrl("/variables/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(buildApiUrl("/variables/count"), () => {
		return HttpResponse.json(0);
	}),

	http.patch(buildApiUrl("/variables/:id"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
	http.delete(buildApiUrl("/variables/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const versionHandlers = [
	http.post(buildApiUrl("/admin/version"), () => {
		return HttpResponse.json("3.0.0");
	}),
];

const workPoolsHandlers = [
	http.post(buildApiUrl("/work_pools/filter"), () => {
		return HttpResponse.json([]);
	}),
	http.post(buildApiUrl("/work_pools/count"), () => {
		return HttpResponse.json(0);
	}),
	http.post(buildApiUrl("/work_pools/:name/workers/filter"), () => {
		return HttpResponse.json([]);
	}),
];

const workQueuesHandlers = [
	http.post(buildApiUrl("/work_queues/filter"), () => {
		return HttpResponse.json([]);
	}),
];

const workPoolQueuesHandlers = [
	http.post(buildApiUrl("/work_pools/:work_pool_name/queues/filter"), () => {
		return HttpResponse.json([]);
	}),
	http.get(buildApiUrl("/work_queues/:id"), () => {
		return HttpResponse.json({});
	}),
	http.patch(buildApiUrl("/work_queues/:id"), () => {
		return HttpResponse.json({});
	}),
	http.delete(buildApiUrl("/work_queues/:id"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
];

export const handlers = [
	...uiSettingsHandlers,
	...artifactsHandlers,
	...automationsHandlers,
	...blockDocumentsHandlers,
	...blockSchemasHandlers,
	...blockTypesHandlers,
	...deploymentsHandlers,
	...eventsHandlers,
	...flowHandlers,
	...flowRunHandlers,
	...globalConcurrencyLimitsHandlers,
	...settingsHandlers,
	...taskRunHandlers,
	...taskRunConcurrencyLimitsHandlers,
	...variablesHandlers,
	...versionHandlers,
	...workPoolsHandlers,
	...workQueuesHandlers,
	...workPoolQueuesHandlers,
];
