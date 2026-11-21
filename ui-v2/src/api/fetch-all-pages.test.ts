import { describe, expect, it, vi } from "vitest";
import { fetchAllPages } from "./fetch-all-pages";

const makeRows = (count: number) =>
	Array.from({ length: count }, (_, i) => ({ id: String(i) }));

// Mimics a filter endpoint that caps every response at `serverLimit`.
const serve = (rows: Array<{ id: string }>, serverLimit: number) =>
	vi.fn((offset: number) =>
		Promise.resolve(rows.slice(offset, offset + serverLimit)),
	);

describe("fetchAllPages", () => {
	it("reads every page using the server's page size", async () => {
		const rows = makeRows(120);
		const fetchPage = serve(rows, 50);

		expect(await fetchAllPages(fetchPage)).toEqual(rows);
		expect(fetchPage.mock.calls.map(([offset]) => offset)).toEqual([
			0, 50, 100,
		]);
	});

	it("stops after an empty page when the total is a multiple of the page size", async () => {
		const rows = makeRows(100);
		const fetchPage = serve(rows, 50);

		expect(await fetchAllPages(fetchPage)).toEqual(rows);
		expect(fetchPage).toHaveBeenCalledTimes(3);
	});

	it("returns an empty list when there are no rows", async () => {
		const fetchPage = serve([], 50);

		expect(await fetchAllPages(fetchPage)).toEqual([]);
		expect(fetchPage).toHaveBeenCalledTimes(1);
	});

	it("starts from the given offset", async () => {
		const rows = makeRows(30);
		const fetchPage = serve(rows, 50);

		expect(await fetchAllPages(fetchPage, 10)).toEqual(rows.slice(10));
	});

	it("stops when a page brings nothing new", async () => {
		const rows = makeRows(3);
		// Ignores the offset and always returns the same rows
		const fetchPage = vi.fn(() => Promise.resolve(rows));

		expect(await fetchAllPages(fetchPage)).toEqual(rows);
		expect(fetchPage).toHaveBeenCalledTimes(2);
	});
});
