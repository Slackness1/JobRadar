'use client';

/**
 * CityBlock — "目标城市" pill multi-select for the Confirm Profile page (P2).
 *
 * 11 cities (北京 / 上海 / 深圳 / 香港 / 新加坡 / 杭州 / 广州 / 南京 / 苏州 /
 * 成都 / 其他). Multi-select pills. Selected → terracotta fill + drop shadow.
 * Unselected → transparent + warm-border ring. Matches design
 * `hifi-ws-confirm.jsx::HFCityBlock`.
 *
 * Hint copy:
 *   - If parser inferred a non-empty `inferred_offices`, show "AI 看你简历像偏
 *     「XX」, 已帮你预勾对应城市".
 *   - Otherwise show generic "默认勾选北京 + 上海 — 加多个城市推荐会更全".
 *
 * Persistence batched in parent → no PUT here. Stored in
 * `preferred_locations` on confirm.
 *
 * Scope: `.hf .rc-confirm`.
 */

// SAIF MF / MBA 学生主流目标城市 — 顺序按设计 hifi-ws-confirm.jsx 来。
export const COMMON_CITIES: string[] = [
  '北京',
  '上海',
  '深圳',
  '香港',
  '新加坡',
  '杭州',
  '广州',
  '南京',
  '苏州',
  '成都',
  '其他',
];

// 中文 label 给 hint 文案用 (parser 推断 office 区域 → 中文)
const OFFICE_LABEL_CN: Record<string, string> = {
  hk: '香港',
  sg: '新加坡',
  mainland: '中国大陆',
  global: '海外 / 全球流动',
};

export interface CityBlockProps {
  selectedCities: string[];
  onToggleCity: (city: string) => void;
  /** Parser-inferred office regions (`inferred_offices`). Drives the hint copy. */
  inferredOffices: string[];
  disabled?: boolean;
}

export function CityBlock({
  selectedCities,
  onToggleCity,
  inferredOffices,
  disabled,
}: CityBlockProps) {
  const inferredLabels = inferredOffices
    .map((o) => OFFICE_LABEL_CN[o] || o)
    .filter(Boolean);
  const hint =
    inferredLabels.length > 0
      ? `AI 看你简历像偏「${inferredLabels.join(' / ')}」, 已帮你预勾对应城市 — 可自行加减`
      : '默认勾选北京 + 上海 — 加多个城市推荐会更全';

  return (
    <div className="rc-confirm__card rc-confirm__block">
      <div className="rc-confirm__block-head">
        <h3 className="rc-confirm__block-title">目标城市</h3>
        <span className="rc-confirm__block-hint">{hint}</span>
      </div>
      <div className="rc-confirm__city-grid">
        {COMMON_CITIES.map((city) => {
          const on = selectedCities.includes(city);
          return (
            <button
              key={city}
              type="button"
              role="checkbox"
              aria-checked={on}
              className={`rc-confirm__city-pill${on ? ' is-on' : ''}`}
              onClick={() => onToggleCity(city)}
              disabled={disabled}
            >
              {city}
            </button>
          );
        })}
      </div>
    </div>
  );
}
