import { CronInput } from "@/components/ui/cron-input";
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

type CronScheduleFormProps = {
	form: UseFormReturn<FormSchema>;
};

export const CronScheduleForm = ({ form }: CronScheduleFormProps) => (
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
		<div className="flex gap-2">
			<div className="w-3/4">
				<FormField
					control={form.control}
					name="schedule.cron"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Value</FormLabel>
							<FormControl>
								<CronInput {...field} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
			</div>
			<FormField
				control={form.control}
				name="schedule.day_or"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Day Or</FormLabel>
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
		</div>
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
