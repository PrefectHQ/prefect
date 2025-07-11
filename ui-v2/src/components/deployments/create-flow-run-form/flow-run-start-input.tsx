import { useState } from "react";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const TAB_OPTIONS = {
	now: {
		label: "Now",
		value: "now",
	},
	later: {
		label: "Later",
		value: "later",
	},
} as const;
type TabOptions = "now" | "later";

type FlowRunStartProps = {
	value: null | string;
	onValueChange: (value: string | null) => void;
};

export const FlowRunStartInput = ({
	value,
	onValueChange,
}: FlowRunStartProps) => {
	const [selectedTab, setSelectedTab] = useState<TabOptions>(
		TAB_OPTIONS.now.value,
	);

	const handleValueChange = (newValue: string | undefined) =>
		onValueChange(newValue ?? null);

	return (
		<Tabs defaultValue={TAB_OPTIONS.now.value} value={selectedTab}>
			<TabsList>
				<TabsTrigger
					value={TAB_OPTIONS.now.value}
					onClick={() => {
						onValueChange(null);
						setSelectedTab(TAB_OPTIONS.now.value);
					}}
				>
					{TAB_OPTIONS.now.label}
				</TabsTrigger>
				<TabsTrigger
					value={TAB_OPTIONS.later.value}
					onClick={() => setSelectedTab(TAB_OPTIONS.later.value)}
				>
					{TAB_OPTIONS.later.label}
				</TabsTrigger>
			</TabsList>
			<TabsContent value={TAB_OPTIONS.now.value}>
				{/** Leave empty */}
			</TabsContent>
			<TabsContent value={TAB_OPTIONS.later.value}>
				<div className="flex flex-col gap-2">
					<Label htmlFor="start-date-time-picker">Start date</Label>
					<DateTimePicker
						id="start-date-time-picker"
						value={value ?? undefined}
						onValueChange={handleValueChange}
					/>
				</div>
			</TabsContent>
		</Tabs>
	);
};
