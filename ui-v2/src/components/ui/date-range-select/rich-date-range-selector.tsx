import { CalendarIcon } from "@radix-ui/react-icons";

import {
	addDays,
	addSeconds,
	differenceInSeconds,
	endOfDay,
	endOfToday,
	format,
	isAfter,
	isBefore,
	isSameDay,
	isSameYear,
	parseISO,
	startOfDay,
	startOfMinute,
	startOfToday,
	subSeconds,
} from "date-fns";
import {
	secondsInDay,
	secondsInHour,
	secondsInMinute,
	secondsInMonth,
	secondsInWeek,
} from "date-fns/constants";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";

// Types mirrored from legacy Vue `prefect-design/src/types/dateRange.ts`
export type DateRangeSelectSpanValue = { type: "span"; seconds: number };
export type DateRangeSelectRangeValue = {
	type: "range";
	startDate: Date;
	endDate: Date;
};
export type DateRangeSelectPeriod = "Today";
export type DateRangeSelectPeriodValue = {
	type: "period";
	period: DateRangeSelectPeriod;
};
export type DateRangeSelectAroundUnit = "second" | "minute" | "hour" | "day";
export type DateRangeSelectAroundValue = {
	type: "around";
	date: Date;
	quantity: number;
	unit: DateRangeSelectAroundUnit;
};
export type DateRangeSelectValue =
	| DateRangeSelectSpanValue
	| DateRangeSelectRangeValue
	| DateRangeSelectAroundValue
	| DateRangeSelectPeriodValue
	| null
	| undefined;

export type DateRangeSelectMode = "span" | "range" | "around" | null;

export type RichDateRangeSelectorProps = {
	value: DateRangeSelectValue;
	onValueChange: (value: DateRangeSelectValue) => void;
	placeholder?: string;
	maxSpanInSeconds?: number;
	clearable?: boolean;
	disabled?: boolean;
	min?: Date;
	minReason?: string;
	max?: Date;
	maxReason?: string;
	className?: string;
	id?: string;
};

// Utilities mirrored from legacy `utilities.ts` with small adjustments
const PAST_7_DAYS_SECONDS = secondsInDay * 7;
const PAST_30_DAYS_SECONDS = secondsInDay * 30;

function isStartOfDay(date: Date): boolean {
	return startOfDay(date).getTime() === date.getTime();
}
function isEndOfDay(date: Date): boolean {
	return endOfDay(date).getTime() === date.getTime();
}
function isFullDateRange({
	startDate,
	endDate,
}: {
	startDate: Date;
	endDate: Date;
}): boolean {
	return isStartOfDay(startDate) && isEndOfDay(endDate);
}
function isPickerSingleDayRange({
	startDate,
	endDate,
}: {
	startDate: Date;
	endDate: Date;
}): boolean {
	return (
		isFullDateRange({ startDate, endDate }) && isSameDay(startDate, endDate)
	);
}

function getDateSpanLabel({ seconds }: DateRangeSelectSpanValue): string {
	const absSeconds = Math.abs(seconds);
	if (absSeconds === PAST_7_DAYS_SECONDS) return "Past 7 days";
	if (absSeconds === PAST_30_DAYS_SECONDS) return "Past 30 days";

	const duration = {
		months: Math.floor(absSeconds / secondsInMonth),
		weeks: Math.floor((absSeconds % secondsInMonth) / secondsInWeek),
		days: Math.floor((absSeconds % secondsInWeek) / secondsInDay),
		hours: Math.floor((absSeconds % secondsInDay) / secondsInHour),
		minutes: Math.floor((absSeconds % secondsInHour) / secondsInMinute),
		seconds: Math.floor(absSeconds % secondsInMinute),
	};

	const parts: string[] = [];
	(Object.entries(duration) as [keyof typeof duration, number][]).forEach(
		([unit, value]) => {
			if (!value) return;
			const singular = unit.slice(0, -1);
			parts.push(
				value === 1 ? singular : `${value} ${singular}${value > 1 ? "s" : ""}`,
			);
		},
	);
	const direction = seconds < 0 ? "Past" : "Next";
	return `${direction} ${parts.join(" ")}`;
}

