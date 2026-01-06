/**
 * Error types for server connection failures
 */
export type ServerErrorType =
	| "network-error" // Server unreachable, network down, CORS, etc.
	| "server-error" // Server returned 5xx error
	| "client-error" // Server returned 4xx error (misconfiguration)
	| "unknown-error"; // Unexpected error

export type ServerError = {
	type: ServerErrorType;
	message: string;
	details?: string;
	statusCode?: number;
};

/**
 * Determines if an error is a network-level failure (server unreachable)
 */
export function isNetworkError(error: unknown): boolean {
	if (error instanceof TypeError) {
		// "Failed to fetch" is the standard message for network errors
		// This includes: server down, CORS issues, network offline
		return (
			error.message.includes("Failed to fetch") ||
			error.message.includes("NetworkError") ||
			error.message.includes("Network request failed")
		);
	}
	return false;
}

/**
 * Categorizes an error and returns a user-friendly ServerError object
 */
export function categorizeError(error: unknown, context?: string): ServerError {
	// Network errors (server unreachable)
	if (isNetworkError(error)) {
		return {
			type: "network-error",
			message: "Unable to connect to Prefect server",
			details:
				"The server may be down, starting up, or there may be a network issue. The app will automatically retry.",
		};
	}

	// Error with status code (from our API client)
	if (error instanceof Error) {
		const statusMatch = error.message.match(/status[:\s]*(\d{3})/i);
		if (statusMatch) {
			const statusCode = Number.parseInt(statusMatch[1], 10);

			if (statusCode >= 500) {
				return {
					type: "server-error",
					message: "Prefect server error",
					details: `The server returned an error (${statusCode}). This may be a temporary issue.`,
					statusCode,
				};
			}

			if (statusCode >= 400) {
				return {
					type: "client-error",
					message: "Configuration error",
					details: `The server rejected the request (${statusCode}). Check your Prefect configuration.`,
					statusCode,
				};
			}
		}

		// Generic Error with message
		return {
			type: "unknown-error",
			message: "Connection error",
			details:
				error.message ||
				"An unexpected error occurred while connecting to the server.",
		};
	}

	// Completely unknown error
	return {
		type: "unknown-error",
		message: "Unexpected error",
		details: context || "An unexpected error occurred. Please try again.",
	};
}
