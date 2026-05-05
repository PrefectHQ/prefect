export { calculateBucketSize } from "./calculate-bucket-size";
export { cn } from "./css";
export { formatDate, formatDateTimeRelative } from "./date";
export {
	intervalToSeconds,
	secondsToApproximateString,
	secondsToString,
} from "./seconds";
export {
	getAllStateColors,
	getStateColor,
	STATE_COLORS,
} from "./state-colors";
export {
	buildSwitchToV1Url,
	buildUiSwitchGithubIssueUrl,
	getRelativeUiLocation,
	getUiPathPrefix,
	getUiSwitchReasonLabel,
	isUiAvailable,
	type LocationLike,
	normalizeBasePath,
	resolveVisibleUiBasePath,
	setPreferredUiVersion,
	stripV2BasePath,
	UI_SWITCH_REASON_OPTIONS,
	type UiSwitchReason,
	type UiVersion,
} from "./ui-version";
export { capitalize, pluralize, titleCase } from "./utils";
