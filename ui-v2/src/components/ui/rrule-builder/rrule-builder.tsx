import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useRef } from "react";
import { type FieldPathValue, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
	dayNames,
	describeRule,
	frequencies,
	getAnnualLabel,
	getMonthlyOptions,
	parseRule,
	type RuleForm,
	ruleFormSchema,
	serializeRule,
	weekdays,
} from "./utils";

export type RRuleBuilderProps = {
	value: string;
	timezone?: string;
	onChange: (value: string) => void;
};

export function RRuleBuilder({
	value,
	timezone = "UTC",
	onChange,
}: RRuleBuilderProps) {
	const parsed = parseRule(value, timezone);
	return (
		<div className="space-y-4 text-foreground">
			{parsed.supported ? (
				<BuilderFields
					key={timezone}
					value={parsed.value}
					timezone={timezone}
					onChange={onChange}
				/>
			) : (
				<div className="space-y-2">
					<p>{describeRule(value) || "No recurrence rule"}</p>
					<p className="text-sm text-muted-foreground">
						This schedule can only be edited in code.
					</p>
					<p className="text-sm text-muted-foreground">
						<a
							href="https://www.prefect.io/docs/v3/concepts/schedules#rrule"
							target="_blank"
							rel="noopener noreferrer"
							className="underline hover:text-foreground"
						>
							Learn how to define RRule schedules
						</a>
					</p>
					<p className="text-sm text-muted-foreground">{parsed.reason}</p>
					<Collapsible key={value}>
						<CollapsibleTrigger asChild>
							<Button type="button" variant="ghost">
								Show rule
							</Button>
						</CollapsibleTrigger>
						<CollapsibleContent>
							<pre className="whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-sm">
								{value || "No recurrence rule"}
							</pre>
						</CollapsibleContent>
					</Collapsible>
				</div>
			)}
		</div>
	);
}

