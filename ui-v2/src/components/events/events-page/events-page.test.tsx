import { describe, expect, it } from "vitest";
import { EventsPage, type EventsPageProps } from "./events-page";

describe("EventsPage", () => {
	it("exports EventsPage component", () => {
		expect(EventsPage).toBeDefined();
		expect(typeof EventsPage).toBe("function");
	});

	it("has correct prop types", () => {
		const spanSearchProps: EventsPageProps = {
			search: { rangeType: "span", seconds: -86400 },
			onSearchChange: () => {},
		};
		expect(spanSearchProps.search.rangeType).toBe("span");

		const rangeSearchProps: EventsPageProps = {
			search: {
				rangeType: "range",
				start: "2024-01-01T00:00:00.000Z",
				end: "2024-01-02T00:00:00.000Z",
			},
			onSearchChange: () => {},
		};
		expect(rangeSearchProps.search.rangeType).toBe("range");

		const filteredSearchProps: EventsPageProps = {
			search: {
				rangeType: "span",
				seconds: -86400,
				resource: ["prefect.flow.flow-1"],
				event: ["prefect.flow-run."],
			},
			onSearchChange: () => {},
		};
		expect(filteredSearchProps.search.resource).toEqual([
			"prefect.flow.flow-1",
		]);
		expect(filteredSearchProps.search.event).toEqual(["prefect.flow-run."]);
	});
});
