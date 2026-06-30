/**
 * Guards against croniter's low==high whole-cycle quirk, where `0 23/6 * * *`
 * becomes every 6 hours on the server but daily 11:00 PM in cron-parser.
 */
export const divergesFromServerCron = (cron: string): boolean => {
	const fields = cron.trim().split(/\s+/);

	if (fields.length !== 5) {
		return false;
	}

	const divergentStarts = [
		new Set(["59"]),
		new Set(["23"]),
		new Set(["31"]),
		new Set(["12"]),
		new Set(["6", "7"]),
	];

	return fields.some((field, index) =>
		field.split(",").some((token) => {
			const match = token.match(/^(\d+)\/\d+$/);
			return match !== null && divergentStarts[index].has(match[1]);
		}),
	);
};
