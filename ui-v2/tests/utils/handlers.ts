import { http, HttpResponse } from "msw";

export const buildApiUrl = (path: string) => {
	return `${import.meta.env.VITE_API_URL}${path}`;
};

const automationsHandlers = [
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

const deploymentsHandlers = [
	http.delete(buildApiUrl("/deployments/:id"), () => {
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

export const handlers = [
	...automationsHandlers,
	...deploymentsHandlers,
	...flowHandlers,
	...flowRunHandlers,
	...globalConcurrencyLimitsHandlers,
	...taskRunConcurrencyLimitsHandlers,
	...variablesHandlers,
];
