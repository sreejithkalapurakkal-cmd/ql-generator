import React, { useState } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from '@dnd-kit/core';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { Badge } from './ui';
import {
  TrackingListMember,
  OUTREACH_STATUSES, OUTREACH_STATUS_LABELS, OUTREACH_STATUS_COLORS,
  SIGNAL_TYPE_LABELS,
} from '../types';

interface KanbanBoardProps {
  members: TrackingListMember[];
  outreachSummary: Record<string, number>;
  onStatusChange: (membershipId: string, newStatus: string) => Promise<void>;
  onCardClick: (member: TrackingListMember) => void;
}

const getHeatColor = (score: number) => {
  if (score >= 75) return '#f5222d';
  if (score >= 50) return '#fa541c';
  if (score >= 25) return '#faad14';
  return '#8c8c8c';
};

// ── Kanban Card ──

const DraggableKanbanCard: React.FC<{
  member: TrackingListMember;
  onClick: () => void;
  activeDragId: string | null;
}> = ({ member, onClick, activeDragId }) => {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: member.membership_id,
  });
  const isActive = isDragging || activeDragId === member.membership_id;

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={onClick}
      className={`bg-white rounded-lg border border-gray-200 p-3 cursor-grab transition-all ${
        isActive ? 'opacity-40 shadow-md' : 'hover:shadow-sm hover:border-gray-300'
      }`}
    >
      <KanbanCardContent member={member} />
    </div>
  );
};

const KanbanCardContent: React.FC<{
  member: TrackingListMember;
  isOverlay?: boolean;
}> = ({ member, isOverlay }) => (
  <div
    className={isOverlay ? 'bg-white rounded-lg border border-gray-200 p-3 shadow-lg rotate-1 cursor-grabbing' : ''}
  >
    <div className="flex items-start justify-between gap-2">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {member.company_name || 'Unknown'}
        </p>
        <p className="text-[11px] text-gray-400 mt-0.5">{member.domain}</p>
      </div>
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0"
        style={{
          background: `${getHeatColor(member.signal_heat_score)}15`,
          color: getHeatColor(member.signal_heat_score),
        }}
      >
        {Math.round(member.signal_heat_score)}
      </div>
    </div>

    {member.latest_signal && (
      <div className="mt-2 pt-2 border-t border-gray-100">
        <Badge variant="signal-type" signalType={member.latest_signal.signal_type} className="text-[10px]">
          {SIGNAL_TYPE_LABELS[member.latest_signal.signal_type] || member.latest_signal.signal_type}
        </Badge>
        <p className="text-[11px] text-gray-500 mt-1 line-clamp-2 leading-snug">
          {member.latest_signal.title}
        </p>
      </div>
    )}

    {member.industry && (
      <p className="text-[11px] text-gray-300 mt-1.5">{member.industry}</p>
    )}
  </div>
);

// ── Droppable Column ──

const KanbanColumn: React.FC<{
  status: string;
  items: TrackingListMember[];
  count: number;
  isOver: boolean;
  onCardClick: (member: TrackingListMember) => void;
  activeDragId: string | null;
}> = ({ status, items, count, isOver, onCardClick, activeDragId }) => {
  const { setNodeRef } = useDroppable({ id: status });

  return (
    <div
      ref={setNodeRef}
      className={`min-w-[260px] max-w-[280px] flex-[0_0_260px] rounded-xl p-3 transition-all ${
        isOver
          ? 'bg-brand-pale border-2 border-dashed border-brand'
          : 'bg-gray-50 border border-gray-100'
      }`}
    >
      {/* Column header */}
      <div className="flex items-center gap-2 mb-3 px-1">
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ background: OUTREACH_STATUS_COLORS[status] }}
        />
        <span className="text-xs font-semibold text-gray-900">
          {OUTREACH_STATUS_LABELS[status]}
        </span>
        <Badge variant="count" className="ml-auto">{count}</Badge>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-2 min-h-[60px]">
        {items.length === 0 ? (
          <div className="py-5 text-center text-xs text-gray-300 border-2 border-dashed border-gray-200 rounded-lg">
            Drop here
          </div>
        ) : (
          items.map((m) => (
            <DraggableKanbanCard
              key={m.membership_id}
              member={m}
              onClick={() => onCardClick(m)}
              activeDragId={activeDragId}
            />
          ))
        )}
      </div>
    </div>
  );
};

// ── Main KanbanBoard ──

const KanbanBoard: React.FC<KanbanBoardProps> = ({
  members, outreachSummary, onStatusChange, onCardClick,
}) => {
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [overColumnId, setOverColumnId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
  );

  // Group members by outreach_status
  const statusGroups: Record<string, TrackingListMember[]> = {};
  OUTREACH_STATUSES.forEach((s) => { statusGroups[s] = []; });
  members.forEach((m) => {
    if (statusGroups[m.outreach_status]) {
      statusGroups[m.outreach_status].push(m);
    } else {
      statusGroups['not_started'].push(m);
    }
  });

  const activeMember = activeDragId
    ? members.find((m) => m.membership_id === activeDragId) || null
    : null;

  const handleDragStart = (event: DragStartEvent) => {
    setActiveDragId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const overId = event.over?.id as string | undefined;
    if (overId && (OUTREACH_STATUSES as readonly string[]).includes(overId)) {
      setOverColumnId(overId);
    } else {
      setOverColumnId(null);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveDragId(null);
    setOverColumnId(null);

    if (!over) return;

    const membershipId = active.id as string;
    const newStatus = over.id as string;

    if (!(OUTREACH_STATUSES as readonly string[]).includes(newStatus)) return;

    const member = members.find((m) => m.membership_id === membershipId);
    if (!member || member.outreach_status === newStatus) return;

    onStatusChange(membershipId, newStatus);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-3.5 overflow-x-auto pb-5 min-h-[400px]">
        {OUTREACH_STATUSES.map((status) => {
          const items = statusGroups[status];
          const count = outreachSummary[status] || items.length;
          return (
            <KanbanColumn
              key={status}
              status={status}
              items={items}
              count={count}
              isOver={overColumnId === status}
              onCardClick={onCardClick}
              activeDragId={activeDragId}
            />
          );
        })}
      </div>

      {/* Drag overlay */}
      <DragOverlay>
        {activeMember ? (
          <KanbanCardContent
            member={activeMember}
            isOverlay
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};

export default KanbanBoard;
