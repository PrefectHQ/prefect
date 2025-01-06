import { http, HttpResponse } from "msw";

export const prefectURL = (path: string) => {
	return `${import.meta.env.VITE_API_URL}${path}`;
};

const automationsHandlers = [
	http.post(prefectURL("/automations/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(prefectURL("/automations/"), () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),

	http.patch(prefectURL("/automations/:id"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
	http.delete(prefectURL("/automations/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const flowHandlers = [
	http.post(prefectURL("/flows/paginate"), () => {
		return HttpResponse.json({
			results: [
				{ id: "1", name: "Flow 1", tags: [] },
				{ id: "2", name: "Flow 2", tags: [] },
			],
		});
	}),
	http.post(prefectURL("/flow_runs/filter"), () => {
		return HttpResponse.json([
			{ id: "1", name: "Flow 1", tags: [] },
			{ id: "2", name: "Flow 2", tags: [] },
		]);
	}),

	http.post(prefectURL("/deployments/count"), () => {
		return HttpResponse.json(1);
	}),
];

const globalConcurrencyLimitsHandlers = [
	http.post(prefectURL("/v2/concurrency_limits/filter"), () => {
		return HttpResponse.json([]);
	}),
	http.post(prefectURL("/v2/concurrency_limits/"), () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),
	http.patch(prefectURL("/v2/concurrency_limits/:id_or_name"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
	http.delete(prefectURL("/v2/concurrency_limits/:id_or_name"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const taskRunConcurrencyLimitsHandlers = [
	http.post(prefectURL("/concurrency_limits/filter"), () => {
		return HttpResponse.json([]);
	}),
	http.post(prefectURL("/concurrency_limits/tag/:tag/reset"), () => {
		return HttpResponse.json({ status: 200 });
	}),
	http.delete(prefectURL("/concurrency_limits/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

const variablesHandlers = [
	http.post(prefectURL("/variables/"), () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),

	http.post(prefectURL("/variables/filter"), () => {
		return HttpResponse.json([]);
	}),

	http.post(prefectURL("/variables/count"), () => {
		return HttpResponse.json(0);
	}),

	http.patch(prefectURL("/variables/:id"), () => {
		return new HttpResponse(null, { status: 204 });
	}),
	http.delete(prefectURL("/variables/:id"), () => {
		return HttpResponse.json({ status: 204 });
	}),
];

export const handlers = [
	...automationsHandlers,
	...flowHandlers,
	...globalConcurrencyLimitsHandlers,
	...taskRunConcurrencyLimitsHandlers,
	...variablesHandlers,
];
