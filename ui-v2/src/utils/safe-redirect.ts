const PLACEHOLDER_ORIGIN = "http://redirect-check.invalid";

/**
 * Returns true when `value` is a path on the current origin.
 *
 * The URL parse is needed because browsers strip tabs and newlines and
 * treat `\` as `/`, so a value such as `/\evil.example` leaves the origin.
 * A value that does not parse is rejected rather than thrown, so the login
 * route's search schema can drop it.
 */
export function isSafeRedirectPath(value: string): boolean {
	if (!value.startsWith("/")) {
		return false;
	}
	try {
		return new URL(value, PLACEHOLDER_ORIGIN).origin === PLACEHOLDER_ORIGIN;
	} catch {
		return false;
	}
}
