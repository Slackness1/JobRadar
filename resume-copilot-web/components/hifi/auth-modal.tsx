'use client';

/**
 * AuthModal — alpha-1 内测账号系统。3 步状态机:
 *   - 'tabs'   登录 / 注册 两个 tab
 *   - 'verify' 注册之后弹出 6 位邮箱码输入
 * 旧的 guest 试用作为底部小字链接保留。
 */
import { Form, Input, Modal, Tabs, Typography, message } from 'antd';
import { useState } from 'react';

import {
  apiLogin,
  apiRegister,
  apiResendVerification,
  apiVerifyEmail,
  markAsGuest,
} from '@/components/resume-copilot/api';
import { HFBtn } from './hifi-primitives';

const { Title, Paragraph, Text } = Typography;

type Mode = 'tabs' | 'verify';

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface LoginFormValues { email: string; password: string; }
interface RegisterFormValues { email: string; password: string; invite_code: string; }

export function AuthModal({ open, onClose, onSuccess }: AuthModalProps) {
  const [mode, setMode] = useState<Mode>('tabs');
  const [pendingUserId, setPendingUserId] = useState<number | null>(null);
  const [pendingEmail, setPendingEmail] = useState<string>('');
  const [verifyCode, setVerifyCode] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  const reset = () => {
    setMode('tabs');
    setPendingUserId(null);
    setPendingEmail('');
    setVerifyCode('');
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  // ── Register ────────────────────────────────────────────────────────────
  const handleRegister = async (values: RegisterFormValues) => {
    setSubmitting(true);
    try {
      const result = await apiRegister({
        email: values.email.trim().toLowerCase(),
        password: values.password,
        invite_code: values.invite_code.trim().toUpperCase(),
      });
      void message.success(result.message);
      setPendingUserId(result.user_id);
      setPendingEmail(result.email);
      setMode('verify');
    } catch (err) {
      void message.error(parseError(err));
    } finally {
      setSubmitting(false);
    }
  };

  // ── Verify ──────────────────────────────────────────────────────────────
  const handleVerify = async () => {
    if (pendingUserId == null) return;
    if (verifyCode.length !== 6) {
      void message.error('请输入 6 位验证码');
      return;
    }
    setSubmitting(true);
    try {
      await apiVerifyEmail({ user_id: pendingUserId, code: verifyCode });
      void message.success(`登录成功,欢迎 ${pendingEmail}`);
      reset();
      onSuccess();
    } catch (err) {
      void message.error(parseError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (pendingUserId == null || resendCooldown > 0) return;
    setSubmitting(true);
    try {
      const r = await apiResendVerification(pendingUserId);
      void message.success(r.message);
      setResendCooldown(60);
      const t = window.setInterval(() => {
        setResendCooldown((c) => {
          if (c <= 1) { window.clearInterval(t); return 0; }
          return c - 1;
        });
      }, 1000);
    } catch (err) {
      void message.error(parseError(err));
    } finally {
      setSubmitting(false);
    }
  };

  // ── Login ───────────────────────────────────────────────────────────────
  const handleLogin = async (values: LoginFormValues) => {
    setSubmitting(true);
    try {
      const result = await apiLogin({
        email: values.email.trim().toLowerCase(),
        password: values.password,
      });
      if (!result.email_verified) {
        void message.warning('邮箱未验证,请先完成验证');
        setPendingUserId(result.user_id);
        setPendingEmail(result.email);
        setMode('verify');
        return;
      }
      void message.success(`欢迎回来 ${result.email}`);
      reset();
      onSuccess();
    } catch (err) {
      void message.error(parseError(err));
    } finally {
      setSubmitting(false);
    }
  };

  // ── 游客试用降级入口 ────────────────────────────────────────────────────
  const handleGuestTrial = () => {
    markAsGuest();
    void message.info('已进入游客模式,数据 2 小时后清理');
    onSuccess();
  };

  return (
    <Modal
      open={open}
      onCancel={handleClose}
      footer={null}
      width={460}
      centered
      destroyOnHidden
      mask={{ closable: true }}
      classNames={{ body: 'hf' }}
    >
      <div className="hf" style={{ padding: '8px 4px 4px' }}>
        {mode === 'tabs' ? (
          <>
            <Title level={3} style={{
              margin: 0,
              fontFamily: 'var(--font-serif)',
              fontWeight: 500,
              letterSpacing: '-0.02em',
            }}>
              JobRadar · alpha 内测
            </Title>
            <Paragraph style={{ marginTop: 6, color: 'var(--olive)', fontSize: 13 }}>
              已有账号直接登录;否则用邀请码注册新账号。
            </Paragraph>

            <Tabs
              defaultActiveKey="login"
              items={[
                {
                  key: 'login',
                  label: '登录',
                  children: (
                    <Form<LoginFormValues>
                      layout="vertical"
                      onFinish={handleLogin}
                      style={{ marginTop: 8 }}
                    >
                      <Form.Item
                        label="邮箱"
                        name="email"
                        rules={[
                          { required: true, message: '请输入邮箱' },
                          { type: 'email', message: '邮箱格式不正确' },
                        ]}
                      >
                        <Input autoComplete="email" placeholder="name@example.com" />
                      </Form.Item>
                      <Form.Item
                        label="密码"
                        name="password"
                        rules={[{ required: true, message: '请输入密码' }]}
                      >
                        <Input.Password autoComplete="current-password" />
                      </Form.Item>
                      <HFBtn type="submit" variant="primary" size="lg"
                             disabled={submitting} style={{ width: '100%' }}>
                        {submitting ? '登录中...' : '登录'}
                      </HFBtn>
                    </Form>
                  ),
                },
                {
                  key: 'register',
                  label: '邀请码注册',
                  children: (
                    <Form<RegisterFormValues>
                      layout="vertical"
                      onFinish={handleRegister}
                      style={{ marginTop: 8 }}
                    >
                      <Form.Item
                        label="邀请码"
                        name="invite_code"
                        rules={[{ required: true, message: '请输入邀请码' }]}
                      >
                        <Input placeholder="JR-XXXXXXXX" style={{ fontFamily: 'var(--font-mono)' }} />
                      </Form.Item>
                      <Form.Item
                        label="邮箱"
                        name="email"
                        rules={[
                          { required: true, message: '请输入邮箱' },
                          { type: 'email', message: '邮箱格式不正确' },
                        ]}
                      >
                        <Input autoComplete="email" placeholder="name@example.com" />
                      </Form.Item>
                      <Form.Item
                        label="密码 (至少 6 位)"
                        name="password"
                        rules={[
                          { required: true, message: '请输入密码' },
                          { min: 6, message: '密码至少 6 位' },
                        ]}
                      >
                        <Input.Password autoComplete="new-password" />
                      </Form.Item>
                      <HFBtn type="submit" variant="primary" size="lg"
                             disabled={submitting} style={{ width: '100%' }}>
                        {submitting ? '提交中...' : '注册 + 发送邮箱验证码'}
                      </HFBtn>
                    </Form>
                  ),
                },
              ]}
            />

            <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px dashed var(--border)' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                没有邀请码?可以{' '}
                <a onClick={handleGuestTrial} style={{ cursor: 'pointer', textDecoration: 'underline' }}>
                  游客试用
                </a>
                {' '}(账号 guest1 / 密码 123456,数据 2 小时清理)
              </Text>
            </div>
          </>
        ) : (
          // ── verify 步骤 ──────────────────────────────────────────────
          <>
            <Title level={3} style={{
              margin: 0,
              fontFamily: 'var(--font-serif)',
              fontWeight: 500,
              letterSpacing: '-0.02em',
            }}>
              输入邮箱验证码
            </Title>
            <Paragraph style={{ marginTop: 6, color: 'var(--olive)', fontSize: 13 }}>
              我们已向 <strong>{pendingEmail}</strong> 发送了 6 位验证码,10 分钟内有效。
              <br /><Text type="secondary" style={{ fontSize: 12 }}>
                没收到?去 QQ 邮箱垃圾邮件夹找找,或用下方「重新发送」。
              </Text>
            </Paragraph>

            <div style={{ marginTop: 20 }}>
              <Input
                size="large"
                placeholder="6 位数字"
                value={verifyCode}
                maxLength={6}
                onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, ''))}
                onPressEnter={handleVerify}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 24,
                  letterSpacing: '8px',
                  textAlign: 'center',
                }}
                autoFocus
              />
            </div>

            <div style={{ marginTop: 18, display: 'flex', gap: 12 }}>
              <HFBtn variant="primary" size="lg" onClick={handleVerify}
                     disabled={submitting || verifyCode.length !== 6} style={{ flex: 1 }}>
                {submitting ? '验证中...' : '验证并登录'}
              </HFBtn>
              <HFBtn variant="ghost" size="lg" onClick={handleResend}
                     disabled={submitting || resendCooldown > 0}>
                {resendCooldown > 0 ? `${resendCooldown}s 后可重发` : '重新发送'}
              </HFBtn>
            </div>

            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <a onClick={reset} style={{ cursor: 'pointer' }}>← 返回</a>
              </Text>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function parseError(err: unknown): string {
  if (err instanceof Error) {
    try {
      const parsed = JSON.parse(err.message);
      if (parsed?.detail) return String(parsed.detail);
    } catch { /* fallthrough */ }
    return err.message;
  }
  return String(err);
}
