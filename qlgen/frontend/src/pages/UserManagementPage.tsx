import React, { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Tag, message, Popconfirm,
  Typography, Space, Switch, Avatar,
} from 'antd';
import { PlusOutlined, UserOutlined, DeleteOutlined } from '@ant-design/icons';
import { listUsers, inviteUser, updateUser, deleteUser } from '../api/usersApi';
import type { AuthUser } from '../api/authApi';
import { useAuth } from '../context/AuthContext';

const { Title } = Typography;

const UserManagementPage: React.FC = () => {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [form] = Form.useForm();
  const { user: currentUser } = useAuth();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const resp = await listUsers();
      setUsers(resp.data);
    } catch {
      message.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleInvite = async (values: { email: string; role: string }) => {
    try {
      await inviteUser(values.email, values.role);
      message.success(`Invited ${values.email}`);
      setInviteModalOpen(false);
      form.resetFields();
      fetchUsers();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to invite user';
      message.error(detail);
    }
  };

  const handleToggleActive = async (userId: string, isActive: boolean) => {
    try {
      await updateUser(userId, { is_active: isActive });
      message.success(isActive ? 'User activated' : 'User deactivated');
      fetchUsers();
    } catch {
      message.error('Failed to update user');
    }
  };

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await updateUser(userId, { role });
      message.success('Role updated');
      fetchUsers();
    } catch {
      message.error('Failed to update role');
    }
  };

  const handleDelete = async (userId: string) => {
    try {
      await deleteUser(userId);
      message.success('User deleted');
      fetchUsers();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete user';
      message.error(detail);
    }
  };

  const columns = [
    {
      title: 'User',
      key: 'user',
      render: (_: unknown, record: AuthUser) => (
        <Space>
          {record.picture_url ? (
            <Avatar size={32} src={record.picture_url} />
          ) : (
            <Avatar size={32} icon={<UserOutlined />} style={{ background: '#5C2D8F' }} />
          )}
          <div>
            <div style={{ fontWeight: 500 }}>{record.name || '—'}</div>
            <div style={{ fontSize: 12, color: '#888' }}>{record.email}</div>
          </div>
        </Space>
      ),
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      width: 160,
      render: (role: string, record: AuthUser) => {
        const isSelf = record.id === currentUser?.id;
        return isSelf ? (
          <Tag color={role === 'super_admin' ? 'purple' : role === 'admin' ? 'blue' : 'default'}>
            {role === 'super_admin' ? 'Super Admin' : role === 'admin' ? 'Admin' : 'User'}
          </Tag>
        ) : (
          <Select
            value={role}
            size="small"
            style={{ width: 140 }}
            onChange={(val) => handleRoleChange(record.id, val)}
            options={[
              { label: 'User', value: 'user' },
              { label: 'Admin', value: 'admin' },
              { label: 'Super Admin', value: 'super_admin' },
            ]}
          />
        );
      },
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_: unknown, record: AuthUser) => {
        const isSelf = record.id === currentUser?.id;
        return isSelf ? (
          <Tag color="green">Active</Tag>
        ) : (
          <Switch
            checked={record.is_active}
            checkedChildren="Active"
            unCheckedChildren="Inactive"
            onChange={(checked) => handleToggleActive(record.id, checked)}
          />
        );
      },
    },
    {
      title: 'Last Login',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 180,
      render: (val: string | null) =>
        val ? new Date(val).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
          hour: '2-digit', minute: '2-digit',
        }) : 'Never',
    },
    {
      title: '',
      key: 'actions',
      width: 60,
      render: (_: unknown, record: AuthUser) => {
        const isSelf = record.id === currentUser?.id;
        return isSelf ? null : (
          <Popconfirm
            title="Delete this user?"
            description="This action cannot be undone."
            onConfirm={() => handleDelete(record.id)}
            okText="Delete"
            okType="danger"
          >
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        );
      },
    },
  ];

  return (
    <div style={{ padding: '32px 48px', maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>User Management</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setInviteModalOpen(true)}>
          Invite User
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={false}
        style={{ background: '#fff', borderRadius: 12 }}
      />

      <Modal
        title="Invite User"
        open={inviteModalOpen}
        onCancel={() => { setInviteModalOpen(false); form.resetFields(); }}
        footer={null}
      >
        <Form form={form} layout="vertical" onFinish={handleInvite} initialValues={{ role: 'user' }}>
          <Form.Item
            name="email"
            label="Email Address"
            rules={[
              { required: true, message: 'Email is required' },
              { type: 'email', message: 'Enter a valid email' },
              {
                validator: (_, value) =>
                  value && value.endsWith('@gadgeon.com')
                    ? Promise.resolve()
                    : Promise.reject('Only @gadgeon.com emails allowed'),
              },
            ]}
          >
            <Input placeholder="firstname.lastname@gadgeon.com" />
          </Form.Item>
          <Form.Item name="role" label="Role">
            <Select
              options={[
                { label: 'User', value: 'user' },
                { label: 'Admin', value: 'admin' },
                { label: 'Super Admin', value: 'super_admin' },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              Send Invite
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagementPage;
