import { useEffect } from "react";

const SUFFIX = "Prefect Server";
const SEPARATOR = " • ";

/**
 * A hook that sets the browser page title with the provided segments.
 * Automatically appends "Prefect Server" to all titles and joins segments with " • ".
 * Resets the title to "Prefect Server" when the component unmounts.
 *
 * @param segments - Title segments to display. Null and undefined values are filtered out.
 * @returns void
 *
 * @example
 * ```tsx
 * // Single segment
 * usePageTitle("Dashboard");
 * // Sets document.title to "Dashboard • Prefect Server"
 *
 * // Multiple segments
 * usePageTitle("Flow", "MyFlow");
 * // Sets document.title to "Flow • MyFlow • Prefect Server"
 *
 * // With conditional values
 * usePageTitle(flow?.name ? `Flow: ${flow.name}` : "Flow");
 * // Sets document.title to "Flow • Prefect Server" while loading
 * // Sets document.title to "Flow: MyFlow • Prefect Server" once loaded
 *
 * // Null values are filtered out
 * usePageTitle(null, "Flow");
 * // Sets document.title to "Flow • Prefect Server"
 * ```
 */
export function usePageTitle(...segments: (string | undefined | null)[]): void {
	const filteredSegments = segments.filter(
		(segment): segment is string => segment !== null && segment !== undefined,
	);
	const title = [...filteredSegments, SUFFIX].join(SEPARATOR);

	useEffect(() => {
		document.title = title;

		return () => {
			document.title = SUFFIX;
		};
	}, [title]);
}
