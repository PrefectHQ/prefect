import { DialogTrigger } from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Typography } from "@/components/ui/typography";

export const RRuleScheduleForm = () => {
	return (
		<div className="flex flex-col gap-4">
			<Typography>
				Sorry, modifying RRule schedules via the UI is currently unsupported;
				select a different schedule type above or modify your schedule in code.
			</Typography>

			<DialogFooter>
				<DialogTrigger asChild>
					<Button variant="outline">Close</Button>
				</DialogTrigger>
				<Button disabled>Save</Button>
			</DialogFooter>
		</div>
	);
};
