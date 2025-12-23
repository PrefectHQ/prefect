import { useEffect } from "react";

type StateType =
	| "SCHEDULED"
	| "PENDING"
	| "RUNNING"
	| "COMPLETED"
	| "FAILED"
	| "CANCELLED"
	| "CANCELLING"
	| "CRASHED"
	| "PAUSED";

function getPreferredColorScheme(): "dark" | "light" | "no-preference" {
	if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
		return "dark";
	}
	if (window.matchMedia("(prefers-color-scheme: light)").matches) {
		return "light";
	}
	return "no-preference";
}

/**
 * A hook that sets the browser favicon based on the provided state type.
 * Resets the favicon to the default when the component unmounts.
 *
 * @param stateType - The state type to display in the favicon (e.g., "COMPLETED", "FAILED")
 * @returns void
 *
 * @example
 * ```tsx
 * // Set favicon based on task run state
 * useStateFavicon(taskRun.state_type);
 * ```
 */
export function useStateFavicon(stateType: StateType | null | undefined): void {
	useEffect(() => {
		const colorScheme = getPreferredColorScheme();
		const favicon16 =
			colorScheme === "dark"
				? document.getElementById("favicon-16-dark")
				: document.getElementById("favicon-16");
		const favicon32 =
			colorScheme === "dark"
				? document.getElementById("favicon-32-dark")
				: document.getElementById("favicon-32");

		if (stateType) {
			const faviconPath = `/${stateType.toLowerCase()}.svg`;
			favicon16?.setAttribute("href", faviconPath);
			favicon32?.setAttribute("href", faviconPath);
		}

		return () => {
			// Reset to default favicon on unmount
			if (colorScheme === "dark") {
				favicon16?.setAttribute("href", "/favicon-16x16-dark.png");
				favicon32?.setAttribute("href", "/favicon-32x32-dark.png");
			} else {
				favicon16?.setAttribute("href", "/favicon-16x16.png");
				favicon32?.setAttribute("href", "/favicon-32x32.png");
			}
		};
	}, [stateType]);
}