function getDateRangeLabel({
	startDate,
	endDate,
}: DateRangeSelectRangeValue): string {
	const dateFormat = "MMM do";
	const dateAndYearFormat = "MMM do, yyyy";
	const timeFormat = "hh:mm a";
	const dateTimeFormat = `${dateFormat} 'at' ${timeFormat}`;
	const dateTimeAndYearFormat = `${dateAndYearFormat} 'at' ${timeFormat}`;

	if (isPickerSingleDayRange({ startDate, endDate })) {
		const startDateFormat = isSameYear(startDate, new Date())
			? dateFormat
			: dateAndYearFormat;
		return format(startDate, startDateFormat);
	}

	if (isFullDateRange({ startDate, endDate })) {
		const startDateFormat = isSameYear(startDate, new Date())
			? dateFormat
			: dateAndYearFormat;
		const endDateFormat = isSameYear(endDate, new Date())
			? dateFormat
			: dateAndYearFormat;
		return `${format(startDate, startDateFormat)} - ${format(endDate, endDateFormat)}`;
	}

	const startDateFormat = isSameYear(startDate, new Date())
		? dateTimeFormat
		: dateTimeAndYearFormat;
	const endDateFormat = isSameYear(endDate, new Date())
		? dateTimeFormat
		: dateTimeAndYearFormat;
	return `${format(startDate, startDateFormat)} - ${format(endDate, endDateFormat)}`;
}

function getDateAroundLabel({
	date,
	quantity,
	unit,
}: DateRangeSelectAroundValue): string {
	const dateFormat = "MMM do, yyyy";
	const timeFormat = "hh:mm a";
	const fmt = isStartOfDay(date)
		? dateFormat
		: `${dateFormat} 'at' ${timeFormat}`;
	const unitLabel = quantity === 1 ? unit : `${unit}s`;
	return `${quantity} ${unitLabel} around ${format(date, fmt)}`;
}

function getPeriodLabel({ period }: DateRangeSelectPeriodValue): string {
	return period;
}

function getDateRangeSelectValueLabel(
	value: DateRangeSelectValue,
): string | null {
	if (!value) return null;
	switch (value.type) {
		case "span":
			return getDateSpanLabel(value);
		case "range":
			return getDateRangeLabel(value);
		case "around":
			return getDateAroundLabel(value);
		case "period":
			return getPeriodLabel(value);
		default:
			return null;
	}
}

// Map DateRangeSelectValue to concrete start/end and a span length for prev/next stepping
type DateRangeWithTimeSpan = {
	startDate: Date;
	endDate: Date;
	timeSpanInSeconds: number;
};
function nowWithoutMilliseconds(): Date {
	const d = new Date();
	d.setMilliseconds(0);
	return d;
}
function getMultiplierForUnit(unit: DateRangeSelectAroundUnit): number {
	switch (unit) {
		case "second":
			return 1;
		case "minute":
			return secondsInMinute;
		case "hour":
			return secondsInHour;
		case "day":
			return secondsInDay;
	}
}
function mapValueToRange(
	source: DateRangeSelectValue,
): DateRangeWithTimeSpan | null {
	if (!source) return null;
	switch (source.type) {
		case "range": {
			const timeSpanInSeconds = differenceInSeconds(
				source.endDate,
				source.startDate,
			);
			return {
				startDate: source.startDate,
				endDate: source.endDate,
				timeSpanInSeconds,
			};
		}
		case "span": {
			const now = nowWithoutMilliseconds();
			const then = addSeconds(now, source.seconds);
			const [startDate, endDate] = [now, then].sort(
				(a, b) => a.getTime() - b.getTime(),
			);
			const timeSpanInSeconds = Math.abs(source.seconds);
			return { startDate, endDate, timeSpanInSeconds };
		}
		case "around": {
			const seconds = Math.abs(
				source.quantity * getMultiplierForUnit(source.unit),
			);
			const startDate = subSeconds(source.date, seconds);
			const endDate = addSeconds(source.date, seconds);
			const timeSpanInSeconds = differenceInSeconds(endDate, startDate);
			return { startDate, endDate, timeSpanInSeconds };
		}
		case "period": {
			// Only Today supported currently
			const startDate = startOfToday();
			const endDate = endOfToday();
			const timeSpanInSeconds = differenceInSeconds(endDate, startDate);
			return { startDate, endDate, timeSpanInSeconds };
		}
		default:
			return null;
	}
}

