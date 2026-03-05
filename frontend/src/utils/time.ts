const beijingFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

function toDateFromApi(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  const normalized = hasTimezone ? value : `${value}Z`;
  return new Date(normalized);
}

export function formatBeijingDateTime(value: string | null | undefined): string {
  if (!value) return '-';
  const date = toDateFromApi(value);
  if (Number.isNaN(date.getTime())) return '-';
  return beijingFormatter.format(date);
}
