import { Calendar } from "@/components/ui/calendar";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Switch } from "@/components/ui/switch";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { UseFormReturn } from "react-hook-form";
import type { FormSchema } from "./use-create-or-edit-schedule-form";

type IntervalScheduleFormProps = {
	form: UseFormReturn<FormSchema>;
};

export const IntervalScheduleForm = ({ form }: IntervalScheduleFormProps) => (
	<div className="flex flex-col gap-4">
		<FormField
			control={form.control}
			name="active"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Active</FormLabel>
					<FormControl>
						<Switch
							className="block"
							checked={field.value}
							onCheckedChange={field.onChange}
						/>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
		<div className="flex gap-2"></div>
		<FormField
			control={form.control}
			name="schedule.anchor_date"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Anchor date</FormLabel>
					<FormControl>
						<Calendar
							mode="single"
							selected={new Date(field.value)}
							onSelect={(value) => String(field.onChange(value))}
							required
						/>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
		<FormField
			control={form.control}
			name="schedule.timezone"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Timezone</FormLabel>
					<FormControl>
						<TimezoneSelect
							selectedValue={field.value}
							onSelect={field.onChange}
						/>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	</div>
);