export function RichDateRangeSelector({
	value,
	onValueChange,
	placeholder = "Select a time span",
	maxSpanInSeconds,
	clearable,
	disabled,
	min,
	minReason,
	max,
	maxReason,
	className,
	id,
}: RichDateRangeSelectorProps) {
	const [open, setOpen] = React.useState(false);
	const [mode, setMode] = React.useState<DateRangeSelectMode>(null);

	const label = React.useMemo(
		() => getDateRangeSelectValueLabel(value) ?? placeholder,
		[value, placeholder],
	);
	const isPlaceholder = label === placeholder;

	function apply(next: DateRangeSelectValue) {
		onValueChange(next);
		setOpen(false);
		setMode(null);
	}

	function clear() {
		onValueChange(null);
	}

	const getIntervalInSeconds = React.useCallback((): number => {
		const range = mapValueToRange(value);
		return range?.timeSpanInSeconds ?? 0;
	}, [value]);

	const getNewRange = React.useCallback(
		(seconds: number): { startDate: Date; endDate: Date } | null => {
			const range = mapValueToRange(value);
			if (!range) return null;
			const { startDate: curStart, endDate: curEnd } = range;
			if (isFullDateRange({ startDate: curStart, endDate: curEnd })) {
				const differenceInDays = Math.ceil(Math.abs(seconds) / secondsInDay);
				const daysToAdd = seconds < 0 ? -differenceInDays : differenceInDays;
				return {
					startDate: addDays(curStart, daysToAdd),
					endDate: addDays(curEnd, daysToAdd),
				};
			}
			return {
				startDate: addSeconds(curStart, seconds),
				endDate: addSeconds(curEnd, seconds),
			};
		},
		[value],
	);

	const previousDisabled = React.useMemo(() => {
		const seconds = getIntervalInSeconds();
		const next = getNewRange(seconds * -1);
		if (!next || !seconds || disabled) return true;
		if (!min) return false;
		return isBefore(next.startDate, min);
	}, [disabled, min, getIntervalInSeconds, getNewRange]);

	const nextDisabled = React.useMemo(() => {
		const seconds = getIntervalInSeconds();
		const next = getNewRange(seconds);
		if (!next || !seconds || disabled) return true;
		if (!max) return false;
		return isAfter(next.endDate, max);
	}, [disabled, max, getIntervalInSeconds, getNewRange]);

	function previous() {
		const seconds = getIntervalInSeconds();
		const next = getNewRange(seconds * -1);
		if (next)
			apply({
				type: "range",
				startDate: next.startDate,
				endDate: next.endDate,
			});
	}
	function nextStep() {
		const seconds = getIntervalInSeconds();
		const next = getNewRange(seconds);
		if (next)
			apply({
				type: "range",
				startDate: next.startDate,
				endDate: next.endDate,
			});
	}

	return (
		<div className={cn("flex items-center", className)}>
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						variant="outline"
						size="icon"
						className="-ml-px"
						onClick={previous}
						disabled={previousDisabled}
						aria-label="Previous range"
					>
						<Icon id="ChevronLeft" className="size-4" />
					</Button>
				</TooltipTrigger>
				{minReason && previousDisabled ? (
					<TooltipContent>{minReason}</TooltipContent>
				) : null}
			</Tooltip>

			<Popover
				open={open}
				onOpenChange={(o) => {
					if (!o) setMode(null);
					setOpen(o);
				}}
			>
				<PopoverTrigger asChild>
					<Button
						id={id}
						variant="outline"
						className={cn(
							"rounded-none border-x-0 min-w-64 justify-start text-left font-normal",
							isPlaceholder && "text-muted-foreground",
						)}
						disabled={disabled}
					>
						<CalendarIcon className="mr-2 h-4 w-4 shrink-0" />
						<span className="truncate">{label}</span>
						<Icon id="ChevronDown" className="ml-auto size-4 shrink-0" />
					</Button>
				</PopoverTrigger>
				<PopoverContent
					className="w-auto p-0"
					align="start"
					onOpenAutoFocus={(e) => e.preventDefault()}
					onMouseDown={(e) => e.stopPropagation()}
				>
					<div className="w-[22rem] max-w-[90vw]">
						{mode === null && (
							<OptionsView onApply={apply} onSetMode={setMode} />
						)}
						{mode === "span" && (
							<RelativeView
								maxSpanInSeconds={maxSpanInSeconds}
								min={min}
								max={max}
								onApply={apply}
							/>
						)}
						{mode === "around" && <AroundView onApply={apply} />}
						{mode === "range" && <RangeView onApply={apply} />}
					</div>
				</PopoverContent>
			</Popover>

			{value && clearable && !disabled ? (
				<Button
					variant="outline"
					size="icon"
					className="rounded-none -ml-px"
					onClick={clear}
					aria-label="Clear date range"
				>
					<Icon id="X" className="size-4" />
				</Button>
			) : null}

			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						variant="outline"
						size="icon"
						className="-ml-px"
						onClick={nextStep}
						disabled={nextDisabled}
						aria-label="Next range"
					>
						<Icon id="ChevronRight" className="size-4" />
					</Button>
				</TooltipTrigger>
				{maxReason && nextDisabled ? (
					<TooltipContent>{maxReason}</TooltipContent>
				) : null}
			</Tooltip>
		</div>
	);
}

