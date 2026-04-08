import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Checkbox, Form, Input, Typography } from 'antd';

import { submitPreviewLogin } from '../auth/mockSession';
import './Login.css';

const { Title, Paragraph } = Typography;

const COMPANY_COVERAGE_TARGET = 3486;
const LIVE_UPDATE_TARGET = 1087;
const COUNT_UP_INTERVAL_MS = 30;

function useAnimatedMetric(target: number, keepGrowing = false) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let countUpTimer: number | undefined;
    let liveTimer: number | undefined;
    let stopped = false;
    const step = Math.max(1, Math.ceil(target / 40));

    const scheduleLiveUpdate = () => {
      if (stopped) {
        return;
      }

      liveTimer = window.setTimeout(() => {
        setValue((current) => current + 1);
        scheduleLiveUpdate();
      }, 1000 + Math.floor(Math.random() * 1001));
    };

    countUpTimer = window.setInterval(() => {
      setValue((current) => {
        const next = Math.min(current + step, target);

        if (next >= target && countUpTimer) {
          window.clearInterval(countUpTimer);
          countUpTimer = undefined;

          if (keepGrowing) {
            scheduleLiveUpdate();
          }
        }

        return next;
      });
    }, COUNT_UP_INTERVAL_MS);

    return () => {
      stopped = true;

      if (countUpTimer) {
        window.clearInterval(countUpTimer);
      }

      if (liveTimer) {
        window.clearTimeout(liveTimer);
      }
    };
  }, [target, keepGrowing]);

  return value;
}

interface LoginFormValues {
  username: string;
  password: string;
  rememberMe: boolean;
  autoLogin: boolean;
}

function getSubmitErrorMessage(error: unknown) {
  if (error instanceof Error && error.message === 'INVALID_CREDENTIALS') {
    return '账号或密码错误，请重试';
  }

  return '登录失败，请稍后重试';
}

export default function Login() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const companyCoverage = useAnimatedMetric(COMPANY_COVERAGE_TARGET);
  const liveUpdates = useAnimatedMetric(LIVE_UPDATE_TARGET, true);

  const handleFinish = async (values: LoginFormValues) => {
    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitPreviewLogin(values);
      navigate('/', { replace: true });
    } catch (error) {
      setSubmitError(getSubmitErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <main className="login-page__shell">
        <section className="login-page__hero" aria-label="JobRadar 平台介绍">
          <Title className="login-page__title">更快发现值得投递的岗位</Title>
          <Paragraph className="login-page__description">
            聚合、筛选、评分与跟踪，集中管理你的求职信息流。
          </Paragraph>

          <ul className="login-page__value-list">
            <li className="login-page__value-item">
              <span className="login-page__value-dot" aria-hidden="true" />
              <span>多来源岗位聚合，减少重复搜岗</span>
            </li>
            <li className="login-page__value-item">
              <span className="login-page__value-dot" aria-hidden="true" />
              <span>统一筛选与评分，快速定位优先机会</span>
            </li>
            <li className="login-page__value-item">
              <span className="login-page__value-dot" aria-hidden="true" />
              <span>申请流程可追踪，避免信息散落</span>
            </li>
          </ul>

          <div className="login-page__stats" aria-label="平台概览">
            <article className="login-page__stat">
              <div className="login-page__stat-value">{companyCoverage} 家公司</div>
              <div className="login-page__stat-label">春招开放公司与重点目标持续覆盖</div>
            </article>
            <article className="login-page__stat">
              <div className="login-page__stat-value">{liveUpdates} 更新</div>
              <div className="login-page__stat-label">岗位动态与开放信息持续刷新</div>
            </article>
          </div>
        </section>

        <section className="login-page__panel" aria-label="登录面板">
          <Title className="login-page__panel-title" level={2}>登录 JobRadar</Title>
          <Paragraph className="login-page__panel-copy">
            登录后继续访问岗位总览、申请流程看板与配置中心。
          </Paragraph>

          <Form<LoginFormValues>
            layout="vertical"
            initialValues={{ rememberMe: false, autoLogin: false }}
            onFinish={handleFinish}
          >
            {submitError ? <Alert className="login-page__alert" showIcon type="error" title={submitError} /> : null}
            <Form.Item label="账号" name="username" rules={[{ required: true, message: '请输入账号' }]}>
              <Input autoComplete="username" />
            </Form.Item>
            <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <div className="login-page__options">
              <Form.Item name="rememberMe" valuePropName="checked" noStyle>
                <Checkbox>记住我</Checkbox>
              </Form.Item>
              <Form.Item name="autoLogin" valuePropName="checked" noStyle>
                <Checkbox>自动登录</Checkbox>
              </Form.Item>
            </div>
            <Button
              className="login-page__submit"
              type="primary"
              htmlType="submit"
              aria-label="登录"
              loading={submitting}
            >
              {submitting ? '登录中...' : '登录'}
            </Button>
          </Form>

          <div className="login-page__footer">
            <div>持续追踪岗位动态、目标公司与申请进展。</div>
            <div className="login-page__footer-help">让求职信息流保持更新与可执行。</div>
          </div>
        </section>
      </main>
    </div>
  );
}
