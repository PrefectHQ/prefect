import type { WorkPool } from "@/api/work-pools";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { WorkPoolPauseResumeToggle } from "./work-pool-card/components/work-pool-pause-resume-toggle";
import { WorkPoolContextMenu } from "./work-pool-card/components/work-pool-context-menu";
import { useDeleteWorkPool } from "@/api/work-pools";
import { Link } from "@tanstack/react-router";
import { toast } from "sonner";

export type WorkPoolDetailsHeaderProps = {
  workPool: WorkPool;
};

export const WorkPoolDetailsHeader = ({ workPool }: WorkPoolDetailsHeaderProps) => {
  const { deleteWorkPool } = useDeleteWorkPool()

  const handleDelete = () => {
    deleteWorkPool(workPool.name, {
      onSuccess: () => toast.success(`${workPool.name} deleted`),
      onError: () => toast.error(`Failed to delete ${workPool.name}`),
    })
  }

  return (
    <div className="flex items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
              Work pools
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="text-xl font-semibold">
            <BreadcrumbPage>{workPool.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center gap-2">
        <WorkPoolPauseResumeToggle workPool={workPool} />
        <WorkPoolContextMenu workPool={workPool} onDelete={handleDelete} />
      </div>
    </div>
  )
}
