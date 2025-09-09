export type DateRangeSelectType = "span" | "range" | "period" | "around";

export type DateRangeSelectSpanValue = {
	type: "span";
	seconds: number;
};

export type DateRangeSelectRangeValue = {
	type: "range";
	startDate: Date;
	endDate: Date;
};

export type DateRangeSelectPeriodValue = {
	type: "period";
	period: "Today";
};

export type DateRangeSelectAroundValue = {
	type: "around";
	date: Date;
	quantity: number;
	unit: "second" | "minute" | "hour" | "day";
};

export type DateRangeSelectValue =
	| DateRangeSelectSpanValue
	| DateRangeSelectRangeValue
	| DateRangeSelectAroundValue
	| DateRangeSelectPeriodValue
	| null
	| undefined;

export type DashboardFilter = {
	range: NonNullable<DateRangeSelectValue>;
	tags: string[];
	hideSubflows?: boolean;
};
