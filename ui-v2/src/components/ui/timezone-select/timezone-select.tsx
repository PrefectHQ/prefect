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

const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

const SUGGESTED_TIMEZONES = [
	{ label: "UTC", value: "Etc/UTC" },
	{
		label: getTimezoneLabel(localTimezone),
		value: localTimezone,
	},
];

const TIMEZONES = Intl.supportedValuesOf("timeZone")
	.map((timezone) => ({
		label: getTimezoneLabel(timezone),
		value: timezone,
	}))
	.slice(0, 5);

const ALL_TIMEZONES = [...SUGGESTED_TIMEZONES, ...TIMEZONES];

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

	const filteredSuggestedTimezones = useMemo(() => {
		return SUGGESTED_TIMEZONES.filter(
			(timeZone) =>
				timeZone.label.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				timeZone.value.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch]);

	const filteredTimezones = useMemo(() => {
		return TIMEZONES.filter(
			(timeZone) =>
				timeZone.label.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				timeZone.value.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch]);

	const selectedTimezone = useMemo(
		() => ALL_TIMEZONES.find(({ value }) => value === selectedValue),
		[selectedValue],
	);

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(selectedValue)}
				aria-label="Select timezone"
			>
				{selectedTimezone?.label ?? "Select timezone"}
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
									selected={selectedValue === value}
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
						{filteredTimezones.length > 0 && (
							<DropdownMenuLabel>All timezones</DropdownMenuLabel>
						)}
						{filteredTimezones.map(({ label, value }) => {
							return (
								<ComboboxCommandItem
									key={value}
									selected={selectedValue === value}
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
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
