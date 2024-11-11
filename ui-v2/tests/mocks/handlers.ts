import { http, HttpResponse } from "msw";

export const handlers = [
	http.post("http://localhost:4200/api/flows/paginate", () => {
		return HttpResponse.json({
			results: [
				{ id: "1", name: "Flow 1", tags: [] },
				{ id: "2", name: "Flow 2", tags: [] },
			],
		});
	}),
	http.post("http://localhost:4200/api/flow_runs/filter", () => {
		return HttpResponse.json([
			{ id: "1", name: "Flow 1", tags: [] },
			{ id: "2", name: "Flow 2", tags: [] },
		]);
	}),

	http.post("http://localhost:4200/api/deployments/count", () => {
		return HttpResponse.json(1);
	}),

	http.post("http://localhost:4200/api/variables/", () => {
		return HttpResponse.json({ status: "success" }, { status: 201 });
	}),
];
