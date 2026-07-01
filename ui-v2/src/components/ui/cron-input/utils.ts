/**
 * Guards against croniter whole-cycle mismatches: low==high ranges, max-start
 * slash steps, and 6-field seconds-position parsing.
 */
const FIELD_MAX = [59, 23, 31, 12, 6];

const MONTH_ALIASES: Record<string, number> = {
	JAN: 1,
	FEB: 2,
	MAR: 3,
	APR: 4,
	MAY: 5,
	JUN: 6,
	JUL: 7,
	AUG: 8,
	SEP: 9,
	OCT: 10,
	NOV: 11,
	DEC: 12,
};

const DOW_ALIASES: Record<string, number> = {
	SUN: 0,
	MON: 1,
	TUE: 2,
	WED: 3,
	THU: 4,
	FRI: 5,
	SAT: 6,
};

const resolveValue = (raw: string, index: number): number | null => {
	const upper = raw.toUpperCase();

	if (index === 3 && upper in MONTH_ALIASES) {
		return MONTH_ALIASES[upper];
	}

	if (index === 4 && upper in DOW_ALIASES) {
		return DOW_ALIASES[upper];
	}

	if (/^\d+$/.test(raw)) {
		return Number(raw);
	}

	return null;
};

const divergentBareStart = (value: number, index: number) =>
	index === 4 ? value === 6 || value === 7 : value === FIELD_MAX[index];

const tokenDiverges = (token: string, index: number): boolean => {
	const bare = token.match(/^([A-Za-z0-9]+)\/\d+$/);
	if (bare) {
		const value = resolveValue(bare[1], index);
		return value !== null && divergentBareStart(value, index);
	}

	const range = token.match(/^([A-Za-z0-9]+)-([A-Za-z0-9]+)(?:\/\d+)?$/);
	if (range) {
		const low = resolveValue(range[1], index);
		const high = resolveValue(range[2], index);
		return low !== null && high !== null && low === high;
	}

	return false;
};

export const divergesFromServerCron = (cron: string): boolean => {
	const fields = cron.trim().split(/\s+/);

	if (fields.length === 6) {
		return true;
	}

	if (fields.length !== 5) {
		return false;
	}

	return fields.some((field, index) =>
		field.split(",").some((token) => tokenDiverges(token, index)),
	);
};
