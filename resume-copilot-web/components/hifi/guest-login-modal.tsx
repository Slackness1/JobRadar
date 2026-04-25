'use client';

import { Checkbox, Form, Input, Modal, Typography, message } from 'antd';
import { useState } from 'react';

import { markAsGuest } from '@/components/resume-copilot/api';
import { HFBtn } from './hifi-primitives';

const GUEST_USERNAME = 'guest1';
const GUEST_PASSWORD = '123456';

const { Title, Paragraph } = Typography;

interface LoginFormValues {
  username: string;
  password: string;
  rememberMe: boolean;
  autoLogin: boolean;
}

interface GuestLoginModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function GuestLoginModal({ open, onClose, onSuccess }: GuestLoginModalProps) {
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<LoginFormValues>();

  const handleFinish = (values: LoginFormValues) => {
    if (values.username !== GUEST_USERNAME || values.password !== GUEST_PASSWORD) {
      void message.error('账号或密码错误');
      return;
    }
    setSubmitting(true);
    try {
      markAsGuest();
      onSuccess();
    } finally {
      window.setTimeout(() => setSubmitting(false), 200);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={420}
      centered
      destroyOnHidden
      maskClosable
      classNames={{ body: 'hf' }}
    >
      <div className="hf" style={{ padding: '8px 4px 4px' }}>
        <Title level={3} style={{ margin: 0, fontFamily: 'var(--font-serif)', fontWeight: 500, letterSpacing: '-0.02em' }}>
          登录后使用
        </Title>
        <Paragraph style={{ marginTop: 8, color: 'var(--olive)', fontSize: 14 }}>
          体验账号 <strong>guest1</strong> / 密码 <strong>123456</strong>；上传的简历仅保留 2 小时。
        </Paragraph>

        <Form<LoginFormValues>
          form={form}
          layout="vertical"
          initialValues={{ username: '', password: '', rememberMe: false, autoLogin: false }}
          onFinish={handleFinish}
          style={{ marginTop: 8 }}
        >
          <Form.Item label="账号" name="username" rules={[{ required: true, message: '请输入账号' }]}>
            <Input autoComplete="username" placeholder="guest1" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password autoComplete="current-password" placeholder="123456" />
          </Form.Item>
          <div style={{ display: 'flex', gap: 18, alignItems: 'center', marginTop: -4, marginBottom: 18 }}>
            <Form.Item name="rememberMe" valuePropName="checked" noStyle>
              <Checkbox>记住我</Checkbox>
            </Form.Item>
            <Form.Item name="autoLogin" valuePropName="checked" noStyle>
              <Checkbox>自动登录</Checkbox>
            </Form.Item>
          </div>
          <HFBtn
            type="submit"
            variant="primary"
            size="lg"
            disabled={submitting}
            style={{ width: '100%' }}
          >
            {submitting ? '登录中...' : '登录'}
          </HFBtn>
        </Form>
      </div>
    </Modal>
  );
}
