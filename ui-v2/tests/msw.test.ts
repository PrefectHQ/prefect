import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
import { buildApiUrl } from "./utils";

const require = createRequire(import.meta.url);

describe("MSW worker compatibility", () => {
	it("serves the worker protocol expected by the installed MSW package", () => {
		const worker = readFileSync(
			require.resolve("../public/mockServiceWorker.js"),
			"utf8",
		);
		const installedWorker = readFileSync(
			require.resolve("msw/mockServiceWorker.js"),
			"utf8",
		);
		const checksum = /const INTEGRITY_CHECKSUM = ["']([^"']+)["']/;

		expect(worker).toMatch(checksum);
		expect(worker.match(checksum)?.[1]).toBe(
			installedWorker.match(checksum)?.[1],
		);
	});

	it("fails unhandled HTTP requests without reaching the network", async () => {
		const url = buildApiUrl("/unhandled-msw-request");
		const response = await fetch(url);

		expect(response.status).toBe(500);
		await expect(response.json()).resolves.toMatchObject({
			message: `No request handler found for GET ${url}`,
		});
	});
});
