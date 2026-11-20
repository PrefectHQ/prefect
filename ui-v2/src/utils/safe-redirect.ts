const PLACEHOLDER_ORIGINS = [
	"http://redirect-check-a.invalid",
	"http://redirect-check-b.invalid",
];

/**
 * Returns true when `value` is a path on the current origin.
 *
 * The URL parse is needed because browsers strip tabs and newlines and
 * treat `\` as `/`, so a value such as `/\evil.example` leaves the origin.
 * The value is resolved against two placeholder origins: a path keeps each
 * base origin, but a network-path reference such as `//host` resolves to
 * its own host, so it cannot match both. A value that does not parse is
 * rejected rather than thrown, so the login route's search schema can
 * drop it.
 */
export function isSafeRedirectPath(value: string): boolean {
	if (!value.startsWith("/")) {
		return false;
	}
	try {
		return PLACEHOLDER_ORIGINS.every(
			(origin) => new URL(value, origin).origin === origin,
		);
	} catch {
		return false;
	}
}
