import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

export function ArchitectureFlow() {
  const initialNodes: Node[] = useMemo(
    () => [
      {
        id: '1',
        data: { label: 'User Query / Ingestion' },
        position: { x: 30, y: 100 },
        sourcePosition: Position.Right,
        style: {
          background: '#FFFFFF',
          color: '#0F172A',
          border: '2px solid #2563EB',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '700',
          boxShadow: '0 2px 4px 0 rgba(0, 0, 0, 0.05)',
        },
      },
      {
        id: '2',
        data: { label: 'Hybrid Retrieval\n(BM25 + pgvector)' },
        position: { x: 240, y: 40 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          background: '#EFF6FF',
          color: '#1D4ED8',
          border: '2px solid #2563EB',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '600',
        },
      },
      {
        id: '3',
        data: { label: 'Cross-Encoder Reranking' },
        position: { x: 460, y: 40 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          background: '#FFFFFF',
          color: '#0F172A',
          border: '2px solid #2563EB',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '600',
        },
      },
      {
        id: '4',
        data: { label: 'LangGraph State Workflow' },
        position: { x: 680, y: 100 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          background: '#FFFFFF',
          color: '#0F172A',
          border: '2px solid #2563EB',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '700',
        },
      },
      {
        id: '5',
        data: { label: 'LLM Generation & Citations' },
        position: { x: 920, y: 40 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          background: '#FFFFFF',
          color: '#0F172A',
          border: '2px solid #2563EB',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '600',
        },
      },
      {
        id: '6',
        data: { label: 'Verification & Hallucination Check' },
        position: { x: 920, y: 160 },
        sourcePosition: Position.Left,
        targetPosition: Position.Right,
        style: {
          background: '#FFFFFF',
          color: '#0F172A',
          border: '2px solid #2563EB',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '600',
        },
      },
      {
        id: '7',
        data: { label: 'Self-Healing Engine\n(Query Rewrite / Recovery)' },
        position: { x: 460, y: 160 },
        sourcePosition: Position.Left,
        targetPosition: Position.Right,
        style: {
          background: '#FEF2F2',
          color: '#B91C1C',
          border: '2px solid #DC2626',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '700',
        },
      },
      {
        id: '8',
        data: { label: 'Verified Output & Citations' },
        position: { x: 1160, y: 100 },
        targetPosition: Position.Left,
        style: {
          background: '#F0FDF4',
          color: '#15803D',
          border: '2px solid #16A34A',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '700',
        },
      },
    ],
    []
  );

  const initialEdges: Edge[] = useMemo(
    () => [
      {
        id: 'e1-2',
        source: '1',
        target: '2',
        animated: true,
        style: { stroke: '#2563EB', strokeWidth: 2 },
      },
      {
        id: 'e2-3',
        source: '2',
        target: '3',
        animated: true,
        style: { stroke: '#2563EB', strokeWidth: 2 },
      },
      {
        id: 'e3-4',
        source: '3',
        target: '4',
        animated: true,
        style: { stroke: '#2563EB', strokeWidth: 2 },
      },
      {
        id: 'e4-5',
        source: '4',
        target: '5',
        animated: true,
        style: { stroke: '#2563EB', strokeWidth: 2 },
      },
      {
        id: 'e5-6',
        source: '5',
        target: '6',
        animated: true,
        style: { stroke: '#2563EB', strokeWidth: 2 },
      },
      {
        id: 'e6-7',
        source: '6',
        target: '7',
        animated: true,
        label: 'If Hallucination Detected',
        labelStyle: { fill: '#f87171', fontSize: 10 },
        style: { stroke: '#ef4444', strokeDasharray: '4 4' },
      },
      {
        id: 'e7-2',
        source: '7',
        target: '2',
        animated: true,
        label: 'Self-Healing Retry',
        labelStyle: { fill: '#f87171', fontSize: 10 },
        style: { stroke: '#ef4444' },
      },
      {
        id: 'e6-8',
        source: '6',
        target: '8',
        animated: true,
        label: 'Passed Verification',
        labelStyle: { fill: '#34d399', fontSize: 10 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' },
        style: { stroke: '#10b981' },
      },
    ],
    []
  );

  return (
    <div className="h-[280px] w-full rounded-xl border border-slate-800 bg-slate-950/80 overflow-hidden">
      <ReactFlow
        nodes={initialNodes}
        edges={initialEdges}
        fitView
        attributionPosition="bottom-right"
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnScroll={false}
      >
        <Background color="#334155" gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
