import { useDeferredValue, useMemo, useState } from "react";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";
import {
	DropdownMenuLabel,
	DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

function getTimezoneLabel(value: string): string {
	return value.replaceAll("/", " / ").replaceAll("_", " ");
}

const UTC_ALIASES = new Set([
	"UTC",
	"Etc/UTC",
	"Etc/UCT",
	"Etc/Universal",
	"Etc/Zulu",
	"Etc/GMT",
	"Etc/GMT+0",
	"Etc/GMT-0",
	"Etc/GMT0",
	"Etc/Greenwich",
]);

function isUTCAlias(timezone: string): boolean {
	return UTC_ALIASES.has(timezone);
}

function normalizeTimezone(timezone: string): string;
function normalizeTimezone(
	timezone: string | undefined | null,
): string | undefined | null;
function normalizeTimezone(
	timezone: string | undefined | null,
): string | undefined | null {
	if (!timezone) {
		return timezone;
	}
	return isUTCAlias(timezone) ? "UTC" : timezone;
}

const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
const normalizedLocalTimezone = normalizeTimezone(localTimezone);

const SUGGESTED_TIMEZONES = [
	{ label: "UTC", value: "UTC" },
	...(normalizedLocalTimezone !== "UTC"
		? [
				{
					label: getTimezoneLabel(localTimezone),
					value: normalizedLocalTimezone,
				},
			]
		: []),
];

const TIMEZONES = Intl.supportedValuesOf("timeZone")
	.filter(
		(timezone) =>
			normalizeTimezone(timezone) !== "UTC" &&
			timezone !== normalizedLocalTimezone,
	)
	.map((timezone) => ({
		label: getTimezoneLabel(timezone),
		value: timezone,
	}));

const ALL_TIMEZONES = [...SUGGESTED_TIMEZONES, ...TIMEZONES];

// Rendering every supported timezone at once makes each keystroke re-render
// hundreds of command items, which is slow enough to be noticeable. Any
// timezone past the limit is still reachable by searching for it.
const MAX_VISIBLE_TIMEZONES = 100;

type TimezoneSelectProps = {
	selectedValue: string | undefined | null;
	onSelect: (value: string) => void;
};

export const TimezoneSelect = ({
	selectedValue = "",
	onSelect,
}: TimezoneSelectProps) => {
	const [search, setSearch] = useState("");

	const deferredSearch = useDeferredValue(search);
	const normalizedSelectedValue = normalizeTimezone(selectedValue);

	const filteredSuggestedTimezones = useMemo(() => {
		return SUGGESTED_TIMEZONES.filter(
			(timeZone) =>
				timeZone.label.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				timeZone.value.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch]);

	const filteredTimezones = useMemo(() => {
		const matches = TIMEZONES.filter(
			(timeZone) =>
				timeZone.label.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				timeZone.value.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
		return {
			timezones: matches.slice(0, MAX_VISIBLE_TIMEZONES),
			truncated: matches.length > MAX_VISIBLE_TIMEZONES,
		};
	}, [deferredSearch]);

	const selectedLabel = useMemo(() => {
		if (!normalizedSelectedValue) {
			return undefined;
		}
		return (
			ALL_TIMEZONES.find(({ value }) => value === normalizedSelectedValue)
				?.label ?? getTimezoneLabel(normalizedSelectedValue)
		);
	}, [normalizedSelectedValue]);

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(normalizedSelectedValue)}
				aria-label="Select timezone"
			>
				{selectedLabel ?? "Select timezone"}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search"
				/>
				<ComboboxCommandEmtpy>No timezone found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredSuggestedTimezones.length > 0 && (
							<DropdownMenuLabel>Suggested timezones</DropdownMenuLabel>
						)}
						{filteredSuggestedTimezones.map(({ label, value }) => {
							return (
								<ComboboxCommandItem
									key={value}
									selected={normalizedSelectedValue === value}
									onSelect={(value) => {
										onSelect(value);
										setSearch("");
									}}
									value={value}
								>
									{label}
								</ComboboxCommandItem>
							);
						})}
						<DropdownMenuSeparator />
						{filteredTimezones.timezones.length > 0 && (
							<DropdownMenuLabel>All timezones</DropdownMenuLabel>
						)}
						{filteredTimezones.timezones.map(({ label, value }) => {
							return (
								<ComboboxCommandItem
									key={value}
									selected={normalizedSelectedValue === value}
									onSelect={(value) => {
										onSelect(value);
										setSearch("");
									}}
									value={value}
								>
									{label}
								</ComboboxCommandItem>
							);
						})}
						{filteredTimezones.truncated && (
							<div className="px-2 py-1.5 text-xs text-muted-foreground">
								Search to see more timezones
							</div>
						)}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
