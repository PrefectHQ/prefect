import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useFormContext } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Stepper } from "@/components/ui/stepper";
import { useStepper } from "@/hooks/use-stepper";

const SIGNS = [
	"Aries",
	"Taurus",
	"Gemini",
	"Cancer",
	"Leo",
	"Vigo",
	"Libra",
	"Scorpio",
	"Sagittarius",
	"Capricon",
	"Aquarius",
	"Pisces",
] as const;

const formSchema = z
	.object({
		name: z.string().min(1),
		sign: z.enum(SIGNS),
		rising: z.enum(SIGNS),
	})
	.strict();
const EXAMPLE_STEPS = ["Name", "Sign", "Rising"] as const;
const RENDER_STEP = {
	Name: () => <NameStep />,
	Sign: () => <SignStep />,
	Rising: () => <RisingStep />,
} as const;

export const FormStepperStory = () => {
	const stepper = useStepper(EXAMPLE_STEPS.length);
	const form = useForm<z.infer<typeof formSchema>>({
		resolver: zodResolver(formSchema),
		defaultValues: {
			name: "",
			sign: "Aries",
			rising: "Aries",
		},
	});

	const handleSubmit = (values: z.infer<typeof formSchema>) => {
		if (stepper.isFinalStep) {
			console.log(values);
			stepper.reset();
			form.reset();
		} else {
			// validate step
			switch (EXAMPLE_STEPS[stepper.currentStep]) {
				case "Name":
					void form.trigger("name");
					break;
				case "Sign":
					void form.trigger("sign");
					break;
				case "Rising":
					void form.trigger("rising");
					break;
			}
			stepper.incrementStep();
		}
	};

	return (
		<div className="flex flex-col gap-4">
			<Stepper
				steps={EXAMPLE_STEPS}
				currentStepNum={stepper.currentStep}
				onClick={(step) => stepper.changeStep(step.stepNum)}
				completedSteps={stepper.completedStepsSet}
				visitedSteps={stepper.visitedStepsSet}
			/>
			<Card className="flex flex-col gap-4 p-4">
				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(handleSubmit)(e)}
						className="space-y-4"
					>
						{RENDER_STEP[EXAMPLE_STEPS[stepper.currentStep]]()}

						<div className="flex justify-end gap-2">
							<Button
								variant="secondary"
								disabled={stepper.isStartingStep}
								onClick={stepper.decrementStep}
							>
								Previous
							</Button>
							<Button type="submit">
								{stepper.isFinalStep ? "Save" : "Next"}
							</Button>
						</div>
					</form>
				</Form>
			</Card>
		</div>
	);
};

const NameStep = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="name"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Name</FormLabel>
					<FormControl>
						<Input type="text" {...field} />
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};

const SignStep = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="sign"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Sign</FormLabel>
					<FormControl>
						<Select {...field} onValueChange={field.onChange}>
							<SelectTrigger>
								<SelectValue placeholder="Select a sign" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectLabel>Signs</SelectLabel>
									{SIGNS.map((sign) => (
										<SelectItem key={sign} value={sign}>
											{sign}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};

const RisingStep = () => {
	const form = useFormContext();
	return (
		<FormField
			control={form.control}
			name="rising"
			render={({ field }) => (
				<FormItem>
					<FormLabel>Sign</FormLabel>
					<FormControl>
						<Select {...field} onValueChange={field.onChange}>
							<SelectTrigger>
								<SelectValue placeholder="Select a rising sign" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectLabel>Signs</SelectLabel>
									{SIGNS.map((sign) => (
										<SelectItem key={sign} value={sign}>
											{sign}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
					</FormControl>
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
