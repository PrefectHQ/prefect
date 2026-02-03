import { DialogTrigger } from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";

export const RRuleScheduleForm = () => {
	return (
		<div className="flex flex-col gap-4">
			<p className="text-base">
				Sorry, modifying RRule schedules via the UI is currently unsupported;
				select a different schedule type above or modify your schedule in code.
			</p>

			<DialogFooter>
				<DialogTrigger asChild>
					<Button variant="outline">Close</Button>
				</DialogTrigger>
				<Button disabled>Save</Button>
			</DialogFooter>
		</div>
	);
};
