import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateWorkPoolQueueMutation } from "@/api/work-pool-queues";

const formSchema = z.object({
	name: z
		.string()
		.min(1, { message: "Name is required" })
		.regex(/^[a-zA-Z0-9_-]+$/, {
			message:
				"Name can only contain letters, numbers, hyphens, and underscores",
		}),
	description: z.string().nullable().optional(),
	is_paused: z.boolean().default(false),
	concurrency_limit: z
		.union([
			z.string().transform((val) => {
				if (val === "" || val === null || val === undefined) return null;
				const num = Number(val);
				if (Number.isNaN(num)) return null;
				if (num <= 0)
					throw new Error("Flow run concurrency must be greater than 0");
				return num;
			}),
			z
				.number()
				.positive({ message: "Flow run concurrency must be greater than 0" })
				.nullable(),
		])
		.nullable()
		.optional(),
	priority: z
		.union([
			z.string().transform((val) => {
				if (val === "" || val === null || val === undefined) return null;
				const num = Number(val);
				if (Number.isNaN(num)) return null;
				if (num <= 0) throw new Error("Priority must be greater than 0");
				if (!Number.isInteger(num))
					throw new Error("Priority must be a whole number");
				return num;
			}),
			z
				.number()
				.int({ message: "Priority must be a whole number" })
				.positive({ message: "Priority must be greater than 0" })
				.nullable(),
		])
		.nullable()
		.optional(),
});

export const DEFAULT_VALUES = {
	name: "",
	description: "",
	is_paused: false,
	concurrency_limit: null,
	priority: null,
} as const;

type UseCreateWorkPoolQueueFormOptions = {
	workPoolName: string;
	onSubmit: () => void;
};

export const useCreateWorkPoolQueueForm = ({
	workPoolName,
	onSubmit,
}: UseCreateWorkPoolQueueFormOptions) => {
	const { mutate: createWorkPoolQueue, isPending: isLoading } =
		useCreateWorkPoolQueueMutation();

	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: DEFAULT_VALUES,
	});

	const create = (values: z.infer<typeof formSchema>) => {
		const workQueueData = {
			...values,
			description: values.description || null,
		};

		createWorkPoolQueue(
			{
				workPoolName,
				workQueueData,
			},
			{
				onSuccess: () => {
					toast.success("Work queue created");
					form.reset(DEFAULT_VALUES);
					onSubmit();
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while creating work queue.";
					form.setError("root", { message });
				},
			},
		);
	};

	return {
		form,
		create,
		isLoading,
	};
};
