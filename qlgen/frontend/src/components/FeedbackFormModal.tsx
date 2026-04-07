import React, { useState } from 'react';
import { Modal, Form, Input, Select, Button, message } from 'antd';
import { createFeedback } from '../api/feedbackApi';
import type { FeedbackType } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
}

const typeOptions: { label: string; value: FeedbackType }[] = [
  { label: 'Feedback', value: 'feedback' },
  { label: 'Complaint', value: 'complaint' },
  { label: 'Bug Report', value: 'bug_report' },
  { label: 'Feature Request', value: 'feature_request' },
];

const FeedbackFormModal: React.FC<Props> = ({ open, onClose }) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (values: { type: FeedbackType; subject: string; description: string }) => {
    setSubmitting(true);
    try {
      await createFeedback(values);
      message.success('Feedback submitted successfully');
      form.resetFields();
      onClose();
    } catch {
      message.error('Failed to submit feedback');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title="Submit Feedback"
      open={open}
      onCancel={handleCancel}
      footer={null}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{ type: 'feedback' }}
        style={{ marginTop: 16 }}
      >
        <Form.Item
          name="type"
          label="Type"
          rules={[{ required: true, message: 'Please select a type' }]}
        >
          <Select options={typeOptions} />
        </Form.Item>
        <Form.Item
          name="subject"
          label="Subject"
          rules={[{ required: true, message: 'Please enter a subject' }]}
        >
          <Input placeholder="Brief summary of your feedback" maxLength={255} />
        </Form.Item>
        <Form.Item
          name="description"
          label="Description"
          rules={[{ required: true, message: 'Please enter a description' }]}
        >
          <Input.TextArea
            rows={5}
            placeholder="Describe your feedback, complaint, or suggestion in detail..."
          />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Button type="primary" htmlType="submit" loading={submitting} block>
            Submit
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default FeedbackFormModal;
