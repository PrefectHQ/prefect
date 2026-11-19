import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { type FieldPathValue, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
	const id = useId();
	return (
		<div className="space-y-2">
			{!hideLabel && <Label htmlFor={id}>{label}</Label>}
			<Select value={value} onValueChange={onChange}>
				<SelectTrigger
					id={id}
					type="button"
					aria-label={hideLabel ? label : undefined}
				>
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					{options.map((option) => (
						<SelectItem key={option.value} value={option.value}>
							{option.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
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
	const { register, getValues, setValue, watch } = useForm<RuleForm>({
		values: value,
		resolver: zodResolver(ruleFormSchema),
	});
	const current = watch();
	const monthly = getMonthlyOptions(current);
	const annualLabel = getAnnualLabel(current);
	const [error, setError] = useState("");
	const id = useId();
	const emit = () => {
		try {
			onChange(serializeRule(getValues(), timezone));
			setError("");
		} catch {
			setError(
				"Enter valid recurrence settings. Select at least one weekday and use positive intervals and occurrence counts.",
			);
		}
	};
	const update = <K extends keyof RuleForm>(
		key: K,
		next: FieldPathValue<RuleForm, K>,
	) => {
		setValue(key, next);
		emit();
	};
	const input = (
		key: "start" | "time" | "interval" | "day" | "month" | "count" | "until",
		label: string,
		type: string,
		min?: number,
		max?: number,
	) => (
		<div className="space-y-2">
			<Label htmlFor={`${id}-${key}`}>{label}</Label>
			<Input
				id={`${id}-${key}`}
				type={type}
				min={min}
				max={max}
				{...register(key, {
					valueAsNumber: type === "number",
					onChange: () => {
						if (
							key === "start" &&
							current.frequency === "YEARLY" &&
							annualLabel
						) {
							const date = new Date(`${getValues("start")}T00:00:00Z`);
							if (Number.isFinite(date.getTime())) {
								setValue("month", date.getUTCMonth() + 1);
								setValue("day", date.getUTCDate());
							}
						}
						emit();
					},
				})}
			/>
		</div>
	);
	return (
		<div className="space-y-4">
			<div className="flex flex-wrap items-center gap-3">
				<Label htmlFor={`${id}-interval`}>Repeat every</Label>
				<Input
					id={`${id}-interval`}
					type="number"
					min={1}
					className="w-20"
					{...register("interval", { valueAsNumber: true, onChange: emit })}
				/>
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
						if (frequency) update("frequency", frequency);
					}}
				/>
			</div>
			{current.frequency === "WEEKLY" && (
				<div className="space-y-2">
					<Label>Repeat on</Label>
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
				</div>
			)}
			{current.frequency === "MONTHLY" && (
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
			<div className="space-y-3">
				<Label id={`${id}-ends`}>Ends</Label>
				<RadioGroup
					aria-labelledby={`${id}-ends`}
					value={current.end}
					onValueChange={(next) => {
						if (next === "never" || next === "until" || next === "count")
							update("end", next);
					}}
				>
					<div className="flex items-center gap-3">
						<RadioGroupItem type="button" id={`${id}-never`} value="never" />
						<Label htmlFor={`${id}-never`}>Never</Label>
					</div>
					<div className="flex items-center gap-3">
						<RadioGroupItem type="button" id={`${id}-on`} value="until" />
						<Label htmlFor={`${id}-on`}>On</Label>
						<Input
							className="w-auto"
							type="date"
							aria-label="End date"
							disabled={current.end !== "until"}
							{...register("until", { onChange: emit })}
						/>
					</div>
					<div className="flex items-center gap-3">
						<RadioGroupItem type="button" id={`${id}-after`} value="count" />
						<Label htmlFor={`${id}-after`}>After</Label>
						<Input
							className="w-20"
							type="number"
							min={1}
							aria-label="Occurrences"
							disabled={current.end !== "count"}
							{...register("count", { valueAsNumber: true, onChange: emit })}
						/>
						<span className="text-sm">occurrences</span>
					</div>
				</RadioGroup>
			</div>
			{error && (
				<p role="alert" className="text-sm text-destructive">
					{error}
				</p>
			)}
		</div>
	);
}
