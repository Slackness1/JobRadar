import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, theme } from 'antd';
import {
  UnorderedListOutlined,
  SettingOutlined,
  StopOutlined,
  BarChartOutlined,
  BugOutlined,
  ClockCircleOutlined,
  TeamOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';

import Jobs from './pages/Jobs';
import JobIntel from './pages/JobIntel';
import Tracks from './pages/Tracks';
import Scoring from './pages/Scoring';
import Exclude from './pages/Exclude';
import Crawl from './pages/Crawl';
import Scheduler from './pages/Scheduler';
import CompanyExpand from './pages/CompanyExpand';


const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/', icon: <UnorderedListOutlined />, label: <Link to="/">岗位总览</Link> },
  { key: '/applied-flow', icon: <CheckCircleOutlined />, label: <Link to="/applied-flow">申请流程看板</Link> },
  { key: '/company-expand', icon: <TeamOutlined />, label: <Link to="/company-expand">公司展开</Link> },

  { key: '/tracks', icon: <SettingOutlined />, label: <Link to="/tracks">赛道配置</Link> },
  { key: '/exclude', icon: <StopOutlined />, label: <Link to="/exclude">排除规则</Link> },
  { key: '/scoring', icon: <BarChartOutlined />, label: <Link to="/scoring">评分设置</Link> },
  { key: '/crawl', icon: <BugOutlined />, label: <Link to="/crawl">爬取管理</Link> },
  { key: '/scheduler', icon: <ClockCircleOutlined />, label: <Link to="/scheduler">定时任务</Link> },
];

const PAGE_TITLES: Record<string, string> = {
  '/': '岗位总览',
  '/applied-flow': '申请流程看板',
  '/company-expand': '公司展开',

  '/tracks': '赛道配置',
  '/exclude': '排除规则',
  '/scoring': '评分设置',
  '/crawl': '爬取管理',
  '/scheduler': '定时任务',
};

function AppLayout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ overflow: 'auto', height: '100vh', position: 'sticky', top: 0, left: 0 }}
      >
        <div style={{
          color: '#fff',
          textAlign: 'center',
          padding: '16px 0',
          fontSize: collapsed ? 16 : 20,
          fontWeight: 'bold',
          letterSpacing: 1,
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          marginBottom: 8,
        }}>
          {collapsed ? 'JR' : 'JobRadar'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          items={menuItems}
          mode="inline"
        />
      </Sider>
      <Layout>
        <Header style={{
          background: colorBgContainer,
          padding: '0 24px',
          fontSize: 18,
          fontWeight: 600,
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
        }}>
          {PAGE_TITLES[location.pathname] || 'JobRadar'}
        </Header>
        <Content style={{
          margin: 16,
          padding: 20,
          background: colorBgContainer,
          borderRadius: borderRadiusLG,
          minHeight: 280,
        }}>
          <Routes>
            <Route path="/" element={<Jobs />} />
            <Route path="/applied-flow" element={<Jobs />} />
            <Route path="/company-expand" element={<CompanyExpand />} />

            <Route path="/job-intel/:jobId" element={<JobIntel />} />

            <Route path="/tracks" element={<Tracks />} />
            <Route path="/scoring" element={<Scoring />} />
            <Route path="/exclude" element={<Exclude />} />
            <Route path="/crawl" element={<Crawl />} />
            <Route path="/scheduler" element={<Scheduler />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
