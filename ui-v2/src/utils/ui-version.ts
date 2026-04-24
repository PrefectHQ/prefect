export type UiVersion = "v1" | "v2";

export type UiSwitchReason =
	| "missing_feature"
	| "bug_incorrect_behavior"
	| "performance_stability"
	| "navigation_usability"
	| "prefer_v1_familiarity"
	| "other";

export type LocationLike = {
	pathname: string;
	search?: string;
	hash?: string;
};

export const UI_VERSION_COOKIE_NAME = "prefect_ui_version";

export const UI_SWITCH_REASON_OPTIONS: ReadonlyArray<{
	value: UiSwitchReason;
	label: string;
	description: string;
}> = [
	{
		value: "missing_feature",
		label: "Missing feature",
		description: "A workflow or page you need is not available in V2 yet.",
	},
	{
		value: "bug_incorrect_behavior",
		label: "Bug or incorrect behavior",
		description: "Something works differently than expected or breaks a task.",
	},
	{
		value: "performance_stability",
		label: "Performance or stability",
		description:
			"The page feels slow, unstable, or unreliable in this browser.",
	},
	{
		value: "navigation_usability",
		label: "Navigation or usability",
		description: "The flow of the UI is harder to use or harder to navigate.",
	},
	{
		value: "prefer_v1_familiarity",
		label: "Prefer V1 or familiarity",
		description:
			"You prefer the existing layout or established workflows in V1.",
	},
	{
		value: "other",
		label: "Other",
		description: "Your reason does not fit the categories above.",
	},
] as const;

const ONE_YEAR_IN_SECONDS = 60 * 60 * 24 * 365;

export function normalizeBasePath(basePath?: string | null): string {
	if (!basePath || basePath === "/") {
		return "/";
	}

	const trimmedBasePath = basePath.replace(/^\/+|\/+$/g, "");
	return trimmedBasePath ? `/${trimmedBasePath}` : "/";
}

export function stripV2BasePath(basePath?: string | null): string {
	const normalizedBasePath = normalizeBasePath(basePath);
	if (normalizedBasePath === "/v2") {
		return "/";
	}
	if (normalizedBasePath.endsWith("/v2")) {
		return normalizedBasePath.slice(0, -3) || "/";
	}
	return normalizedBasePath;
}

export function isUiAvailable(
	availableUis: ReadonlyArray<UiVersion> | undefined,
	version: UiVersion,
): boolean {
	return availableUis?.includes(version) ?? false;
}

export function getUiPathPrefix(
	pathname: string,
	currentBasePath?: string | null,
): string {
	const normalizedCurrentBasePath = normalizeBasePath(currentBasePath);
	if (normalizedCurrentBasePath === "/") {
		return "";
	}

	const normalizedPathname = normalizeBasePath(pathname);
	let lastMatchingIndex = -1;
	let searchIndex = 0;

	while (searchIndex < normalizedPathname.length) {
		const index = normalizedPathname.indexOf(
			normalizedCurrentBasePath,
			searchIndex,
		);
		if (index === -1) {
			break;
		}

		const nextCharacter =
			normalizedPathname[index + normalizedCurrentBasePath.length];
		if (nextCharacter === undefined || nextCharacter === "/") {
			lastMatchingIndex = index;
		}

		searchIndex = index + 1;
	}

	return lastMatchingIndex === -1
		? ""
		: normalizedPathname.slice(0, lastMatchingIndex);
}

export function resolveVisibleUiBasePath(args: {
	configuredBasePath?: string | null;
	location: LocationLike;
	currentBasePath?: string | null;
}): string {
	const normalizedConfiguredBasePath = normalizeBasePath(args.configuredBasePath);
	const prefix = getUiPathPrefix(
		args.location.pathname || "/",
		args.currentBasePath ?? args.configuredBasePath,
	);

	if (!prefix) {
		return normalizedConfiguredBasePath;
	}

	if (normalizedConfiguredBasePath === "/") {
		return prefix;
	}

	return `${prefix}${normalizedConfiguredBasePath}`;
}

export function getRelativeUiLocation(
	location: LocationLike,
	basePath?: string | null,
	currentBasePath?: string | null,
): Required<LocationLike> {
	const normalizedBasePath = resolveVisibleUiBasePath({
		configuredBasePath: basePath,
		location,
		currentBasePath,
	});
	let pathname = location.pathname || "/";

	if (normalizedBasePath !== "/" && pathname.startsWith(normalizedBasePath)) {
		pathname = pathname.slice(normalizedBasePath.length) || "/";
	}

	return {
		pathname: pathname || "/",
		search: location.search ?? "",
		hash: location.hash ?? "",
	};
}

function buildUiUrl(
	basePath: string,
	location: LocationLike,
): string {
	const normalizedBasePath = normalizeBasePath(basePath);
	const normalizedPathname = location.pathname.startsWith("/")
		? location.pathname
		: `/${location.pathname}`;
	const search = location.search ?? "";
	const hash = location.hash ?? "";

	if (normalizedBasePath === "/") {
		return `${normalizedPathname}${search}${hash}`;
	}

	if (normalizedPathname === "/") {
		return `${normalizedBasePath}${search}${hash}`;
	}

	return `${normalizedBasePath}${normalizedPathname}${search}${hash}`;
}

export function buildSwitchToV1Url(args: {
	v1BaseUrl: string | null;
	v2BaseUrl: string | null;
	location: LocationLike;
}): string {
	const relativeLocation = getRelativeUiLocation(
		args.location,
		args.v2BaseUrl,
		args.v2BaseUrl,
	);
	const v1BasePath = resolveVisibleUiBasePath({
		configuredBasePath: args.v1BaseUrl,
		location: args.location,
		currentBasePath: args.v2BaseUrl,
	});
	return buildUiUrl(v1BasePath, relativeLocation);
}

export function setPreferredUiVersion(args: {
	targetBasePath: string | null | undefined;
	currentBasePath?: string | null;
	version: UiVersion;
	location?: LocationLike;
}): void {
	const location = args.location ?? window.location;
	const cookiePath = resolveVisibleUiBasePath({
		configuredBasePath: args.targetBasePath,
		location,
		currentBasePath: args.currentBasePath,
	});
	document.cookie = `${UI_VERSION_COOKIE_NAME}=${args.version}; Path=${cookiePath}; Max-Age=${ONE_YEAR_IN_SECONDS}; SameSite=Lax`;
}

export function getUiSwitchReasonLabel(reason: UiSwitchReason): string {
	return (
		UI_SWITCH_REASON_OPTIONS.find((option) => option.value === reason)?.label ??
		"Other"
	);
}

export function buildUiSwitchGithubIssueUrl(args: {
	reason: UiSwitchReason;
	notes?: string;
	currentPath: string;
}): string {
	const reasonLabel = getUiSwitchReasonLabel(args.reason);
	const notes = args.notes?.trim() || "None provided.";
	const body = [
		"### UI switch feedback",
		"",
		"- From UI: V2",
		"- To UI: V1",
		`- Current path: ${args.currentPath}`,
		`- Reason: ${reasonLabel}`,
		"",
		"### Additional notes",
		notes,
	].join("\n");

	const params = new URLSearchParams({
		title: `V2 feedback: ${reasonLabel}`,
		body,
	});

	return `https://github.com/PrefectHQ/prefect/issues/new?${params.toString()}`;
}
