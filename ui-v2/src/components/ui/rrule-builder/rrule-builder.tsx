import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { type FieldPathValue, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
	describeRule,
	frequencies,
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

const dayNames = [
	"Monday",
	"Tuesday",
	"Wednesday",
	"Thursday",
	"Friday",
	"Saturday",
	"Sunday",
];

export function RRuleBuilder({
	value,
	timezone = "UTC",
	onChange,
}: RRuleBuilderProps) {
	const [raw, setRaw] = useState(false);
	const parsed = parseRule(value, timezone);
	const id = useId();
	return (
		<div className="space-y-4 text-foreground">
			{raw ? (
				<div className="space-y-2">
					<Label htmlFor={id}>Raw recurrence rule</Label>
					<Textarea
						id={id}
						value={value}
						onChange={(event) => onChange(event.target.value)}
						className="font-mono"
					/>
					<p className="text-sm text-muted-foreground">
						Include DTSTART with TZID to preserve the intended local start time.
						Advanced rules are preserved as entered.
					</p>
					<Button
						type="button"
						variant="outline"
						disabled={!parsed.supported}
						onClick={() => setRaw(false)}
					>
						Use builder
					</Button>
					{!parsed.supported && (
						<p className="text-sm text-muted-foreground">{parsed.reason}</p>
					)}
				</div>
			) : (
				<>
					{parsed.supported ? (
						<BuilderFields
							key={timezone}
							value={parsed.value}
							timezone={timezone}
							onChange={onChange}
						/>
					) : (
						<div className="space-y-2">
							<p>{describeRule(value)}</p>
							<p className="text-sm text-muted-foreground">{parsed.reason}</p>
							<pre className="whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-sm">
								{value || "No recurrence rule"}
							</pre>
						</div>
					)}
					<Button type="button" variant="ghost" onClick={() => setRaw(true)}>
						Edit raw rule
					</Button>
				</>
			)}
		</div>
	);
}

function Choice({
	label,
	value,
	options,
	onChange,
}: {
	label: string;
	value: string;
	options: { value: string; label: string }[];
	onChange: (value: string) => void;
}) {
	const id = useId();
	return (
		<div className="space-y-2">
			<Label htmlFor={id}>{label}</Label>
			<Select value={value} onValueChange={onChange}>
				<SelectTrigger id={id} type="button">
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
				{...register(key, { valueAsNumber: type === "number", onChange: emit })}
			/>
		</div>
	);
	return (
		<div className="space-y-4">
			<div className="flex flex-wrap items-end gap-3">
				{input("interval", "Repeat every", "number", 1)}
				<Choice
					label="Frequency"
					value={current.frequency}
					options={frequencies.map((frequency, index) => ({
						value: frequency,
						label: ["Daily", "Weekly", "Monthly", "Yearly"][index],
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
								{dayNames[index].slice(0, 2)}
							</ToggleGroupItem>
						))}
					</ToggleGroup>
				</div>
			)}
			{current.frequency === "MONTHLY" && (
				<>
					<Choice
						label="Monthly pattern"
						value={current.monthly}
						options={[
							{ value: "day", label: "On day of month" },
							{ value: "weekday", label: "On ordinal weekday" },
						]}
						onChange={(next) => {
							if (next === "day" || next === "weekday") update("monthly", next);
						}}
					/>
					{current.monthly === "weekday" && (
						<div className="flex flex-wrap gap-3">
							<Choice
								label="Ordinal"
								value={String(current.position)}
								options={[1, 2, 3, 4, 5, -1].map((position, index) => ({
									value: String(position),
									label: [
										"First",
										"Second",
										"Third",
										"Fourth",
										"Fifth",
										"Last",
									][index],
								}))}
								onChange={(next) => update("position", Number(next))}
							/>
							<Choice
								label="Weekday"
								value={current.weekday}
								options={weekdays.map((day, index) => ({
									value: day,
									label: dayNames[index],
								}))}
								onChange={(next) => {
									const day = weekdays.find((item) => item === next);
									if (day) update("weekday", day);
								}}
							/>
						</div>
					)}
				</>
			)}
			{current.frequency === "YEARLY" &&
				input("month", "Month", "number", 1, 12)}
			{(current.frequency === "YEARLY" ||
				(current.frequency === "MONTHLY" && current.monthly === "day")) && (
				<>
					{input("day", "Day of month", "number", 1, 31)}
					<p className="text-sm text-muted-foreground">
						Months without this day are skipped.
					</p>
				</>
			)}
			<div className="flex flex-wrap gap-3">
				{input("start", "Start date", "date")}
				{input("time", `Time (${timezone})`, "time")}
			</div>
			<Choice
				label="Ends"
				value={current.end}
				options={[
					{ value: "never", label: "Never" },
					{ value: "until", label: "On date" },
					{ value: "count", label: "After occurrences" },
				]}
				onChange={(next) => {
					if (next === "never" || next === "until" || next === "count")
						update("end", next);
				}}
			/>
			{current.end === "until" && input("until", "End date", "date")}
			{current.end === "count" && input("count", "Occurrences", "number", 1)}
			{error && (
				<p role="alert" className="text-sm text-destructive">
					{error}
				</p>
			)}
		</div>
	);
}
