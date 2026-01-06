import { describe, expect, it } from "vitest";
import { categorizeError, isNetworkError } from "./error-utils";

describe("isNetworkError", () => {
	it("returns true for 'Failed to fetch' TypeError", () => {
		const error = new TypeError("Failed to fetch");
		expect(isNetworkError(error)).toBe(true);
	});

	it("returns true for 'NetworkError' TypeError", () => {
		const error = new TypeError(
			"NetworkError when attempting to fetch resource",
		);
		expect(isNetworkError(error)).toBe(true);
	});

	it("returns false for other TypeErrors", () => {
		const error = new TypeError("Cannot read property 'foo' of undefined");
		expect(isNetworkError(error)).toBe(false);
	});

	it("returns false for regular Errors", () => {
		const error = new Error("Failed to fetch");
		expect(isNetworkError(error)).toBe(false);
	});

	it("returns false for non-Error values", () => {
		expect(isNetworkError("Failed to fetch")).toBe(false);
		expect(isNetworkError(null)).toBe(false);
		expect(isNetworkError(undefined)).toBe(false);
	});
});

describe("categorizeError", () => {
	it("categorizes network errors correctly", () => {
		const error = new TypeError("Failed to fetch");
		const result = categorizeError(error);

		expect(result.type).toBe("network-error");
		expect(result.message).toBe("Unable to connect to Prefect server");
	});

	it("categorizes 5xx errors as server errors", () => {
		const error = new Error("Failed to fetch UI settings: status 500");
		const result = categorizeError(error);

		expect(result.type).toBe("server-error");
		expect(result.statusCode).toBe(500);
	});

	it("categorizes 4xx errors as client errors", () => {
		const error = new Error("Request failed with status 404");
		const result = categorizeError(error);

		expect(result.type).toBe("client-error");
		expect(result.statusCode).toBe(404);
	});

	it("categorizes unknown errors with context", () => {
		const error = new Error("Something went wrong");
		const result = categorizeError(error, "Custom context");

		expect(result.type).toBe("unknown-error");
		expect(result.details).toBe("Something went wrong");
	});

	it("handles non-Error values", () => {
		const result = categorizeError("string error", "Fallback context");

		expect(result.type).toBe("unknown-error");
		expect(result.details).toBe("Fallback context");
	});
});
