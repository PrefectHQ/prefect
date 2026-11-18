const PLACEHOLDER_ORIGIN = "http://redirect-check.invalid";

/**
 * Returns true when `value` is a path on the current origin.
 *
 * The URL parse is needed because browsers strip tabs and newlines and
 * treat `\` as `/`, so a value such as `/\evil.example` leaves the origin.
 */
export function isSafeRedirectPath(value: string): boolean {
	if (!value.startsWith("/")) {
		return false;
	}
	return new URL(value, PLACEHOLDER_ORIGIN).origin === PLACEHOLDER_ORIGIN;
}
