/**
 * OpportunitiesDashboard - Main UI for reviewing and approving crypto opportunities
 * Displays opportunities, approval workflow, and statistics
 */

import React, { useState, useEffect } from 'react';
import './OpportunitiesDashboard.css';
import {
  Table,
  Button,
  Modal,
  Form,
  Select,
  Input,
  Statistic,
  Row,
  Col,
  Card,
  Tag,
  Space,
  Spin,
  message,
  Pagination,
  DatePicker,
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  DollarOutlined,
  PercentageOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';

interface Opportunity {
  id: string;
  title: string;
  description: string;
  type: string;
  source: string;
  estimated_value_usd: number;
  effort_level: string;
  approval_status: string;
  estimated_roi: number;
  blockchain: string;
  url: string;
  discovered_at: string;
}

interface Statistics {
  total_opportunities: number;
  by_type: Record<string, number>;
  approved_count: number;
  pending_count: number;
  total_estimated_value_usd: number;
  average_roi: number;
}

const OpportunitiesDashboard: React.FC = () => {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [stats, setStats] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [approvalReason, setApprovalReason] = useState('');
  const [operator, setOperator] = useState('');
  const [filterType, setFilterType] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Fetch opportunities
  const fetchOpportunities = async () => {
    setLoading(true);
    try {
      const params: any = {
        limit: pageSize,
        offset: (currentPage - 1) * pageSize,
      };
      if (filterType) params.type = filterType;
      if (filterStatus) params.status = filterStatus;

      const response = await axios.get('/api/opportunities', { params });
      setOpportunities(response.data.opportunities);
    } catch (error) {
      message.error('Failed to fetch opportunities');
    } finally {
      setLoading(false);
    }
  };

  // Fetch statistics
  const fetchStatistics = async () => {
    try {
      const response = await axios.get('/api/statistics');
      setStats(response.data);
    } catch (error) {
      message.error('Failed to fetch statistics');
    }
  };

  // Fetch pending approvals
  const fetchPendingApprovals = async () => {
    try {
      const response = await axios.get('/api/opportunities/pending/approval');
    } catch (error) {
    }
  };

  // Initial load
  useEffect(() => {
    fetchOpportunities();
    fetchStatistics();
    fetchPendingApprovals();

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchOpportunities();
      fetchStatistics();
    }, 30000);

    return () => clearInterval(interval);
  }, [currentPage, pageSize, filterType, filterStatus]);

  // Approve opportunity
  const handleApprove = async (opportunity: Opportunity) => {
    if (!operator) {
      message.error('Please enter operator name');
      return;
    }

    try {
      await axios.post(`/api/opportunities/${opportunity.id}/approve`, {
        opportunity_id: opportunity.id,
        operator,
        status: 'approved',
        notes: approvalReason,
      });

      message.success(`Approved: ${opportunity.title}`);
      setModalVisible(false);
      setApprovalReason('');
      setOperator('');
      fetchOpportunities();
      fetchStatistics();
    } catch (error) {
      message.error('Failed to approve opportunity');
    }
  };

  // Reject opportunity
  const handleReject = async (opportunity: Opportunity) => {
    if (!operator) {
      message.error('Please enter operator name');
      return;
    }

    try {
      await axios.post(`/api/opportunities/${opportunity.id}/reject`, {
        opportunity_id: opportunity.id,
        operator,
        status: 'rejected',
        notes: approvalReason,
      });

      message.success(`Rejected: ${opportunity.title}`);
      setModalVisible(false);
      setApprovalReason('');
      setOperator('');
      fetchOpportunities();
      fetchStatistics();
    } catch (error) {
      message.error('Failed to reject opportunity');
    }
  };

  // Claim opportunity
  const handleClaim = async (opportunity: Opportunity) => {
    try {
      await axios.post(`/api/opportunities/${opportunity.id}/claim`, {
        opportunity_id: opportunity.id,
        claimed_by: operator || 'Unknown',
        notes: approvalReason,
      });

      message.success(`Claimed: ${opportunity.title}`);
      setModalVisible(false);
      setApprovalReason('');
      setOperator('');
      fetchOpportunities();
      fetchStatistics();
    } catch (error) {
      message.error('Failed to claim opportunity');
    }
  };

  // Refresh scan
  const handleRefreshScan = async () => {
    setLoading(true);
    try {
      await axios.post('/api/scan', {});
      message.success('Scan started - opportunities will be updated shortly');
      setTimeout(() => {
        fetchOpportunities();
        fetchStatistics();
      }, 2000);
    } catch (error) {
      message.error('Failed to start scan');
    } finally {
      setLoading(false);
    }
  };

  // Export opportunities
  const handleExport = async () => {
    try {
      const response = await axios.get('/api/export', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'opportunities.json');
      document.body.appendChild(link);
      link.click();
      message.success('Opportunities exported');
    } catch (error) {
      message.error('Failed to export opportunities');
    }
  };

  // Get status color
  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'approved':
        return 'green';
      case 'rejected':
        return 'red';
      case 'pending':
        return 'orange';
      case 'claimed':
        return 'blue';
      default:
        return 'default';
    }
  };

  // Get effort color
  const getEffortColor = (effort: string): string => {
    switch (effort) {
      case 'very_easy':
        return 'green';
      case 'easy':
        return 'lime';
      case 'medium':
        return 'orange';
      case 'hard':
        return 'red';
      default:
        return 'default';
    }
  };

  // Table columns
  const columns = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      render: (text: string) => (
        <button
          type="button"
          aria-label={`View details for ${text}`}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0 }}
        >
          {text}
        </button>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      filters: [
        { text: 'Airdrop', value: 'airdrop' },
        { text: 'Faucet', value: 'faucet' },
        { text: 'Whale', value: 'whale_movement' },
        { text: 'Staking', value: 'staking_reward' },
        { text: 'Yield', value: 'yield_farming' },
        { text: 'Liquidity', value: 'liquidity_mining' },
      ],
      render: (type: string) => <Tag>{type.toUpperCase()}</Tag>,
    },
    {
      title: 'Value (USD)',
      dataIndex: 'estimated_value_usd',
      key: 'estimated_value_usd',
      render: (value: number) => `$${value.toLocaleString()}`,
      sorter: (a, b) => a.estimated_value_usd - b.estimated_value_usd,
    },
    {
      title: 'ROI',
      dataIndex: 'estimated_roi',
      key: 'estimated_roi',
      render: (roi: number) => (
        <span className={roi > 1 ? 'roi-positive' : 'roi-negative'}>
          {(roi * 100).toFixed(1)}%
        </span>
      ),
      sorter: (a, b) => a.estimated_roi - b.estimated_roi,
    },
    {
      title: 'Effort',
      dataIndex: 'effort_level',
      key: 'effort_level',
      render: (effort: string) => (
        <Tag color={getEffortColor(effort)}>{effort.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Blockchain',
      dataIndex: 'blockchain',
      key: 'blockchain',
      render: (chain: string) => <Tag color="blue">{chain.toUpperCase()}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'approval_status',
      key: 'approval_status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Opportunity) => (
        <Space>
          {record.approval_status === 'pending' && (
            <>
              <Button
                type="primary"
                size="small"
                onClick={() => {
                  setSelectedOpp(record);
                  setModalVisible(true);
                }}
              >
                Review
              </Button>
            </>
          )}
          {record.approval_status === 'approved' && (
            <Button
              type="default"
              size="small"
              onClick={() => {
                setSelectedOpp(record);
                setModalVisible(true);
              }}
            >
              Claim
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div className="opportunities-dashboard">
      {/* Header */}
      <Row gutter={[16, 16]} className="dashboard-header">
        <Col span={24}>
          <Row justify="space-between" align="middle">
            <h1>Rimuru Opportunity Aggregator</h1>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefreshScan}
                loading={loading}
              >
                Refresh Scan
              </Button>
              <Button icon={<DownloadOutlined />} onClick={handleExport}>
                Export
              </Button>
            </Space>
          </Row>
        </Col>
      </Row>

      {/* Statistics */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Total Opportunities"
                value={stats.total_opportunities}
                prefix={<ExclamationCircleOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Pending Approval"
                value={stats.pending_count}
                valueStyle={{ color: '#ff7a45' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Approved"
                value={stats.approved_count}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card>
              <Statistic
                title="Total Value (USD)"
                value={stats.total_estimated_value_usd}
                prefix={<DollarOutlined />}
                suffix="USD"
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Filters */}
      <Card style={{ marginBottom: '24px' }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} lg={6}>
            <Select
              placeholder="Filter by type"
              style={{ width: '100%' }}
              allowClear
              onChange={(value) => {
                setFilterType(value);
                setCurrentPage(1);
              }}
              options={[
                { label: 'Airdrop', value: 'airdrop' },
                { label: 'Faucet', value: 'faucet' },
                { label: 'Whale Movement', value: 'whale_movement' },
                { label: 'Staking', value: 'staking_reward' },
                { label: 'Yield Farming', value: 'yield_farming' },
                { label: 'Liquidity Mining', value: 'liquidity_mining' },
              ]}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Select
              placeholder="Filter by status"
              style={{ width: '100%' }}
              allowClear
              onChange={(value) => {
                setFilterStatus(value);
                setCurrentPage(1);
              }}
              options={[
                { label: 'Pending', value: 'pending' },
                { label: 'Approved', value: 'approved' },
                { label: 'Rejected', value: 'rejected' },
                { label: 'Claimed', value: 'claimed' },
              ]}
            />
          </Col>
        </Row>
      </Card>

      {/* Opportunities Table */}
      <Card>
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={opportunities.map((opp, index) => ({
              ...opp,
              key: opp.id,
            }))}
            pagination={false}
            scroll={{ x: 1200 }}
          />
        </Spin>

        {/* Pagination */}
        <Row justify="center" style={{ marginTop: '16px' }}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            pageSizeOptions={['10', '20', '50', '100']}
            onChange={(page) => setCurrentPage(page)}
            onShowSizeChange={(_, size) => {
              setPageSize(size);
              setCurrentPage(1);
            }}
          />
        </Row>
      </Card>

      {/* Approval Modal */}
      <Modal
        title={selectedOpp ? `Review: ${selectedOpp.title}` : 'Review Opportunity'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setSelectedOpp(null);
          setApprovalReason('');
          setOperator('');
        }}
        footer={null}
        width={600}
      >
        {selectedOpp && (
          <Form layout="vertical">
            <Form.Item label="Title" labelCol={{ span: 24 }}>
              <Input disabled defaultValue={selectedOpp.title} />
            </Form.Item>

            <Form.Item label="Type" labelCol={{ span: 24 }}>
              <Input disabled defaultValue={selectedOpp.type} />
            </Form.Item>

            <Form.Item label="Estimated Value (USD)" labelCol={{ span: 24 }}>
              <Input
                disabled
                defaultValue={`$${selectedOpp.estimated_value_usd.toLocaleString()}`}
              />
            </Form.Item>

            <Form.Item label="Estimated ROI" labelCol={{ span: 24 }}>
              <Input
                disabled
                defaultValue={`${(selectedOpp.estimated_roi * 100).toFixed(2)}%`}
              />
            </Form.Item>

            <Form.Item label="Blockchain" labelCol={{ span: 24 }}>
              <Input disabled defaultValue={selectedOpp.blockchain} />
            </Form.Item>

            <Form.Item label="URL" labelCol={{ span: 24 }}>
              <Input
                defaultValue={selectedOpp.url}
                onClick={() => window.open(selectedOpp.url, '_blank')}
              />
            </Form.Item>

            <Form.Item label="Operator Name" labelCol={{ span: 24 }}>
              <Input
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                placeholder="Enter your operator ID"
              />
            </Form.Item>

            <Form.Item label="Notes" labelCol={{ span: 24 }}>
              <Input.TextArea
                value={approvalReason}
                onChange={(e) => setApprovalReason(e.target.value)}
                placeholder="Add approval or rejection notes"
                rows={3}
              />
            </Form.Item>

            <Form.Item>
              <Space>
                {selectedOpp.approval_status === 'pending' && (
                  <>
                    <Button
                      type="primary"
                      onClick={() => handleApprove(selectedOpp)}
                    >
                      <CheckCircleOutlined /> Approve
                    </Button>
                    <Button
                      danger
                      onClick={() => handleReject(selectedOpp)}
                    >
                      <CloseCircleOutlined /> Reject
                    </Button>
                  </>
                )}
                {selectedOpp.approval_status === 'approved' && (
                  <Button
                    type="primary"
                    onClick={() => handleClaim(selectedOpp)}
                  >
                    Claim Opportunity
                  </Button>
                )}
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
};

export default OpportunitiesDashboard;
