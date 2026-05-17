import React, { useEffect, useState } from 'react';
import { Modal, Select, Input, Button, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { Badge } from './ui';
import {
  getTrackingLists, createTrackingList, promoteFromPipeline, addListMembers,
} from '../api/trackingApi';
import { TrackingList } from '../types';

interface AddToTrackingListModalProps {
  open: boolean;
  onClose: () => void;
  companyIds?: string[];
  companyKbIds?: string[];
  source?: 'pipeline' | 'kb_browser' | 'manual';
}

const AddToTrackingListModal: React.FC<AddToTrackingListModalProps> = ({
  open, onClose, companyIds, companyKbIds, source = 'pipeline',
}) => {
  const [lists, setLists] = useState<TrackingList[]>([]);
  const [selectedListId, setSelectedListId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [showNewList, setShowNewList] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const itemCount = (companyIds?.length || 0) + (companyKbIds?.length || 0);

  useEffect(() => {
    if (open) {
      getTrackingLists()
        .then((res) => setLists(res.data.lists || []))
        .catch(() => {});
    }
  }, [open]);

  const handleCreateList = async () => {
    if (!newListName.trim()) return;
    setCreating(true);
    try {
      const res = await createTrackingList({ name: newListName.trim() });
      setLists((prev) => [res.data, ...prev]);
      setSelectedListId(res.data.id);
      setShowNewList(false);
      setNewListName('');
    } catch {
      message.error('Failed to create list');
    } finally {
      setCreating(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedListId) { message.warning('Select a tracking list'); return; }
    setSubmitting(true);
    try {
      let added = 0;
      if (companyIds && companyIds.length > 0) {
        const res = await promoteFromPipeline(selectedListId, companyIds);
        added += res.data.promoted;
      }
      if (companyKbIds && companyKbIds.length > 0) {
        const res = await addListMembers(selectedListId, {
          company_kb_ids: companyKbIds,
          added_from: source,
        });
        added += res.data.added;
      }
      message.success(`${added} ${added === 1 ? 'company' : 'companies'} added to tracking list`);
      onClose();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to add companies');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Add to Tracking List"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>Cancel</Button>,
        <Button key="add" type="primary" loading={submitting} onClick={handleSubmit} disabled={!selectedListId}>
          Add {itemCount} {itemCount === 1 ? 'Company' : 'Companies'}
        </Button>,
      ]}
    >
      <div className="mt-3">
        <Badge className="mb-4 bg-brand-pale text-brand">
          {itemCount} {itemCount === 1 ? 'company' : 'companies'} selected
        </Badge>

        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
          Select Tracking List
        </label>
        <Select
          placeholder="Choose a tracking list..."
          value={selectedListId}
          onChange={setSelectedListId}
          style={{ width: '100%', marginBottom: 12 }}
          options={lists.map((tl) => ({
            value: tl.id,
            label: `${tl.name} (${tl.company_count} companies)`,
          }))}
        />

        {showNewList ? (
          <div className="flex items-center gap-2 mt-1">
            <Input
              placeholder="New list name"
              value={newListName}
              onChange={(e) => setNewListName(e.target.value)}
              onPressEnter={handleCreateList}
              autoFocus
              style={{ width: 260 }}
            />
            <Button onClick={handleCreateList} loading={creating} type="primary" size="small">
              Create
            </Button>
            <Button onClick={() => setShowNewList(false)} size="small">Cancel</Button>
          </div>
        ) : (
          <Button
            type="link"
            icon={<PlusOutlined />}
            onClick={() => setShowNewList(true)}
            className="!p-0 !text-xs"
          >
            Create new list
          </Button>
        )}
      </div>
    </Modal>
  );
};

export default AddToTrackingListModal;
