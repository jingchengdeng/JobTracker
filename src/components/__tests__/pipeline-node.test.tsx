import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { PipelineNode } from "../pipeline-node";
import type { NodeState } from "@/lib/pipeline-layout";

function state(partial: Partial<NodeState> = {}): NodeState {
  return {
    status: "completed",
    attempt: 1,
    durationMs: 420,
    error: null,
    traceback: null,
    startedAt: "2026-04-10T00:00:00Z",
    completedAt: null,
    workflowRunId: "wf-1",
    version: 1,
    ...partial,
  };
}

function renderNode(props: {
  label: string;
  graph: string;
  state: NodeState | undefined;
  onFailedClick?: () => void;
}) {
  return render(
    <ReactFlowProvider>
      <PipelineNode
        data={{
          label: props.label,
          graph: props.graph,
          nodeName: props.label,
          state: props.state,
          onFailedClick: props.onFailedClick,
        }}
        id="master:extract_fields"
        type="pipelineNode"
        selected={false}
        zIndex={0}
        isConnectable={false}
        xPos={0}
        yPos={0}
        dragging={false}
      />
    </ReactFlowProvider>,
  );
}

describe("PipelineNode", () => {
  it("renders the label and graph badge", () => {
    renderNode({ label: "extract_fields", graph: "master", state: state() });
    expect(screen.getByText("extract_fields")).toBeInTheDocument();
    expect(screen.getByText("master")).toBeInTheDocument();
  });

  it("shows ×N attempt badge only when attempt > 1", () => {
    const { unmount } = renderNode({ label: "x", graph: "master", state: state({ attempt: 1 }) });
    expect(screen.queryByText(/×/)).toBeNull();
    unmount();

    renderNode({ label: "x", graph: "master", state: state({ attempt: 3 }) });
    expect(screen.getByText("×3")).toBeInTheDocument();
  });

  it("renders all five statuses without throwing", () => {
    const statuses: NodeState["status"][] = ["pending", "running", "completed", "failed", "skipped"];
    for (const s of statuses) {
      renderNode({ label: "n", graph: "master", state: state({ status: s }) });
    }
  });

  it("fires onFailedClick only for failed nodes", () => {
    const onFailedClick = vi.fn();
    const { unmount } = renderNode({
      label: "n",
      graph: "master",
      state: state({ status: "completed" }),
      onFailedClick,
    });
    fireEvent.click(screen.getByTestId("pipeline-node-card"));
    expect(onFailedClick).not.toHaveBeenCalled();
    unmount();

    renderNode({
      label: "n",
      graph: "master",
      state: state({ status: "failed" }),
      onFailedClick,
    });
    fireEvent.click(screen.getByTestId("pipeline-node-card"));
    expect(onFailedClick).toHaveBeenCalledTimes(1);
  });

  it("renders pending cards when state is undefined", () => {
    renderNode({ label: "not_started", graph: "resume", state: undefined });
    expect(screen.getByText("not_started")).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });
});