// ----- Options (initial) -----
function OptionsView({
	onApply,
	onSetMode,
}: {
	onApply: (value: DateRangeSelectValue) => void;
	onSetMode: (mode: DateRangeSelectMode) => void;
}) {
	const items: { label: string; onClick: () => void }[] = [
		{
			label: "Past hour",
			onClick: () => onApply({ type: "span", seconds: secondsInHour * -1 }),
		},
		{
			label: "Past day",
			onClick: () => onApply({ type: "span", seconds: secondsInDay * -1 }),
		},
		{
			label: "Past 7 days",
			onClick: () =>
				onApply({ type: "span", seconds: PAST_7_DAYS_SECONDS * -1 }),
		},
		{
			label: "Past 30 days",
			onClick: () =>
				onApply({ type: "span", seconds: PAST_30_DAYS_SECONDS * -1 }),
		},
		{
			label: "Today",
			onClick: () => onApply({ type: "period", period: "Today" }),
		},
		{ label: "Relative time", onClick: () => onSetMode("span") },
		{ label: "Around a time", onClick: () => onSetMode("around") },
		{ label: "Date range", onClick: () => onSetMode("range") },
	];
	return (
		<div className="p-1">
			{items.map((it, i) => (
				<Button
					key={it.label}
					variant="ghost"
					className={cn(
						"w-full justify-between font-normal",
						i === 3 && "border-b rounded-none border-border",
					)}
					onClick={it.onClick}
				>
					<span>{it.label}</span>
				</Button>
			))}
		</div>
	);
}

// ----- Relative (span) -----
function RelativeView({
	maxSpanInSeconds,
	min,
	max,
	onApply,
}: {
	maxSpanInSeconds?: number;
	min?: Date;
	max?: Date;
	onApply: (value: DateRangeSelectValue) => void;
}) {
	type Option = {
		label: string;
		unit: string;
		quantity: number;
		value: number;
	};
	const [search, setSearch] = React.useState("");
	const plural = React.useCallback((unit: string, qty: number) => {
		return qty === 1 ? unit : `${unit}s`;
	}, []);
	const options = React.useMemo<Option[]>(() => {
		const [quantitySearch = ""] = search.match(/\d+/) ?? [];
		const [unitSearch = ""] = search.match(/[a-zA-Z]+/) ?? [];
		const [directionSearch = ""] = search.match(/[+-]+/) ?? [];
		const parsed = Number.parseInt(quantitySearch);
		const quantity = Number.isNaN(parsed) ? 1 : parsed;

		const spans: Option[] = [
			{
				label: `Past ${quantity} ${plural("minute", quantity)}`,
				unit: "minute",
				quantity,
				value: quantity * secondsInMinute * -1,
			},
			{
				label: `Past ${quantity} ${plural("hour", quantity)}`,
				unit: "hour",
				quantity,
				value: quantity * secondsInHour * -1,
			},
			{
				label: `Past ${quantity} ${plural("day", quantity)}`,
				unit: "day",
				quantity,
				value: quantity * secondsInDay * -1,
			},
			{
				label: `Past ${quantity} ${plural("week", quantity)}`,
				unit: "week",
				quantity,
				value: quantity * secondsInWeek * -1,
			},
			{
				label: `Next ${quantity} ${plural("minute", quantity)}`,
				unit: "minute",
				quantity,
				value: quantity * secondsInMinute,
			},
			{
				label: `Next ${quantity} ${plural("hour", quantity)}`,
				unit: "hour",
				quantity,
				value: quantity * secondsInHour,
			},
			{
				label: `Next ${quantity} ${plural("day", quantity)}`,
				unit: "day",
				quantity,
				value: quantity * secondsInDay,
			},
			{
				label: `Next ${quantity} ${plural("week", quantity)}`,
				unit: "week",
				quantity,
				value: quantity * secondsInWeek,
			},
		];

		const now = new Date();
		const limit = maxSpanInSeconds ?? secondsInMonth * 2;

		return spans.filter((opt) => {
			const time = addSeconds(now, opt.value);
			if (min && isBefore(time, min)) return false;
			if (max && isAfter(time, max)) return false;
			const withinSpan = Math.abs(opt.value) < limit;
			const unitMatches = plural(opt.unit, quantity).includes(unitSearch);
			const directionMatches = (opt.value > 0 ? "+" : "-").includes(
				directionSearch,
			);
			return withinSpan && unitMatches && directionMatches;
		});
	}, [search, maxSpanInSeconds, min, max, plural]);

	return (
		<div>
			<div className="p-2">
				<Input
					placeholder="Relative time (15m, 1h, 1d, 1w)"
					value={search}
					onChange={(e) => setSearch(e.target.value)}
					autoFocus
				/>
			</div>
			<div className="max-h-64 overflow-auto">
				{options.map((opt) => (
					<Button
						key={opt.label}
						variant="ghost"
						className="w-full justify-between font-normal"
						onClick={() => onApply({ type: "span", seconds: opt.value })}
					>
						<span>{opt.label}</span>
						<span className="text-muted-foreground font-mono">
							{(opt.value > 0 ? "+" : "-") +
								`${opt.quantity}${opt.unit.slice(0, 1)}`}
						</span>
					</Button>
				))}
			</div>
		</div>
	);
}

