import { buildGetWorkPoolQuery, useUpdateWorkPool } from "@/api/work-pools";
import { WorkPoolForm, type WorkPoolFormValues } from "@/components/work-pools/work-pool-form";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

export const Route = createFileRoute(
  "/work-pools/work-pool_/$workPoolName/edit",
)({
  component: RouteComponent,
  loader: async ({ context, params }) => {
    const { workPoolName } = params;
    await context.queryClient.ensureQueryData(buildGetWorkPoolQuery(workPoolName));
  },
  wrapInSuspense: true,
});

function RouteComponent() {
  const { workPoolName } = Route.useParams();
  const navigate = Route.useNavigate();
  const { data: workPool } = useSuspenseQuery(buildGetWorkPoolQuery(workPoolName));
  const { updateWorkPool, isPending } = useUpdateWorkPool();

  const onSubmit = (values: WorkPoolFormValues) => {
    updateWorkPool(
      {
        name: workPoolName,
        description: values.description,
        concurrency_limit: values.concurrency_limit,
        is_paused: values.is_paused,
        base_job_template: null,
        storage_configuration: null,
      },
      {
        onSuccess: () => {
          toast.success("Work pool updated");
          navigate({ to: "/work-pools/work-pool/$workPoolName", params: { workPoolName } });
        },
        onError: (err) => {
          const message = err.message ?? "Unknown error";
          toast.error(message);
        },
      },
    );
  };

  return <WorkPoolForm workPool={workPool} onSubmit={onSubmit} loading={isPending} />;
}
