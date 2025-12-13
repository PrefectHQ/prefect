import { capitalize } from "@/utils";

/**
 * Get event prefixes for filtering.
 * For example, "prefect.flow-run.Completed" returns:
 * ["prefect.*", "prefect.flow-run.*", "prefect.flow-run.Completed"]
 */
export function getEventPrefixes(eventName: string): string[] {
	const prefixes: string[] = [];
	const parts = eventName.split(".");

	for (let i = 1; i < parts.length; i++) {
		const prefix = parts.slice(0, i).join(".");
		prefixes.push(`${prefix}.*`);
	}

	return [...prefixes, eventName];
}

/**
 * Format event label from event name.
 * For example, "prefect.flow-run.Completed" becomes "Flow Run Completed"
 */
export function formatEventLabel(eventName: string): string {
	// Remove prefect. or prefect-cloud. prefix
	let label = eventName;
	if (label.startsWith("prefect.")) {
		label = label.slice(8);
	} else if (label.startsWith("prefect-cloud.")) {
		label = label.slice(14);
	}

	// Replace dashes and dots with spaces, then capitalize each word
	return label
		.split(/[._-]/)
		.map((word) => capitalize(word.toLowerCase()))
		.join(" ");
}
