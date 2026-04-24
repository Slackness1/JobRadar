import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Checkbox, Form, Input, Typography } from 'antd';

import { submitPreviewLogin } from '../auth/mockSession';
import './Login.css';

const { Title, Paragraph } = Typography;

const COMPANY_COVERAGE_TARGET = 3486;
const LIVE_UPDATE_TARGET = 1087;
const COUNT_UP_INTERVAL_MS = 30;
const TICKER_DURATION_SECONDS = 42;

interface FeaturedJob {
  company: string;
  title: string;
  location: string;
  track: string;
}

const FEATURED_JOBS: FeaturedJob[] = [
  { company: '阿里巴巴', title: '后端开发工程师', location: '杭州', track: '互联网' },
  { company: '腾讯', title: '产品经理', location: '深圳', track: '互联网' },
  { company: '字节跳动', title: '算法工程师', location: '北京', track: '互联网' },
  { company: '中金公司', title: '研究助理', location: '上海', track: '券商' },
  { company: '中信证券', title: '投行项目助理', location: '北京', track: '券商' },
  { company: '中信建投', title: '行业研究岗', location: '上海', track: '券商' },
  { company: '华泰证券', title: '量化分析岗', location: '上海', track: '券商' },
  { company: '国家电网', title: '信息技术岗', location: '南京', track: '央国企' },
  { company: '国家电投', title: '数字化运营岗', location: '北京', track: '央国企' },
  { company: '招商银行', title: '数据分析岗', location: '深圳', track: '银行' },
  { company: '工商银行', title: '金融科技岗', location: '北京', track: '银行' },
  { company: '建设银行', title: '数据治理岗', location: '北京', track: '银行' },
  { company: '中国银行', title: '风险管理岗', location: '上海', track: '银行' },
  { company: '农业银行', title: '软件开发岗', location: '杭州', track: '银行' },
];

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
  const [tickerPaused, setTickerPaused] = useState(false);
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
      <section
        className="login-page__ticker"
        aria-label="重点岗位速览"
        onMouseEnter={() => setTickerPaused(true)}
        onMouseLeave={() => setTickerPaused(false)}
      >
        <div
          className="login-page__ticker-track"
          style={{
            animationDuration: `${TICKER_DURATION_SECONDS}s`,
            animationPlayState: tickerPaused ? 'paused' : 'running',
          }}
        >
          <span className="login-page__ticker-badge">重点岗位速览</span>
          {[...FEATURED_JOBS, ...FEATURED_JOBS].map((job, index) => (
            <span className="login-page__ticker-item" key={`${job.company}-${job.title}-${index}`}>
              <strong>{job.track}</strong>
              <span>{`${job.company} · ${job.title} · ${job.location}`}</span>
            </span>
          ))}
        </div>
      </section>

      <main className="login-page__shell">
        <section className="login-page__hero" aria-label="JobRadar 平台介绍">
          <Title className="login-page__title">更快发现值得投递的岗位</Title>
          <Paragraph className="login-page__description">
            面向高校就业与职业发展场景，聚合互联网、券商、央国企、银行等重点平台岗位，强调覆盖、筛选与更新时效。
          </Paragraph>

          <ul className="login-page__value-list">
            <li className="login-page__value-item">
              <span className="login-page__value-dot" aria-hidden="true" />
              <span>重点公司持续覆盖，岗位入口统一归集</span>
            </li>
            <li className="login-page__value-item">
              <span className="login-page__value-dot" aria-hidden="true" />
              <span>春招开放信息与岗位动态快速更新</span>
            </li>
            <li className="login-page__value-item">
              <span className="login-page__value-dot" aria-hidden="true" />
              <span>更适合学校老师与学生一眼扫清核心信息</span>
            </li>
          </ul>

          <div className="login-page__stats" aria-label="平台概览">
            <article className="login-page__stat">
              <div className="login-page__stat-value">{companyCoverage} 家公司</div>
              <div className="login-page__stat-label">春招开放公司与重点目标持续覆盖</div>
            </article>
            <article className="login-page__stat">
              <div className="login-page__stat-value">{liveUpdates} 日更新</div>
              <div className="login-page__stat-label">岗位动态与开放信息按日持续刷新</div>
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
