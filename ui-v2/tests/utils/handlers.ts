import { HttpResponse, http } from "msw";

export const buildApiUrl = (path: string) => {
	return `${import.meta.env.VITE_API_URL}${path}`;
};

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

const deploymentsHandlers = [
	http.post(buildApiUrl("/deployments/filter"), () => {
		return HttpResponse.json([]);
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
	http.post(buildApiUrl("/flows/paginate"), () => {
		return HttpResponse.json({
			results: [
				{ id: "1", name: "Flow 1", tags: [] },
				{ id: "2", name: "Flow 2", tags: [] },
			],
		});
	}),

	http.post(buildApiUrl("/deployments/count"), () => {
		return HttpResponse.json(1);
	}),
];

const flowRunHandlers = [
	http.post(buildApiUrl("/flow_runs/filter"), () => {
		return HttpResponse.json([
			{ id: "1", name: "Flow 1", tags: [] },
			{ id: "2", name: "Flow 2", tags: [] },
		]);
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

const taskRunHandlers = [
	http.post(buildApiUrl("/task_runs/filter"), () => {
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
	...automationsHandlers,
	...blockDocumentsHandlers,
	...blockSchemasHandlers,
	...blockTypesHandlers,
	...deploymentsHandlers,
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
