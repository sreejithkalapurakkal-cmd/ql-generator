import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Space, Popconfirm, message, Tag } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, RocketOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listICPs, deleteICP } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPConfig } from '../types';

const ICPListPage: React.FC = () => {
  const navigate = useNavigate();
  const [icps, setIcps] = useState<ICPConfig[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchICPs = () => {
    setLoading(true);
    listICPs().then((res) => setIcps(res.data)).finally(() => setLoading(false));
  };

  useEffect(() => { fetchICPs(); }, []);

  const handleDelete = async (id: string) => {
    await deleteICP(id);
    message.success('ICP deleted');
    fetchICPs();
  };

  const handleRunPipeline = async (icpId: string) => {
    try {
      const res = await startPipeline({ icp_config_id: icpId, options: { max_companies: 15, max_contacts_per_company: 5 } });
      message.success('Pipeline started');
      navigate(`/pipeline/${res.data.id}`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to start pipeline');
    }
  };

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Description', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: 'Industries',
      key: 'industries',
      render: (_: unknown, record: ICPConfig) => {
        const cfg = record.config as any;
        return cfg?.industry_types?.slice(0, 3).map((i: any) => (
          <Tag key={i.vertical}>{i.vertical}</Tag>
        ));
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      render: (d: string) => new Date(d).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: ICPConfig) => (
        <Space>
          <Button size="small" type="primary" onClick={() => handleRunPipeline(record.id!)}>
            Run Pipeline
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/icp/${record.id}/edit`)}>
            Edit
          </Button>
          <Popconfirm title="Delete this ICP?" onConfirm={() => handleDelete(record.id!)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Configuration</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 className="page-title">Saved ICPs</h1>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
            New ICP
          </Button>
        </div>
      </div>

      <Card>
        <Table columns={columns} dataSource={icps} rowKey="id" loading={loading} />
      </Card>
    </div>
  );
};

export default ICPListPage;
