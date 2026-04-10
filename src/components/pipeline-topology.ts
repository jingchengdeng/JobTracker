/**
 * Static ReactFlow topology for the pipeline debug tab.
 *
 * Keep in sync with the backend graph shape:
 *   - backend/src/agents/master_workflow.py
 *   - backend/src/agents/extraction_pipeline.py
 *   - backend/src/agents/orchestrator.py
 *   - backend/src/agents/linkedin_graph.py
 *
 * If a node is added or removed backend-side, update this file too.
 */
import type { Node, Edge } from "@xyflow/react";

export type NodeKey = string;

export type TopologyNode = {
  id: NodeKey;
  label: string;
  graph: "master" | "resume" | "linkedin";
  parent?: NodeKey;
};

export const MASTER_NODES: TopologyNode[] = [
  { id: "master:extract_fields", label: "extract_fields", graph: "master" },
  { id: "master:validate_fields", label: "validate_fields", graph: "master" },
  { id: "master:insert_job", label: "insert_job", graph: "master" },
  { id: "master:resolve_default_resume", label: "resolve_default_resume", graph: "master" },
  { id: "master:resume_branch", label: "resume_branch", graph: "master" },
  { id: "master:linkedin_branch", label: "linkedin_branch", graph: "master" },
  { id: "master:fail_node", label: "fail_node", graph: "master" },
];

export const RESUME_NODES: TopologyNode[] = [
  { id: "resume:jd_analysis", label: "jd_analysis", graph: "resume", parent: "resume-group" },
  { id: "resume:gap_analysis", label: "gap_analysis", graph: "resume", parent: "resume-group" },
  { id: "resume:suggestions", label: "suggestions", graph: "resume", parent: "resume-group" },
  { id: "resume:rewrite", label: "rewrite", graph: "resume", parent: "resume-group" },
];

export const LINKEDIN_NODES: TopologyNode[] = [
  { id: "linkedin:load_job", label: "load_job", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:precondition_check", label: "precondition_check", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:analyze_jd", label: "analyze_jd", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:extract_domain_from_jd", label: "extract_domain", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:load_brave_key", label: "load_brave_key", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:brave_domain_search", label: "brave_domain_search", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:enrich_company_apollo", label: "enrich_apollo", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:build_queries", label: "build_queries", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:run_brave_searches", label: "run_brave_searches", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:run_browser_searches", label: "run_browser_searches", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:review_leadership", label: "review_leadership", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:merge_dedup", label: "merge_dedup", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:score_relevance", label: "score_relevance", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:filter_rank", label: "filter_rank", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:generate_notes", label: "generate_notes", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:compile_summary", label: "compile_summary", graph: "linkedin", parent: "linkedin-group" },
  { id: "linkedin:save_results", label: "save_results", graph: "linkedin", parent: "linkedin-group" },
];

type Pos = { x: number; y: number };

const POSITIONS: Record<string, Pos> = {
  "master:extract_fields": { x: 40, y: 20 },
  "master:validate_fields": { x: 220, y: 20 },
  "master:insert_job": { x: 400, y: 20 },
  "master:resolve_default_resume": { x: 580, y: 20 },
  "master:resume_branch": { x: 760, y: -40 },
  "master:linkedin_branch": { x: 760, y: 80 },
  "master:fail_node": { x: 400, y: 120 },
  "resume-group": { x: 0, y: 200 },
  "linkedin-group": { x: 0, y: 360 },
};

export function buildTopology(): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];

  nodes.push(
    {
      id: "resume-group",
      type: "group",
      position: POSITIONS["resume-group"],
      data: { label: "RESUME SUB-PIPELINE" },
      style: { width: 900, height: 120, backgroundColor: "rgba(129,140,248,0.05)", border: "1px dashed rgba(129,140,248,0.38)" },
    },
    {
      id: "linkedin-group",
      type: "group",
      position: POSITIONS["linkedin-group"],
      data: { label: "LINKEDIN SUB-PIPELINE" },
      style: { width: 1600, height: 120, backgroundColor: "rgba(129,140,248,0.05)", border: "1px dashed rgba(129,140,248,0.38)" },
    },
  );

  MASTER_NODES.forEach((n) => {
    nodes.push({
      id: n.id,
      type: "pipelineNode",
      position: POSITIONS[n.id] ?? { x: 0, y: 0 },
      data: { label: n.label, graph: n.graph, nodeName: n.label },
    });
  });

  RESUME_NODES.forEach((n, i) => {
    nodes.push({
      id: n.id,
      type: "pipelineNode",
      parentId: "resume-group",
      extent: "parent",
      position: { x: 20 + i * 200, y: 40 },
      data: { label: n.label, graph: n.graph, nodeName: n.label },
    });
  });

  LINKEDIN_NODES.forEach((n, i) => {
    nodes.push({
      id: n.id,
      type: "pipelineNode",
      parentId: "linkedin-group",
      extent: "parent",
      position: { x: 20 + (i % 8) * 190, y: 40 + Math.floor(i / 8) * 50 },
      data: { label: n.label, graph: n.graph, nodeName: n.label },
    });
  });

  const edges: Edge[] = [
    { id: "e1", source: "master:extract_fields", target: "master:validate_fields" },
    { id: "e2", source: "master:validate_fields", target: "master:insert_job" },
    { id: "e3", source: "master:insert_job", target: "master:resolve_default_resume" },
    { id: "e4", source: "master:resolve_default_resume", target: "master:resume_branch" },
    { id: "e5", source: "master:resolve_default_resume", target: "master:linkedin_branch" },
    { id: "e6", source: "master:validate_fields", target: "master:fail_node", animated: false },
  ];

  return { nodes, edges };
}
