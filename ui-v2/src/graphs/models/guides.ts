export type FormatDate = (date: Date) => string;

export type FormatDateFns = {
	timeBySeconds: FormatDate;
	timeByMinutesWithDates: FormatDate;
	date: FormatDate;
};
