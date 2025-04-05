import type { WithPosition } from "../types/schemas";

export function sortByPropertyPosition(a: WithPosition, b: WithPosition) {
	return (a.position ?? 0) - (b.position ?? 0);
}
