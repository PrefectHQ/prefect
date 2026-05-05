import {
	trackUiSwitchFeedbackSubmitted,
	trackUiVersionSwitched,
} from "@/analytics";
import type { UiSettings } from "@/api/ui-settings";
import {
	buildSwitchToV1Url,
	buildUiSwitchGithubIssueUrl,
	getRelativeUiLocation,
	type LocationLike,
	setPreferredUiVersion,
	type UiSwitchReason,
} from "@/utils/ui-version";

export type UiSwitchFeedbackInput = {
	reason: UiSwitchReason;
	notes?: string;
	openGithubIssue?: boolean;
};

type OpenWindow = (
	url?: string | URL,
	target?: string,
	features?: string,
) => Window | null;

export function switchToV1Ui(args: {
	uiSettings: Pick<UiSettings, "v1BaseUrl" | "v2BaseUrl">;
	analyticsEnabled: boolean;
	location?: LocationLike;
	feedback?: UiSwitchFeedbackInput;
	openWindow?: OpenWindow;
	redirectTo?: (url: string) => void;
}): string | undefined {
	const v1BaseUrl = args.uiSettings.v1BaseUrl;
	if (!v1BaseUrl) {
		return;
	}

	const location = args.location ?? window.location;
	const v2BaseUrl = args.uiSettings.v2BaseUrl ?? null;
	const currentLocation = getRelativeUiLocation(location, v2BaseUrl);
	const targetUrl = buildSwitchToV1Url({
		v1BaseUrl,
		v2BaseUrl,
		location,
	});

	setPreferredUiVersion({
		targetBasePath: v1BaseUrl,
		currentBasePath: v2BaseUrl,
		version: "v1",
		location,
	});
	trackUiVersionSwitched(args.analyticsEnabled, {
		from_ui: "v2",
		to_ui: "v1",
		current_path: currentLocation.pathname,
	});

	if (args.feedback) {
		trackUiSwitchFeedbackSubmitted(args.analyticsEnabled, {
			reason: args.feedback.reason,
			has_notes: Boolean(args.feedback.notes?.trim()),
			from_ui: "v2",
			to_ui: "v1",
			current_path: currentLocation.pathname,
		});

		if (args.feedback.openGithubIssue) {
			const issueUrl = buildUiSwitchGithubIssueUrl({
				reason: args.feedback.reason,
				notes: args.feedback.notes,
				currentPath: currentLocation.pathname,
			});
			(args.openWindow ?? window.open)(
				issueUrl,
				"_blank",
				"noopener,noreferrer",
			);
		}
	}

	(args.redirectTo ?? ((url: string) => window.location.assign(url)))(
		targetUrl,
	);
	return targetUrl;
}