// ----- Around a time -----
function AroundView({
	onApply,
}: {
	onApply: (value: DateRangeSelectValue) => void;
}) {
	const [dateIso, setDateIso] = React.useState<string | undefined>(undefined);
	const [quantity, setQuantity] = React.useState<number>(15);
	const [unit, setUnit] = React.useState<DateRangeSelectAroundUnit>("second");

	function commit() {
		if (!dateIso || !quantity) return onApply(null);
		onApply({ type: "around", date: parseISO(dateIso), quantity, unit });
	}

	return (
		<div className="p-2 space-y-3">
			<DateTimePicker value={dateIso} onValueChange={setDateIso} />
			<div className="grid grid-cols-[1fr_8rem] gap-2 max-w-[322px]">
				<div className="flex">
					<span className="inline-flex items-center px-3 border border-r-0 border-input rounded-l-md text-sm font-mono">
						±
					</span>
					<Input
						type="number"
						min={1}
						value={quantity}
						onChange={(e) => setQuantity(Number(e.target.value))}
						className="rounded-l-none"
					/>
				</div>
				<Select
					value={unit}
					onValueChange={(v) => setUnit(v as DateRangeSelectAroundUnit)}
				>
					<SelectTrigger>
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						<SelectItem value="second">Seconds</SelectItem>
						<SelectItem value="minute">Minutes</SelectItem>
						<SelectItem value="hour">Hours</SelectItem>
						<SelectItem value="day">Days</SelectItem>
					</SelectContent>
				</Select>
			</div>
			<div className="flex gap-2 justify-end">
				<Button variant="ghost" onClick={() => onApply(null)}>
					Cancel
				</Button>
				<Button onClick={commit}>Apply</Button>
			</div>
		</div>
	);
}

