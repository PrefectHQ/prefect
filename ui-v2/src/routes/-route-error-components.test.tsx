import { describe, expect, it } from "vitest";
import { categorizeError } from "@/api/error-utils";

// Tests for the selective error handling logic used in route error components
// (FlowsErrorComponent, DeploymentsErrorComponent, WorkPoolsErrorComponent)
//
// The route error components use this pattern:
//   const serverError = categorizeError(error);
//   if (serverError.type !== "server-error" && serverError.type !== "client-error") {
//     throw error; // Bubble up to root error component
//   }
//   return <RouteErrorState error={serverError} onRetry={reset} />;
describe("Route Error Components - Selective Error Handling", () => {
	// Helper to create errors that categorizeError will classify as specific types
	const createServerError = () => new Error("Request failed with status 500");
	const createClientError = () => new Error("Request failed with status 404");
	const createNetworkError = () => {
		const error = new TypeError("Failed to fetch");
		return error;
	};
	const createUnknownError = () => new Error("Something unexpected happened");

	describe("categorizeError classification", () => {
		it("classifies 5xx errors as server-error", () => {
			const error = createServerError();
			const result = categorizeError(error);
			expect(result.type).toBe("server-error");
		});

		it("classifies 4xx errors as client-error", () => {
			const error = createClientError();
			const result = categorizeError(error);
			expect(result.type).toBe("client-error");
		});

		it("classifies TypeError with 'Failed to fetch' as network-error", () => {
			const error = createNetworkError();
			const result = categorizeError(error);
			expect(result.type).toBe("network-error");
		});

		it("classifies other errors as unknown-error", () => {
			const error = createUnknownError();
			const result = categorizeError(error);
			expect(result.type).toBe("unknown-error");
		});
	});

	describe("FlowsErrorComponent", () => {
		it("handles server errors (5xx) at route level", () => {
			const error = createServerError();
			const serverError = categorizeError(error);

			// Verify the error would be handled (not re-thrown)
			const shouldHandle =
				serverError.type === "server-error" ||
				serverError.type === "client-error";
			expect(shouldHandle).toBe(true);
		});

		it("handles client errors (4xx) at route level", () => {
			const error = createClientError();
			const serverError = categorizeError(error);

			const shouldHandle =
				serverError.type === "server-error" ||
				serverError.type === "client-error";
			expect(shouldHandle).toBe(true);
		});

		it("re-throws network errors to bubble up to root", () => {
			const error = createNetworkError();
			const serverError = categorizeError(error);

			const shouldRethrow =
				serverError.type !== "server-error" &&
				serverError.type !== "client-error";
			expect(shouldRethrow).toBe(true);
		});

		it("re-throws unknown errors to bubble up to root", () => {
			const error = createUnknownError();
			const serverError = categorizeError(error);

			const shouldRethrow =
				serverError.type !== "server-error" &&
				serverError.type !== "client-error";
			expect(shouldRethrow).toBe(true);
		});
	});

	describe("Error handling logic pattern", () => {
		// This tests the exact logic pattern used in all three route error components
		const shouldHandleAtRouteLevel = (error: unknown): boolean => {
			const serverError = categorizeError(error);
			return (
				serverError.type === "server-error" ||
				serverError.type === "client-error"
			);
		};

		it("handles 500 Internal Server Error at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 500")),
			).toBe(true);
		});

		it("handles 502 Bad Gateway at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 502")),
			).toBe(true);
		});

		it("handles 503 Service Unavailable at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 503")),
			).toBe(true);
		});

		it("handles 400 Bad Request at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 400")),
			).toBe(true);
		});

		it("handles 401 Unauthorized at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 401")),
			).toBe(true);
		});

		it("handles 403 Forbidden at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 403")),
			).toBe(true);
		});

		it("handles 404 Not Found at route level", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Request failed with status 404")),
			).toBe(true);
		});

		it("bubbles up network errors (Failed to fetch) to root", () => {
			expect(shouldHandleAtRouteLevel(new TypeError("Failed to fetch"))).toBe(
				false,
			);
		});

		it("bubbles up network errors (NetworkError) to root", () => {
			expect(shouldHandleAtRouteLevel(new TypeError("NetworkError"))).toBe(
				false,
			);
		});

		it("bubbles up unknown errors to root", () => {
			expect(
				shouldHandleAtRouteLevel(new Error("Unexpected error occurred")),
			).toBe(false);
		});

		it("bubbles up non-Error objects to root", () => {
			expect(shouldHandleAtRouteLevel("string error")).toBe(false);
		});

		it("bubbles up null/undefined to root", () => {
			expect(shouldHandleAtRouteLevel(null)).toBe(false);
			expect(shouldHandleAtRouteLevel(undefined)).toBe(false);
		});
	});
});
