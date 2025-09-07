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
		.number()
		.positive({ message: "Concurrency limit must be greater than 0" })
		.nullable()
		.optional()
		.or(z.string())
		.pipe(
			z.union([
				z.string().transform((val) => {
					if (val === "" || val === null) return null;
					const num = Number(val);
					if (Number.isNaN(num)) return null;
					return num;
				}),
				z.number().nullable(),
			]),
		),
	priority: z
		.number()
		.positive({ message: "Priority must be greater than 0" })
		.nullable()
		.optional()
		.or(z.string())
		.pipe(
			z.union([
				z.string().transform((val) => {
					if (val === "" || val === null) return null;
					const num = Number(val);
					if (Number.isNaN(num)) return null;
					return num;
				}),
				z.number().nullable(),
			]),
		),
});

const DEFAULT_VALUES = {
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