// ----- Range (date range calendar) -----
function RangeView({
	onApply,
}: {
	onApply: (value: DateRangeSelectValue) => void;
}) {
	const [range, setRange] = React.useState<{ from?: Date; to?: Date }>({});

	const selectedRange: DateRange | undefined = React.useMemo(() => {
		return range.from ? { from: range.from, to: range.to } : undefined;
	}, [range.from, range.to]);

	// Helpers to maintain date and time parts separately
	function setDatePart(original: Date | undefined, dateStr: string): Date {
		const [y, m, d] = dateStr.split("-").map((n) => Number(n));
		const result = new Date(original ?? new Date());
		result.setFullYear(y);
		result.setMonth(m - 1);
		result.setDate(d);
		return result;
	}
	function setTimePart(original: Date | undefined, timeStr: string): Date {
		const [hh, mm] = timeStr.split(":").map((n) => Number(n));
		const result = new Date(original ?? new Date());
		result.setHours(hh);
		result.setMinutes(mm);
		result.setSeconds(0);
		result.setMilliseconds(0);
		return result;
	}
	function toDateInputValue(d?: Date): string {
		if (!d) return "";
		const yyyy = d.getFullYear();
		const mm = String(d.getMonth() + 1).padStart(2, "0");
		const dd = String(d.getDate()).padStart(2, "0");
		return `${yyyy}-${mm}-${dd}`;
	}
	function toTimeInputValue(d?: Date): string {
		if (!d) return "";
		const hh = String(d.getHours()).padStart(2, "0");
		const mm = String(d.getMinutes()).padStart(2, "0");
		return `${hh}:${mm}`;
	}

	function handleCalendarSelect(next?: DateRange) {
		if (!next) {
			setRange({});
			return;
		}
		setRange((prev) => {
			const prevFrom = prev.from;
			const prevTo = prev.to;
			const from = next.from
				? (() => {
						const existing = prevFrom ?? undefined;
						// If time was set previously, keep it, otherwise default startOfDay
						if (!existing) return startOfDay(next.from);
						const fromSel = next.from;
						return new Date(
							fromSel.getFullYear(),
							fromSel.getMonth(),
							fromSel.getDate(),
							existing.getHours(),
							existing.getMinutes(),
							0,
							0,
						);
					})()
				: undefined;
			const to = next.to
				? (() => {
						const existing = prevTo ?? undefined;
						if (!existing) return endOfDay(next.to);
						const toSel = next.to;
						return new Date(
							toSel.getFullYear(),
							toSel.getMonth(),
							toSel.getDate(),
							existing.getHours(),
							existing.getMinutes(),
							0,
							0,
						);
					})()
				: undefined;
			return { from, to };
		});
	}

	function commit() {
		if (range.from && range.to) {
			onApply({ type: "range", startDate: range.from, endDate: range.to });
		} else {
			onApply(null);
		}
	}

	return (
		<div className="p-2 space-y-3">
			<Calendar
				mode="range"
				selected={selectedRange}
				onSelect={handleCalendarSelect}
				initialFocus
				classNames={{ root: "mx-auto" }}
			/>
			<div className="grid grid-cols-1 gap-3">
				{/* From section */}
				<div className="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
					<div className="col-span-4 flex items-center justify-between text-sm text-muted-foreground">
						<span>From</span>
						<Button
							variant="ghost"
							size="sm"
							onClick={() =>
								setRange((prev) => ({
									...prev,
									from: startOfMinute(new Date()),
								}))
							}
						>
							Now
						</Button>
					</div>
					<Input
						type="date"
						value={toDateInputValue(range.from)}
						onChange={(e) =>
							setRange((prev) => ({
								...prev,
								from: setDatePart(
									prev.from ?? startOfDay(new Date()),
									e.target.value || toDateInputValue(prev.from),
								),
							}))
						}
					/>
					<Input
						type="time"
						step={60}
						value={toTimeInputValue(range.from)}
						onChange={(e) =>
							setRange((prev) => ({
								...prev,
								from: setTimePart(
									prev.from ?? startOfDay(new Date()),
									e.target.value || toTimeInputValue(prev.from),
								),
							}))
						}
					/>
				</div>

				{/* To section */}
				<div className="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
					<div className="col-span-4 flex items-center justify-between text-sm text-muted-foreground">
						<span>To</span>
						<Button
							variant="ghost"
							size="sm"
							onClick={() =>
								setRange((prev) => ({ ...prev, to: startOfMinute(new Date()) }))
							}
						>
							Now
						</Button>
					</div>
					<Input
						type="date"
						value={toDateInputValue(range.to)}
						onChange={(e) =>
							setRange((prev) => ({
								...prev,
								to: setDatePart(
									prev.to ?? endOfDay(new Date()),
									e.target.value || toDateInputValue(prev.to),
								),
							}))
						}
					/>
					<Input
						type="time"
						step={60}
						value={toTimeInputValue(range.to)}
						onChange={(e) =>
							setRange((prev) => ({
								...prev,
								to: setTimePart(
									prev.to ?? endOfDay(new Date()),
									e.target.value || toTimeInputValue(prev.to),
								),
							}))
						}
					/>
				</div>
			</div>
			<div className="flex gap-2 justify-end">
				<Button variant="ghost" onClick={() => onApply(null)}>
					Cancel
				</Button>
				<Button onClick={commit} disabled={!range.from || !range.to}>
					Apply
				</Button>
			</div>
		</div>
	);
}
