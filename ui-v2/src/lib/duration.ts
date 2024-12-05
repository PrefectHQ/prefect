import {
	formatDuration,
	intervalToDuration,
	type Duration,
	formatDistanceStrict,
} from "date-fns";

export function secondsToString(input: number): string {
	const duration: Duration = intervalToDuration({
		start: 0,
		end: input * 1000, // convert seconds to milliseconds
	});

	return formatDuration(duration, {
		zero: false,
		delimiter: " ",
	}).trim();
}

export function secondsToApproximateString(input: number): string {
	return formatDistanceStrict(0, input * 1000, {
		addSuffix: false,
	});
}