function Choice({
	label,
	value,
	options,
	onChange,
	hideLabel = false,
}: {
	label: string;
	value: string;
	options: { value: string; label: string }[];
	onChange: (value: string) => void;
	hideLabel?: boolean;
}) {
	return (
		<FormItem>
			{!hideLabel && <FormLabel>{label}</FormLabel>}
			<Select value={value} onValueChange={onChange}>
				<FormControl>
					<SelectTrigger
						type="button"
						aria-label={hideLabel ? label : undefined}
					>
						<SelectValue />
					</SelectTrigger>
				</FormControl>
				<SelectContent>
					{options.map((option) => (
						<SelectItem key={option.value} value={option.value}>
							{option.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
			<FormMessage role="alert" />
		</FormItem>
	);
}

function getStartFields(start: string) {
	const date = new Date(`${start}T00:00:00Z`);
	if (
		!Number.isFinite(date.getTime()) ||
		date.toISOString().slice(0, 10) !== start
	)
		return null;
	const day = date.getUTCDate();
	return {
		day,
		month: date.getUTCMonth() + 1,
		weekday: weekdays[(date.getUTCDay() + 6) % 7],
		position: Math.ceil(day / 7),
		last:
			day + 7 >
			new Date(
				Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0),
			).getUTCDate(),
	};
}

function BuilderFields({
	value,
	timezone,
	onChange,
}: {
	value: RuleForm;
	timezone: string;
	onChange: (rule: string) => void;
}) {
	const form = useForm<RuleForm>({
		values: value,
		resolver: zodResolver(ruleFormSchema),
	});
	const { control, getValues, setValue, watch, trigger } = form;
	const current = watch();
	const monthly = getMonthlyOptions(current);
	const annualLabel = getAnnualLabel(current);
	const id = useId();
	const lastValidStart = useRef(value.start);
	const emit = () => {
		void trigger();
		const values = getValues();
		if (ruleFormSchema.safeParse(values).success)
			onChange(serializeRule(values, timezone));
	};
	const update = <K extends keyof RuleForm>(
		key: K,
		next: FieldPathValue<RuleForm, K>,
	) => {
		setValue(key, next);
		emit();
	};
	const initializeFrequency = (
		frequency: RuleForm["frequency"],
		start: NonNullable<ReturnType<typeof getStartFields>>,
		preferLast = false,
	) => {
		if (frequency === "WEEKLY") setValue("weekdays", [start.weekday]);
		if (frequency === "MONTHLY") {
			setValue("day", start.day);
			setValue("weekday", start.weekday);
			setValue("position", preferLast && start.last ? -1 : start.position);
		}
		if (frequency === "YEARLY") {
			setValue("day", start.day);
			setValue("month", start.month);
		}
	};
	const syncStart = (next: string) => {
		if (getStartFields(current.start)) lastValidStart.current = current.start;
		const previous = getStartFields(lastValidStart.current);
		const start = getStartFields(next);
		if (!start) return;
		lastValidStart.current = next;
		if (!previous) return;
		const derived =
			(current.frequency === "WEEKLY" &&
				current.weekdays.length === 1 &&
				current.weekdays[0] === previous.weekday) ||
			(current.frequency === "YEARLY" &&
				current.day === previous.day &&
				current.month === previous.month) ||
			(current.frequency === "MONTHLY" &&
				((current.monthly === "day" && current.day === previous.day) ||
					(current.monthly === "weekday" &&
						current.weekday === previous.weekday &&
						(current.position === previous.position ||
							(current.position === -1 && previous.last)))));
		if (derived)
			initializeFrequency(current.frequency, start, current.position === -1);
	};
	const input = (
		key: "start" | "time" | "interval" | "day" | "month" | "until",
		label: string,
		type: string,
		min?: number,
		max?: number,
		inline = false,
		hideLabel = false,
		disabled = false,
	) => (
		<FormField
			control={control}
			name={key}
			render={({ field }) => (
				<FormItem
					className={
						inline ? "flex flex-wrap items-center gap-3 space-y-0" : undefined
					}
				>
					{!hideLabel && <FormLabel>{label}</FormLabel>}
					<FormControl>
						<Input
							{...field}
							value={Number.isNaN(field.value) ? "" : field.value}
							aria-label={hideLabel ? label : undefined}
							disabled={disabled}
							className={key === "interval" ? "w-20" : "w-auto"}
							type={type}
							min={min}
							max={max}
							onChange={(event) => {
								field.onChange(
									type === "number"
										? event.target.valueAsNumber
										: event.target.value,
								);
								if (key === "start") syncStart(event.target.value);
								emit();
							}}
						/>
					</FormControl>
					{key === "interval" && (
						<FormField
							control={control}
							name="frequency"
							render={() => (
								<Choice
									label="Recurrence unit"
									hideLabel
									value={current.frequency}
									options={frequencies.map((frequency, index) => ({
										value: frequency,
										label: `${["day", "week", "month", "year"][index]}${current.interval > 1 ? "s" : ""}`,
									}))}
									onChange={(next) => {
										const frequency = frequencies.find((item) => item === next);
										if (frequency) {
											const start =
												getStartFields(getValues("start")) ??
												getStartFields(lastValidStart.current);
											if (start) initializeFrequency(frequency, start);
											update("frequency", frequency);
										}
									}}
								/>
							)}
						/>
					)}
					<FormMessage
						role="alert"
						className={inline ? "basis-full" : undefined}
					/>
				</FormItem>
			)}
		/>
	);
	return (
		<Form {...form}>
			<div className="space-y-4">
				{input("interval", "Repeat every", "number", 1, undefined, true)}
				{current.frequency === "WEEKLY" && (
					<FormField
						control={control}
						name="weekdays"
						render={() => (
							<FormItem>
								<FormLabel>Repeat on</FormLabel>
								<FormControl>
									<ToggleGroup
										type="multiple"
										variant="outline"
										value={current.weekdays}
										onValueChange={(next) =>
											update(
												"weekdays",
												weekdays.filter((day) => next.includes(day)),
											)
										}
										aria-label="Weekdays"
									>
										{weekdays.map((day, index) => (
											<ToggleGroupItem
												type="button"
												key={day}
												value={day}
												aria-label={dayNames[index]}
											>
												{dayNames[index].slice(0, 1)}
											</ToggleGroupItem>
										))}
									</ToggleGroup>
								</FormControl>
								<FormMessage role="alert" />
							</FormItem>
						)}
					/>
				)}
				{current.frequency === "MONTHLY" && (
					<FormField
						control={control}
						name={current.monthly === "day" ? "day" : "position"}
						render={() => (
							<Choice
								label="Monthly recurrence"
								hideLabel
								value={monthly.selected}
								options={monthly.options}
								onChange={(next) => {
									const option = monthly.options.find(
										(option) => option.value === next,
									);
									if (option) {
										setValue("monthly", option.settings.monthly);
										setValue("day", option.settings.day);
										setValue("position", option.settings.position);
										setValue("weekday", option.settings.weekday);
										emit();
									}
								}}
							/>
						)}
					/>
				)}
				{current.frequency === "YEARLY" &&
					(annualLabel ? (
						<p className="text-sm">{annualLabel}</p>
					) : (
						<div className="flex gap-3">
							{input("month", "Month of year", "number", 1, 12)}
							{input("day", "Day of month", "number", 1, 31)}
						</div>
					))}
				<div className="flex flex-wrap gap-3">
					{input("start", "Start date", "date")}
					{input("time", `Time (${timezone})`, "time")}
				</div>
				<FormField
					control={control}
					name="end"
					render={() => (
						<FormItem className="space-y-3">
							<FormLabel id={`${id}-ends`}>Ends</FormLabel>
							<FormControl>
								<RadioGroup
									aria-labelledby={`${id}-ends`}
									value={current.end}
									onValueChange={(next) => {
										if (next === "never" || next === "until")
											update("end", next);
									}}
								>
									<div className="flex items-center gap-3">
										<RadioGroupItem
											type="button"
											id={`${id}-never`}
											value="never"
										/>
										<Label htmlFor={`${id}-never`}>Never</Label>
									</div>
									<div className="flex items-center gap-3">
										<RadioGroupItem
											type="button"
											id={`${id}-on`}
											value="until"
										/>
										<Label htmlFor={`${id}-on`}>On</Label>
										{input(
											"until",
											"End date",
											"date",
											undefined,
											undefined,
											false,
											true,
											current.end !== "until",
										)}
									</div>
								</RadioGroup>
							</FormControl>
							<FormMessage role="alert" />
						</FormItem>
					)}
				/>
			</div>
		</Form>
	);
}
